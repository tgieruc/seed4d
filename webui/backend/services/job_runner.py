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

        # Write YAML to temp file inside config/ (mounted into Docker at /seed4d/config/)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, dir=str(PROJECT_ROOT / "config")) as f:
            f.write(yaml_content)
            config_path = f.name

        job.status = "running"
        job.started_at = datetime.now(UTC)
        db.commit()
        await _broadcast(job_id, {"type": "status", "status": "running"})

        container = _detect_docker_container()
        logger.info("Job %s: container=%s", job_id, container)

        if container:
            # Run inside the Docker container.
            # The project dir is volume-mounted at /seed4d (see docs/datasets.md).
            container_config = "/seed4d/config/" + Path(config_path).name
            container_data = "/seed4d/" + data_dir
            cmd = [
                "docker",
                "exec",
                container,
                "python3",
                "/seed4d/generator.py",
                "--config",
                container_config,
                "--data_dir",
                container_data,
                "--carla_executable",
                "/workspace/CarlaUE4.sh",
            ]
        else:
            logger.warning("No Docker container found — running generator.py on host")
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

        log_lines: list[str] = []
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, process.stdout.readline)
            if not line and process.poll() is not None:
                break
            if line:
                log_lines.append(line)
                await _broadcast(job_id, {"type": "log", "line": line.rstrip()})

        job.log = "".join(log_lines)
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
        # Clean up temp config
        if config_path:
            with contextlib.suppress(OSError):
                os.unlink(config_path)
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
