import asyncio
import contextlib
import logging
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from webui.backend.database import SessionLocal
from webui.backend.models import JobRecord

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOCKER_IMAGE = os.environ.get("SEED4D_IMAGE", "seed4d")

# One job at a time by default. Raise to allow parallel jobs (needs unique CARLA ports).
_job_semaphore = asyncio.Semaphore(1)

# In-memory store for active WebSocket connections per job
_job_subscribers: dict[str, list[asyncio.Queue]] = {}

# Track running job IDs so we can clean up on shutdown
_active_job_ids: set[str] = set()


def _container_name(job_id: str) -> str:
    return f"job-{job_id}"


def subscribe(job_id: str) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue()
    _job_subscribers.setdefault(job_id, []).append(queue)
    return queue


def unsubscribe(job_id: str, queue: asyncio.Queue):
    if job_id in _job_subscribers:
        _job_subscribers[job_id] = [q for q in _job_subscribers[job_id] if q is not queue]


async def _broadcast(job_id: str, message: dict):
    for queue in _job_subscribers.get(job_id, []):
        await queue.put(message)


async def run_job(job_id: str, yaml_content: str, data_dir: str = "data"):
    """Run generator.py in a fresh Docker container, stream output via WebSocket.

    Jobs are serialized by ``_job_semaphore`` (default: 1 at a time).
    Each job gets its own container named ``job-{job_id}``.
    On success the container is removed; on failure it is kept for inspection.
    """
    async with _job_semaphore:
        # Re-fetch status: job may have been cancelled while waiting in the queue
        db = SessionLocal()
        job = db.get(JobRecord, job_id)
        db.close()
        if not job or job.status == "cancelled":
            return
        await _run_job_inner(job_id, yaml_content, data_dir)


async def _run_job_inner(job_id: str, yaml_content: str, data_dir: str):
    db = SessionLocal()
    config_path = None
    success = False
    container = _container_name(job_id)
    job = None
    try:
        job = db.get(JobRecord, job_id)
        if not job:
            return

        # Write config to a stable path on the mounted volume
        config_path = str(PROJECT_ROOT / "config" / f"_job_{job_id}.yaml")
        Path(config_path).write_text(yaml_content)

        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()
        _active_job_ids.add(job_id)
        await _broadcast(job_id, {"type": "status", "status": "running"})

        # Log file on the mounted volume — readable from both host and container
        log_file = PROJECT_ROOT / "config" / f"_job_{job_id}.log"
        log_file.write_text("")

        container_config = f"/seed4d/config/_job_{job_id}.yaml"
        container_data = f"/seed4d/{data_dir}"
        container_log = f"/seed4d/config/_job_{job_id}.log"

        inner_cmd = (
            f"PYTHONUNBUFFERED=1 python3 -u /seed4d/generator.py"
            f" --config {container_config}"
            f" --data_dir {container_data}"
            f" --carla_executable /workspace/CarlaUE4.sh"
            f" > {container_log} 2>&1"
        )

        cmd = [
            "docker",
            "run",
            "--name",
            container,
            "--gpus",
            "all",
            "--shm-size=20g",
            "-v",
            f"{PROJECT_ROOT}:/seed4d",
            "-v",
            "/tmp/.X11-unix:/tmp/.X11-unix:rw",
            "-v",
            "/usr/share/vulkan/icd.d:/usr/share/vulkan/icd.d",
            DOCKER_IMAGE,
            "bash",
            "-c",
            inner_cmd,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            cwd=str(PROJECT_ROOT),
        )
        job.pid = process.pid
        db.commit()

        # Tail the log file, streaming lines to WebSocket subscribers
        wait_task = asyncio.create_task(process.wait())
        prev_size = 0
        while not wait_task.done():
            try:
                content = log_file.read_text()
            except OSError:
                content = ""
            if len(content) > prev_size:
                new_text = content[prev_size:]
                prev_size = len(content)
                for line in new_text.splitlines():
                    if line:
                        await _broadcast(job_id, {"type": "log", "line": line})
                job.log = content
                db.commit()
            await asyncio.sleep(2)

        # Final read of the log file
        try:
            final_log = log_file.read_text()
        except OSError:
            final_log = job.log or ""

        job.log = final_log
        job.pid = None

        # Re-read status: cancel_job may have set it to "cancelled" while we were running
        db.refresh(job)
        if job.status == "cancelled":
            await _broadcast(job_id, {"type": "status", "status": "cancelled"})
        elif process.returncode == 0:
            job.status = "completed"
            job.data_path = data_dir
            job.completed_at = datetime.now(UTC)
            db.commit()
            success = True
            await _broadcast(job_id, {"type": "status", "status": "completed"})
        else:
            job.status = "failed"
            job.error = f"Process exited with code {process.returncode}"
            job.completed_at = datetime.now(UTC)
            db.commit()
            await _broadcast(job_id, {"type": "status", "status": "failed"})

    except Exception as e:
        logger.exception("Job %s failed", job_id)
        job = db.get(JobRecord, job_id)
        if job:
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.now(UTC)
            db.commit()
        await _broadcast(job_id, {"type": "status", "status": "failed", "error": str(e)})
    finally:
        _active_job_ids.discard(job_id)
        # Remove container on success; leave it on failure/cancel for inspection
        if success:
            _remove_container(container)
        # Clean up config + log files
        if config_path and job and job.status in ("completed", "failed", "cancelled"):
            with contextlib.suppress(OSError):
                os.unlink(config_path)
            with contextlib.suppress(OSError):
                os.unlink(str(PROJECT_ROOT / "config" / f"_job_{job_id}.log"))
        db.close()


def _remove_container(container: str):
    with contextlib.suppress(Exception):
        subprocess.run(["docker", "rm", container], capture_output=True, timeout=10)


def _stop_container(container: str):
    with contextlib.suppress(Exception):
        subprocess.run(["docker", "stop", container], capture_output=True, timeout=15)


def mark_active_jobs_failed():
    """Mark any in-memory active jobs as failed and stop their containers. Called on shutdown."""
    if not _active_job_ids:
        return
    db = SessionLocal()
    for jid in list(_active_job_ids):
        _stop_container(_container_name(jid))
        job = db.get(JobRecord, jid)
        if job and job.status == "running":
            job.status = "failed"
            job.error = "Server restarted — job was interrupted. Please re-run."
            job.completed_at = datetime.now(UTC)
            job.pid = None
    db.commit()
    db.close()
    _active_job_ids.clear()


def cleanup_stale_configs():
    """Remove leftover _job_*.yaml and _job_*.log config files from completed/failed jobs."""
    config_dir = PROJECT_ROOT / "config"
    for f in config_dir.glob("_job_*"):
        with contextlib.suppress(OSError):
            f.unlink()


def cancel_job(job_id: str, db: Session):
    job = db.get(JobRecord, job_id)
    if not job:
        return False
    # Stop the container — this cleanly terminates generator.py and CARLA inside it
    _stop_container(_container_name(job_id))
    job.status = "cancelled"
    job.completed_at = datetime.now(UTC)
    job.pid = None
    db.commit()
    return True
