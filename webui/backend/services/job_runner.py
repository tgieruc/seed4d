import asyncio
import contextlib
import logging
import os
import signal
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from webui.backend.database import SessionLocal
from webui.backend.models import JobRecord

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# In-memory store for active WebSocket connections per job
_job_subscribers: dict[str, list[asyncio.Queue]] = {}

# Track running job IDs so we can clean up on shutdown
_active_job_ids: set[str] = set()


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


def _detect_docker_container() -> str | None:
    """Find a running Docker container suitable for SEED4D jobs.

    Checks for containers from the ``seed4d`` or ``carlasim/carla`` images,
    then falls back to a container literally named ``carla``.
    """
    # Check for seed4d image first (has Python deps + project code)
    for image in ("seed4d", "carlasim/carla:0.9.16", "carlasim/carla"):
        try:
            result = subprocess.run(
                ["docker", "ps", "--filter", f"ancestor={image}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            names = [n for n in result.stdout.strip().split("\n") if n]
            if names:
                return names[0]
        except Exception:
            pass
    # Fallback: check for container named "carla" or "seed4d"
    for name in ("carla", "seed4d"):
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format", "{{.State.Running}}", name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.stdout.strip() == "true":
                return name
        except Exception:
            pass
    return None


async def run_job(job_id: str, yaml_content: str, data_dir: str = "data"):
    """Run generator.py as subprocess, stream output via WebSocket.

    If a running Docker container is detected, runs inside it via
    ``docker exec``.  Otherwise falls back to running on the host.
    """
    db = SessionLocal()
    config_path = None
    try:
        job = db.get(JobRecord, job_id)
        if not job:
            return

        # Write YAML to a stable file based on job ID (mounted into Docker at /seed4d/config/)
        loop = asyncio.get_running_loop()
        config_path = str(PROJECT_ROOT / "config" / f"_job_{job_id}.yaml")
        Path(config_path).write_text(yaml_content)

        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()
        _active_job_ids.add(job_id)
        await _broadcast(job_id, {"type": "status", "status": "running"})

        # Run Docker detection in a thread to avoid blocking the event loop
        container = await loop.run_in_executor(None, _detect_docker_container)
        logger.info("Job %s: container=%s", job_id, container)

        # Log file on the mounted volume — readable from both host and container
        log_file = PROJECT_ROOT / "config" / f"_job_{job_id}.log"
        log_file.write_text("")

        if container:
            # Run inside the Docker container.
            # The project dir is volume-mounted at /seed4d (see docs/datasets.md).
            container_config = "/seed4d/config/" + Path(config_path).name
            container_data = "/seed4d/" + data_dir
            container_log = "/seed4d/config/" + log_file.name
            # Use bash to redirect output to a log file on the mounted volume
            inner_cmd = (
                f"PYTHONUNBUFFERED=1 python3 -u /seed4d/generator.py"
                f" --config {container_config}"
                f" --data_dir {container_data}"
                f" --carla_executable /workspace/CarlaUE4.sh"
                f" > {container_log} 2>&1"
            )
            cmd = ["docker", "exec", container, "bash", "-c", inner_cmd]
        else:
            logger.warning("No Docker container found — running generator.py on host")
            cmd = [
                "bash",
                "-c",
                f"PYTHONUNBUFFERED=1 python3 -u {PROJECT_ROOT / 'generator.py'}"
                f" --config {config_path}"
                f" --data_dir {PROJECT_ROOT / data_dir}"
                f" > {log_file} 2>&1",
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
        prev_size = 0
        while process.returncode is None:
            # Read any new content from the log file
            try:
                content = log_file.read_text()
            except OSError:
                content = ""
            if len(content) > prev_size:
                new_text = content[prev_size:]
                prev_size = len(content)
                # Broadcast new lines to WebSocket subscribers
                for line in new_text.splitlines():
                    if line:
                        await _broadcast(job_id, {"type": "log", "line": line})
                # Update DB so API polling also sees logs
                job.log = content
                db.commit()
            # Check if process finished; if not, sleep briefly
            if process.returncode is None:
                await asyncio.sleep(1)
                # Poll the process
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(process.wait(), timeout=0.1)

        # Final read of the log file
        try:
            final_log = log_file.read_text()
        except OSError:
            final_log = job.log or ""

        job.log = final_log
        job.pid = None

        if process.returncode == 0:
            job.status = "completed"
            # Try to extract data_path from the config
            job.data_path = data_dir
        else:
            job.status = "failed"
            job.error = f"Process exited with code {process.returncode}"

        job.completed_at = datetime.now(UTC)
        db.commit()
        await _broadcast(job_id, {"type": "status", "status": job.status})

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
        # Clean up config + log files only when job finished (not on server reload)
        if config_path and job and job.status in ("completed", "failed", "cancelled"):
            with contextlib.suppress(OSError):
                os.unlink(config_path)
            with contextlib.suppress(OSError):
                os.unlink(str(PROJECT_ROOT / "config" / f"_job_{job_id}.log"))
        db.close()


def mark_active_jobs_failed():
    """Mark any in-memory active jobs as failed. Called on shutdown."""
    if not _active_job_ids:
        return
    db = SessionLocal()
    for jid in list(_active_job_ids):
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
    """Remove leftover _job_*.yaml config files from completed/failed jobs."""
    config_dir = PROJECT_ROOT / "config"
    for f in config_dir.glob("_job_*"):
        with contextlib.suppress(OSError):
            f.unlink()


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
