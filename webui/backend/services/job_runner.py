import asyncio
import contextlib
import logging
import os
import signal
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from webui.backend.database import SessionLocal
from webui.backend.models import JobRecord

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# In-memory store for active WebSocket connections per job
_job_subscribers: dict[str, list[asyncio.Queue]] = {}


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
    """Run generator.py as subprocess, stream output via WebSocket."""
    db = SessionLocal()
    try:
        job = db.get(JobRecord, job_id)
        if not job:
            return

        # Write YAML to temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, dir=str(PROJECT_ROOT / "config")) as f:
            f.write(yaml_content)
            config_path = f.name

        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()
        await _broadcast(job_id, {"type": "status", "status": "running"})

        cmd = [
            "python3",
            str(PROJECT_ROOT / "generator.py"),
            "--config",
            config_path,
            "--data_dir",
            str(PROJECT_ROOT / data_dir),
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        job.pid = process.pid
        db.commit()

        log_lines = []
        while True:
            line = await asyncio.get_event_loop().run_in_executor(None, process.stdout.readline)
            if not line and process.poll() is not None:
                break
            if line:
                log_lines.append(line)
                await _broadcast(job_id, {"type": "log", "line": line.rstrip()})

        job.log = "".join(log_lines)
        job.pid = None

        if process.returncode == 0:
            job.status = "completed"
        else:
            job.status = "failed"
            job.error = f"Process exited with code {process.returncode}"

        job.completed_at = datetime.now(UTC)
        db.commit()
        await _broadcast(job_id, {"type": "status", "status": job.status})

        # Clean up temp config
        os.unlink(config_path)

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
        db.close()


def cancel_job(job_id: str, db: Session):
    job = db.get(JobRecord, job_id)
    if not job:
        return False
    if job.pid:
        with contextlib.suppress(ProcessLookupError):
            os.kill(job.pid, signal.SIGTERM)
    job.status = "cancelled"
    job.completed_at = datetime.now(UTC)
    job.pid = None
    db.commit()
    return True
