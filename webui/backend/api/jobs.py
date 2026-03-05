import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from webui.backend.database import get_db
from webui.backend.models import ConfigRecord, JobRecord
from webui.backend.services.job_runner import cancel_job, run_job, subscribe, unsubscribe

router = APIRouter(tags=["jobs"])

# Track background tasks to prevent GC (satisfies RUF006)
_background_tasks: set[asyncio.Task] = set()


def _schedule_job(job_id: str, yaml_content: str):
    """Schedule a job to run in the background event loop, if available."""
    try:
        loop = asyncio.get_running_loop()
        task = loop.create_task(run_job(job_id, yaml_content))
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except RuntimeError:
        pass  # No event loop in sync test context


class JobCreate(BaseModel):
    config_id: str


class JobResponse(BaseModel):
    id: str
    config_id: str
    config_name: str
    status: str
    progress: dict | None
    log: str
    created_at: str
    started_at: str | None
    completed_at: str | None
    error: str | None
    data_path: str | None


def _to_response(job: JobRecord) -> JobResponse:
    return JobResponse(
        id=job.id,
        config_id=job.config_id,
        config_name=job.config_name,
        status=job.status,
        progress=job.progress,
        log=job.log,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
        data_path=job.data_path,
    )


@router.post("/api/jobs", response_model=JobResponse, status_code=201)
async def submit_job(body: JobCreate, db: Session = Depends(get_db)):
    config = db.get(ConfigRecord, body.config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    job = JobRecord(config_id=config.id, config_name=config.name)
    db.add(job)
    db.commit()
    db.refresh(job)

    # Launch job in background
    _schedule_job(job.id, config.yaml_content)

    return _to_response(job)


@router.get("/api/jobs", response_model=list[JobResponse])
def list_jobs(status: str | None = None, db: Session = Depends(get_db)):
    query = db.query(JobRecord).order_by(JobRecord.created_at.desc())
    if status:
        query = query.filter(JobRecord.status == status)
    return [_to_response(j) for j in query.all()]


@router.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(JobRecord, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _to_response(job)


@router.post("/api/jobs/{job_id}/cancel", status_code=200)
def cancel(job_id: str, db: Session = Depends(get_db)):
    if not cancel_job(job_id, db):
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "cancelled"}


@router.post("/api/jobs/{job_id}/rerun", response_model=JobResponse, status_code=201)
async def rerun_job(job_id: str, db: Session = Depends(get_db)):
    old_job = db.get(JobRecord, job_id)
    if not old_job:
        raise HTTPException(status_code=404, detail="Job not found")
    config = db.get(ConfigRecord, old_job.config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config no longer exists")
    new_job = JobRecord(config_id=config.id, config_name=config.name)
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    _schedule_job(new_job.id, config.yaml_content)
    return _to_response(new_job)


@router.websocket("/ws/jobs/{job_id}")
async def job_ws(websocket: WebSocket, job_id: str):
    await websocket.accept()
    queue = subscribe(job_id)
    try:
        while True:
            msg = await queue.get()
            await websocket.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(job_id, queue)
