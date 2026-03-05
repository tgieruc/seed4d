from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from webui.backend.api.configs import router as configs_router
from webui.backend.api.datasets import router as datasets_router
from webui.backend.api.jobs import router as jobs_router
from webui.backend.api.references import router as references_router
from webui.backend.database import Base, SessionLocal, engine
from webui.backend.models import JobRecord
from webui.backend.services.job_runner import cleanup_stale_configs, mark_active_jobs_failed

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # On startup: mark orphaned running/queued jobs as failed
    db = SessionLocal()
    orphaned = db.query(JobRecord).filter(JobRecord.status.in_(["queued", "running"])).all()
    for job in orphaned:
        job.status = "failed"
        job.error = "Server restarted — job was interrupted. Please re-run."
        job.completed_at = datetime.now(UTC)
    if orphaned:
        db.commit()
    cleanup_stale_configs()
    db.close()
    yield
    # Shutdown: mark any still-running jobs as failed
    mark_active_jobs_failed()


app = FastAPI(title="SEED4D Web UI", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(configs_router)
app.include_router(references_router)
app.include_router(jobs_router)
app.include_router(datasets_router)


@app.get("/api/health")
def health():
    return {"status": "ok"}
