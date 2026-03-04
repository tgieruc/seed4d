# SEED4D Web UI — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a web UI (FastAPI + React) to configure, supervise, and visualize SEED4D data generation.

**Architecture:** Monorepo under `webui/` with `backend/` (FastAPI, SQLite, SQLAlchemy) and `frontend/` (React, Vite, TypeScript, react-three-fiber). Backend imports Pydantic models from `common/config.py`. Jobs run `generator.py` as subprocesses with WebSocket progress streaming.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite, React 18, Vite, TypeScript, Tailwind CSS, react-three-fiber, Zustand (state), TanStack Query (data fetching)

**Design doc:** `docs/plans/2026-03-04-webui-design.md`

---

## Milestone 1: Project Scaffolding & Backend Foundation

### Task 1: Initialize backend project structure

**Files:**
- Create: `webui/backend/__init__.py`
- Create: `webui/backend/main.py`
- Create: `webui/backend/database.py`
- Create: `webui/backend/models.py`
- Create: `webui/backend/requirements.txt`
- Create: `webui/__init__.py`

**Step 1: Create directory structure**

```bash
mkdir -p webui/backend/api webui/backend/services
touch webui/__init__.py webui/backend/__init__.py webui/backend/api/__init__.py webui/backend/services/__init__.py
```

**Step 2: Write `webui/backend/requirements.txt`**

```
fastapi>=0.115.0
uvicorn[standard]>=0.34.0
sqlalchemy>=2.0
aiosqlite>=0.20.0
pydantic>=2.0
pyyaml>=6.0
python-multipart>=0.0.9
```

**Step 3: Write `webui/backend/database.py`**

```python
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "webui.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

**Step 4: Write `webui/backend/models.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from webui.backend.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConfigRecord(Base):
    __tablename__ = "configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    yaml_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class JobRecord(Base):
    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    config_id: Mapped[str] = mapped_column(String(36))
    config_name: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="queued")
    progress: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    log: Mapped[str] = mapped_column(Text, default="")
    pid: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_path: Mapped[str | None] = mapped_column(Text, nullable=True)


class CameraRigRecord(Base):
    __tablename__ = "camera_rigs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(255))
    json_content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
```

**Step 5: Write `webui/backend/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from webui.backend.database import Base, engine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="SEED4D Web UI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

**Step 6: Test it starts**

```bash
cd webui/backend && python -m uvicorn webui.backend.main:app --reload --port 8000
# Visit http://localhost:8000/api/health → {"status": "ok"}
# Ctrl+C to stop
```

**Step 7: Commit**

```bash
git add webui/
git commit -m "feat(webui): scaffold backend with FastAPI, SQLAlchemy, SQLite models"
```

---

### Task 2: Config CRUD API

**Files:**
- Create: `webui/backend/api/configs.py`
- Modify: `webui/backend/main.py` (add router)
- Create: `tests/webui/test_configs_api.py`

**Step 1: Write the failing test**

```python
# tests/webui/test_configs_api.py
import pytest
from fastapi.testclient import TestClient

from webui.backend.main import app
from webui.backend.database import Base, engine

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

client = TestClient(app)

SAMPLE_YAML = """
map: Town01
vehicle: vehicle.mini.cooper_s
weather: ClearNoon
spawn_point: [1]
steps: 5
min_distance: 0.0
number_of_vehicles: 5
number_of_walkers: 0
carla:
  host: localhost
  port: 2000
  synchronous_mode: true
  fixed_delta_seconds: 0.1
  timeout: 40.0
dataset:
  nuscenes:
    attached_to_vehicle: true
    sensor_info:
      type:
        - sensor.camera.rgb
      fov: 90
      width: 1600
      height: 900
    transform_file_cams: camera/nuscenes/nuscenes_adjusted.json
""".strip()


def test_create_config():
    resp = client.post("/api/configs", json={"name": "test", "yaml_content": SAMPLE_YAML})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "test"
    assert "id" in data


def test_list_configs():
    client.post("/api/configs", json={"name": "a", "yaml_content": SAMPLE_YAML})
    client.post("/api/configs", json={"name": "b", "yaml_content": SAMPLE_YAML})
    resp = client.get("/api/configs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_config():
    create = client.post("/api/configs", json={"name": "test", "yaml_content": SAMPLE_YAML})
    config_id = create.json()["id"]
    resp = client.get(f"/api/configs/{config_id}")
    assert resp.status_code == 200
    assert resp.json()["name"] == "test"


def test_update_config():
    create = client.post("/api/configs", json={"name": "old", "yaml_content": SAMPLE_YAML})
    config_id = create.json()["id"]
    resp = client.put(f"/api/configs/{config_id}", json={"name": "new", "yaml_content": SAMPLE_YAML})
    assert resp.status_code == 200
    assert resp.json()["name"] == "new"


def test_delete_config():
    create = client.post("/api/configs", json={"name": "test", "yaml_content": SAMPLE_YAML})
    config_id = create.json()["id"]
    resp = client.delete(f"/api/configs/{config_id}")
    assert resp.status_code == 204
    resp = client.get(f"/api/configs/{config_id}")
    assert resp.status_code == 404


def test_validate_config():
    create = client.post("/api/configs", json={"name": "test", "yaml_content": SAMPLE_YAML})
    config_id = create.json()["id"]
    resp = client.post(f"/api/configs/{config_id}/validate")
    assert resp.status_code == 200
    assert resp.json()["valid"] is True


def test_validate_invalid_config():
    bad_yaml = "map: Town01\nvehicle: car\n"
    create = client.post("/api/configs", json={"name": "bad", "yaml_content": bad_yaml})
    config_id = create.json()["id"]
    resp = client.post(f"/api/configs/{config_id}/validate")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert len(resp.json()["errors"]) > 0
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/webui/test_configs_api.py -v
```

Expected: FAIL (no module `webui.backend.api.configs`, no routes)

**Step 3: Write `webui/backend/api/configs.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

import yaml

from common.config import ScenarioConfig
from webui.backend.database import get_db
from webui.backend.models import ConfigRecord

router = APIRouter(prefix="/api/configs", tags=["configs"])


class ConfigCreate(BaseModel):
    name: str
    yaml_content: str


class ConfigResponse(BaseModel):
    id: str
    name: str
    yaml_content: str
    created_at: str
    updated_at: str


@router.get("", response_model=list[ConfigResponse])
def list_configs(db: Session = Depends(get_db)):
    records = db.query(ConfigRecord).order_by(ConfigRecord.updated_at.desc()).all()
    return [_to_response(r) for r in records]


@router.post("", response_model=ConfigResponse, status_code=201)
def create_config(body: ConfigCreate, db: Session = Depends(get_db)):
    record = ConfigRecord(name=body.name, yaml_content=body.yaml_content)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.get("/{config_id}", response_model=ConfigResponse)
def get_config(config_id: str, db: Session = Depends(get_db)):
    record = db.get(ConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    return _to_response(record)


@router.put("/{config_id}", response_model=ConfigResponse)
def update_config(config_id: str, body: ConfigCreate, db: Session = Depends(get_db)):
    record = db.get(ConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    record.name = body.name
    record.yaml_content = body.yaml_content
    db.commit()
    db.refresh(record)
    return _to_response(record)


@router.delete("/{config_id}", status_code=204)
def delete_config(config_id: str, db: Session = Depends(get_db)):
    record = db.get(ConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(record)
    db.commit()


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = []


@router.post("/{config_id}/validate", response_model=ValidateResponse)
def validate_config(config_id: str, db: Session = Depends(get_db)):
    record = db.get(ConfigRecord, config_id)
    if not record:
        raise HTTPException(status_code=404, detail="Config not found")
    try:
        raw = yaml.safe_load(record.yaml_content)
        ScenarioConfig(**raw)
        return ValidateResponse(valid=True)
    except Exception as e:
        return ValidateResponse(valid=False, errors=[str(e)])


def _to_response(record: ConfigRecord) -> ConfigResponse:
    return ConfigResponse(
        id=record.id,
        name=record.name,
        yaml_content=record.yaml_content,
        created_at=record.created_at.isoformat(),
        updated_at=record.updated_at.isoformat(),
    )
```

**Step 4: Register router in `webui/backend/main.py`**

Add after CORS middleware:

```python
from webui.backend.api.configs import router as configs_router

app.include_router(configs_router)
```

**Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/webui/test_configs_api.py -v
```

Expected: All 7 tests PASS

**Step 6: Commit**

```bash
git add webui/backend/api/configs.py tests/webui/
git commit -m "feat(webui): add config CRUD API with validation"
```

---

### Task 3: Reference data endpoints (maps, vehicles, weathers)

**Files:**
- Create: `webui/backend/api/references.py`
- Modify: `webui/backend/main.py` (add router)
- Create: `tests/webui/test_references_api.py`

**Step 1: Write the failing test**

```python
# tests/webui/test_references_api.py
from fastapi.testclient import TestClient
from webui.backend.main import app

client = TestClient(app)


def test_list_maps():
    resp = client.get("/api/maps")
    assert resp.status_code == 200
    maps = resp.json()
    assert "Town01" in maps
    assert len(maps) >= 7


def test_list_weathers():
    resp = client.get("/api/weathers")
    assert resp.status_code == 200
    weathers = resp.json()
    assert "ClearNoon" in weathers
    assert len(weathers) == 14


def test_list_vehicles():
    resp = client.get("/api/vehicles")
    assert resp.status_code == 200
    vehicles = resp.json()
    assert len(vehicles) > 0
    assert any("mini" in v.lower() for v in vehicles)


def test_list_camera_rigs():
    resp = client.get("/api/camera-rigs")
    assert resp.status_code == 200
    rigs = resp.json()
    assert len(rigs) > 0
    assert any(r["name"] == "nuscenes" for r in rigs)
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/webui/test_references_api.py -v
```

**Step 3: Write `webui/backend/api/references.py`**

```python
import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["references"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

MAPS = [
    "Town01", "Town02", "Town03", "Town04", "Town05",
    "Town06", "Town07", "Town10HD", "Town12", "Town15",
]

WEATHERS = [
    "ClearNoon", "CloudyNoon", "WetNoon", "WetCloudyNoon",
    "MidRainyNoon", "HardRainNoon", "SoftRainNoon",
    "ClearSunset", "CloudySunset", "WetSunset", "WetCloudySunset",
    "MidRainSunset", "HardRainSunset", "SoftRainSunset",
]

# Common CARLA 0.9.16 vehicle blueprints
VEHICLES = [
    "vehicle.audi.a2", "vehicle.audi.etron", "vehicle.audi.tt",
    "vehicle.bmw.grandtourer", "vehicle.chevrolet.impala",
    "vehicle.citroen.c3", "vehicle.dodge.charger_2020",
    "vehicle.dodge.charger_police", "vehicle.ford.mustang",
    "vehicle.jeep.wrangler_rubicon", "vehicle.lincoln.mkz_2017",
    "vehicle.lincoln.mkz_2020", "vehicle.mercedes.coupe",
    "vehicle.mercedes.coupe_2020", "vehicle.micro.microlino",
    "vehicle.mini.cooper_s", "vehicle.mini.cooper_s_2021",
    "vehicle.nissan.micra", "vehicle.nissan.patrol",
    "vehicle.nissan.patrol_2021", "vehicle.seat.leon",
    "vehicle.tesla.model3", "vehicle.toyota.prius",
    "vehicle.volkswagen.t2", "vehicle.volkswagen.t2_2021",
]


@router.get("/api/maps")
def list_maps() -> list[str]:
    return MAPS


@router.get("/api/weathers")
def list_weathers() -> list[str]:
    return WEATHERS


@router.get("/api/vehicles")
def list_vehicles() -> list[str]:
    return VEHICLES


@router.get("/api/camera-rigs")
def list_camera_rigs() -> list[dict]:
    rigs = []
    camera_dir = CONFIG_DIR / "camera"
    if not camera_dir.exists():
        return rigs
    for rig_dir in sorted(camera_dir.iterdir()):
        if not rig_dir.is_dir():
            continue
        for json_file in sorted(rig_dir.glob("*.json")):
            with open(json_file) as f:
                content = json.load(f)
            num_cameras = len(content.get("coordinates", []))
            rigs.append({
                "name": rig_dir.name,
                "file": str(json_file.relative_to(CONFIG_DIR)),
                "filename": json_file.name,
                "num_cameras": num_cameras,
                "content": content,
            })
    return rigs
```

**Step 4: Register router in `webui/backend/main.py`**

```python
from webui.backend.api.references import router as references_router

app.include_router(references_router)
```

**Step 5: Run tests**

```bash
python3 -m pytest tests/webui/test_references_api.py -v
```

Expected: All PASS

**Step 6: Commit**

```bash
git add webui/backend/api/references.py tests/webui/test_references_api.py
git commit -m "feat(webui): add reference data endpoints (maps, weathers, vehicles, camera rigs)"
```

---

### Task 4: Job submission and management API

**Files:**
- Create: `webui/backend/api/jobs.py`
- Create: `webui/backend/services/job_runner.py`
- Create: `tests/webui/test_jobs_api.py`
- Modify: `webui/backend/main.py` (add router)

**Step 1: Write the failing test**

```python
# tests/webui/test_jobs_api.py
import pytest
from fastapi.testclient import TestClient

from webui.backend.main import app
from webui.backend.database import Base, engine

SAMPLE_YAML = """
map: Town01
vehicle: vehicle.mini.cooper_s
weather: ClearNoon
spawn_point: [1]
steps: 1
min_distance: 0.0
number_of_vehicles: 0
number_of_walkers: 0
carla:
  host: localhost
  port: 2000
  synchronous_mode: true
  fixed_delta_seconds: 0.1
  timeout: 40.0
dataset:
  nuscenes:
    attached_to_vehicle: true
    sensor_info:
      type: [sensor.camera.rgb]
      fov: 90
      width: 800
      height: 600
    transform_file_cams: camera/nuscenes/nuscenes_adjusted.json
""".strip()


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


client = TestClient(app)


def _create_config():
    resp = client.post("/api/configs", json={"name": "test", "yaml_content": SAMPLE_YAML})
    return resp.json()["id"]


def test_submit_job():
    config_id = _create_config()
    resp = client.post("/api/jobs", json={"config_id": config_id})
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "queued"
    assert data["config_id"] == config_id


def test_list_jobs():
    config_id = _create_config()
    client.post("/api/jobs", json={"config_id": config_id})
    client.post("/api/jobs", json={"config_id": config_id})
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_job():
    config_id = _create_config()
    create = client.post("/api/jobs", json={"config_id": config_id})
    job_id = create.json()["id"]
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == job_id


def test_list_jobs_filter_status():
    config_id = _create_config()
    client.post("/api/jobs", json={"config_id": config_id})
    resp = client.get("/api/jobs?status=queued")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    resp = client.get("/api/jobs?status=running")
    assert len(resp.json()) == 0
```

**Step 2: Run test to verify it fails**

```bash
python3 -m pytest tests/webui/test_jobs_api.py -v
```

**Step 3: Write `webui/backend/services/job_runner.py`**

```python
import asyncio
import logging
import os
import signal
import subprocess
import tempfile
from datetime import datetime, timezone
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
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, dir=str(PROJECT_ROOT / "config")
        ) as f:
            f.write(yaml_content)
            config_path = f.name

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()
        await _broadcast(job_id, {"type": "status", "status": "running"})

        cmd = [
            "python3", str(PROJECT_ROOT / "generator.py"),
            "--config", config_path,
            "--data_dir", str(PROJECT_ROOT / data_dir),
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

        job.completed_at = datetime.now(timezone.utc)
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
            job.completed_at = datetime.now(timezone.utc)
            db.commit()
        await _broadcast(job_id, {"type": "status", "status": "failed", "error": str(e)})
    finally:
        db.close()


def cancel_job(job_id: str, db: Session):
    job = db.get(JobRecord, job_id)
    if not job:
        return False
    if job.pid:
        try:
            os.kill(job.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    job.status = "cancelled"
    job.completed_at = datetime.now(timezone.utc)
    job.pid = None
    db.commit()
    return True
```

**Step 4: Write `webui/backend/api/jobs.py`**

```python
import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.orm import Session

from webui.backend.database import get_db
from webui.backend.models import ConfigRecord, JobRecord
from webui.backend.services.job_runner import cancel_job, run_job, subscribe, unsubscribe

router = APIRouter(tags=["jobs"])


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
def submit_job(body: JobCreate, db: Session = Depends(get_db)):
    config = db.get(ConfigRecord, body.config_id)
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")
    job = JobRecord(config_id=config.id, config_name=config.name)
    db.add(job)
    db.commit()
    db.refresh(job)

    # Launch job in background
    asyncio.get_event_loop().create_task(run_job(job.id, config.yaml_content))

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
def rerun_job(job_id: str, db: Session = Depends(get_db)):
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
    asyncio.get_event_loop().create_task(run_job(new_job.id, config.yaml_content))
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
```

**Step 5: Register router in `webui/backend/main.py`**

```python
from webui.backend.api.jobs import router as jobs_router

app.include_router(jobs_router)
```

**Step 6: Run tests**

```bash
python3 -m pytest tests/webui/test_jobs_api.py -v
```

Expected: All PASS

**Step 7: Commit**

```bash
git add webui/backend/api/jobs.py webui/backend/services/job_runner.py tests/webui/test_jobs_api.py
git commit -m "feat(webui): add job submission, management API, and WebSocket streaming"
```

---

### Task 5: Dataset browser API

**Files:**
- Create: `webui/backend/api/datasets.py`
- Modify: `webui/backend/main.py`
- Create: `tests/webui/test_datasets_api.py`

**Step 1: Write the failing test**

```python
# tests/webui/test_datasets_api.py
import json
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from webui.backend.main import app

client = TestClient(app)


@pytest.fixture
def mock_data_dir(tmp_path, monkeypatch):
    """Create a fake data directory structure."""
    spawn = tmp_path / "Town01" / "ClearNoon" / "vehicle.mini.cooper_s" / "spawn_point_1" / "step_0"
    ego = spawn / "ego_vehicle" / "nuscenes"
    sensors = ego / "sensors"
    transforms = ego / "transforms"
    sensors.mkdir(parents=True)
    transforms.mkdir(parents=True)

    # Create a fake image
    (sensors / "0_rgb.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    # Create a fake transforms.json
    tf = {"camera_model": "OPENCV", "frames": [{"file_path": "../sensors/0_rgb.png"}]}
    (transforms / "transforms.json").write_text(json.dumps(tf))

    # Monkeypatch the DATA_DIR in datasets module
    import webui.backend.api.datasets as ds_mod
    monkeypatch.setattr(ds_mod, "DATA_DIR", tmp_path)
    return tmp_path


def test_list_datasets(mock_data_dir):
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    tree = resp.json()
    assert len(tree) > 0


def test_get_transforms(mock_data_dir):
    resp = client.get(
        "/api/datasets/Town01/ClearNoon/vehicle.mini.cooper_s/spawn_point_1/step_0/ego_vehicle/nuscenes/transforms"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["camera_model"] == "OPENCV"
```

**Step 2: Run test to verify fails**

```bash
python3 -m pytest tests/webui/test_datasets_api.py -v
```

**Step 3: Write `webui/backend/api/datasets.py`**

```python
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"


@router.get("")
def list_datasets():
    """Return tree of generated datasets."""
    if not DATA_DIR.exists():
        return []

    tree = []
    for map_dir in sorted(DATA_DIR.iterdir()):
        if not map_dir.is_dir() or map_dir.name.startswith(".") or map_dir.name == "failed_configs":
            continue
        map_node = {"name": map_dir.name, "type": "map", "children": []}
        for weather_dir in sorted(map_dir.iterdir()):
            if not weather_dir.is_dir():
                continue
            weather_node = {"name": weather_dir.name, "type": "weather", "children": []}
            for vehicle_dir in sorted(weather_dir.iterdir()):
                if not vehicle_dir.is_dir():
                    continue
                vehicle_node = {"name": vehicle_dir.name, "type": "vehicle", "children": []}
                for spawn_dir in sorted(vehicle_dir.iterdir()):
                    if not spawn_dir.is_dir():
                        continue
                    steps = sorted([d.name for d in spawn_dir.iterdir() if d.is_dir() and d.name.startswith("step_")])
                    vehicle_node["children"].append({
                        "name": spawn_dir.name,
                        "type": "spawn_point",
                        "steps": steps,
                        "path": str(spawn_dir.relative_to(DATA_DIR)),
                    })
                if vehicle_node["children"]:
                    weather_node["children"].append(vehicle_node)
            if weather_node["children"]:
                map_node["children"].append(weather_node)
        if map_node["children"]:
            tree.append(map_node)
    return tree


@router.get("/{path:path}/transforms")
def get_transforms(path: str):
    transforms_file = DATA_DIR / path / "transforms" / "transforms.json"
    if not transforms_file.exists():
        raise HTTPException(status_code=404, detail="transforms.json not found")
    with open(transforms_file) as f:
        return json.load(f)


@router.get("/{path:path}/images/{filename}")
def get_image(path: str, filename: str):
    image_path = DATA_DIR / path / "sensors" / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path)


@router.get("/{path:path}/bev")
def get_bev(path: str):
    """Serve BEV GIF."""
    bev_path = DATA_DIR / path / "BEV_ego.gif"
    if not bev_path.exists():
        raise HTTPException(status_code=404, detail="BEV GIF not found")
    return FileResponse(bev_path, media_type="image/gif")


@router.get("/{path:path}/pointcloud/{filename}")
def get_pointcloud(path: str, filename: str):
    ply_path = DATA_DIR / path / "sensors" / filename
    if not ply_path.exists():
        raise HTTPException(status_code=404, detail="Point cloud not found")
    return FileResponse(ply_path, media_type="application/octet-stream")
```

**Step 4: Register router in `webui/backend/main.py`**

```python
from webui.backend.api.datasets import router as datasets_router

app.include_router(datasets_router)
```

**Step 5: Run tests**

```bash
python3 -m pytest tests/webui/test_datasets_api.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add webui/backend/api/datasets.py tests/webui/test_datasets_api.py
git commit -m "feat(webui): add dataset browser API with file serving"
```

---

## Milestone 2: Frontend Scaffolding & Config Builder

### Task 6: Initialize React + Vite + TypeScript project

**Files:**
- Create: `webui/frontend/` (entire Vite scaffold)
- Create: `webui/frontend/src/App.tsx`
- Create: `webui/frontend/src/main.tsx`

**Step 1: Scaffold Vite project**

```bash
cd webui && npm create vite@latest frontend -- --template react-ts
cd frontend && npm install
```

**Step 2: Install dependencies**

```bash
cd webui/frontend
npm install react-router-dom @tanstack/react-query zustand
npm install -D tailwindcss @tailwindcss/vite
```

**Step 3: Configure Tailwind**

Add to `webui/frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
})
```

Replace `webui/frontend/src/index.css` with:

```css
@import "tailwindcss";
```

**Step 4: Write `webui/frontend/src/App.tsx`**

```tsx
import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

function Layout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <nav className="border-b border-gray-800 px-6 py-3 flex gap-6 items-center">
        <span className="font-bold text-lg tracking-tight">SEED4D</span>
        <NavLink to="/config" className={({ isActive }) =>
          isActive ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'
        }>Config Builder</NavLink>
        <NavLink to="/jobs" className={({ isActive }) =>
          isActive ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'
        }>Jobs</NavLink>
        <NavLink to="/viewer" className={({ isActive }) =>
          isActive ? 'text-blue-400' : 'text-gray-400 hover:text-gray-200'
        }>Data Viewer</NavLink>
      </nav>
      <main className="p-6">{children}</main>
    </div>
  )
}

function ConfigBuilder() {
  return <div><h1 className="text-2xl font-bold">Config Builder</h1><p className="text-gray-400 mt-2">Coming soon...</p></div>
}

function JobMonitor() {
  return <div><h1 className="text-2xl font-bold">Job Monitor</h1><p className="text-gray-400 mt-2">Coming soon...</p></div>
}

function DataViewer() {
  return <div><h1 className="text-2xl font-bold">Data Viewer</h1><p className="text-gray-400 mt-2">Coming soon...</p></div>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<ConfigBuilder />} />
            <Route path="/config" element={<ConfigBuilder />} />
            <Route path="/jobs" element={<JobMonitor />} />
            <Route path="/viewer" element={<DataViewer />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

**Step 5: Verify dev server starts**

```bash
cd webui/frontend && npm run dev
# Visit http://localhost:5173 — should see nav bar with 3 links
# Ctrl+C to stop
```

**Step 6: Commit**

```bash
git add webui/frontend/
git commit -m "feat(webui): scaffold React frontend with Vite, Tailwind, routing"
```

---

### Task 7: API client and shared types

**Files:**
- Create: `webui/frontend/src/api.ts`
- Create: `webui/frontend/src/types.ts`

**Step 1: Write `webui/frontend/src/types.ts`**

```typescript
export interface Config {
  id: string
  name: string
  yaml_content: string
  created_at: string
  updated_at: string
}

export interface Job {
  id: string
  config_id: string
  config_name: string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: { spawn_point?: number; step?: number; total_spawn_points?: number; total_steps?: number } | null
  log: string
  created_at: string
  started_at: string | null
  completed_at: string | null
  error: string | null
  data_path: string | null
}

export interface CameraRig {
  name: string
  file: string
  filename: string
  num_cameras: number
  content: {
    coordinates: number[][]
    pitchs: number[]
    yaws: number[]
    fov?: number[]
  }
}

export interface DatasetNode {
  name: string
  type: 'map' | 'weather' | 'vehicle' | 'spawn_point'
  children?: DatasetNode[]
  steps?: string[]
  path?: string
}
```

**Step 2: Write `webui/frontend/src/api.ts`**

```typescript
import type { Config, Job, CameraRig, DatasetNode } from './types'

const BASE = ''

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + url, init)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

// Configs
export const listConfigs = () => fetchJSON<Config[]>('/api/configs')
export const getConfig = (id: string) => fetchJSON<Config>(`/api/configs/${id}`)
export const createConfig = (name: string, yaml_content: string) =>
  fetchJSON<Config>('/api/configs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, yaml_content }),
  })
export const updateConfig = (id: string, name: string, yaml_content: string) =>
  fetchJSON<Config>(`/api/configs/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, yaml_content }),
  })
export const deleteConfig = (id: string) =>
  fetch(`/api/configs/${id}`, { method: 'DELETE' })
export const validateConfig = (id: string) =>
  fetchJSON<{ valid: boolean; errors: string[] }>(`/api/configs/${id}/validate`, { method: 'POST' })

// References
export const listMaps = () => fetchJSON<string[]>('/api/maps')
export const listWeathers = () => fetchJSON<string[]>('/api/weathers')
export const listVehicles = () => fetchJSON<string[]>('/api/vehicles')
export const listCameraRigs = () => fetchJSON<CameraRig[]>('/api/camera-rigs')

// Jobs
export const listJobs = (status?: string) =>
  fetchJSON<Job[]>(`/api/jobs${status ? `?status=${status}` : ''}`)
export const getJob = (id: string) => fetchJSON<Job>(`/api/jobs/${id}`)
export const submitJob = (config_id: string) =>
  fetchJSON<Job>('/api/jobs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ config_id }),
  })
export const cancelJob = (id: string) =>
  fetch(`/api/jobs/${id}/cancel`, { method: 'POST' })
export const rerunJob = (id: string) =>
  fetchJSON<Job>(`/api/jobs/${id}/rerun`, { method: 'POST' })

// Datasets
export const listDatasets = () => fetchJSON<DatasetNode[]>('/api/datasets')
export const getTransforms = (path: string) =>
  fetchJSON<Record<string, unknown>>(`/api/datasets/${path}/transforms`)

// WebSocket
export function connectJobWS(jobId: string, onMessage: (msg: Record<string, unknown>) => void): WebSocket {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
  const ws = new WebSocket(`${proto}://${window.location.host}/ws/jobs/${jobId}`)
  ws.onmessage = (e) => onMessage(JSON.parse(e.data))
  return ws
}
```

**Step 3: Commit**

```bash
git add webui/frontend/src/api.ts webui/frontend/src/types.ts
git commit -m "feat(webui): add API client and TypeScript types"
```

---

### Task 8: Config Builder page — form sections

**Files:**
- Create: `webui/frontend/src/pages/ConfigBuilder.tsx`
- Create: `webui/frontend/src/store/configStore.ts`
- Modify: `webui/frontend/src/App.tsx` (import ConfigBuilder)

This is the largest frontend task. The form has sections for World, Spawn Points, Simulation, Traffic, Sensor Datasets, Options, Post-processing, and Actions.

**Step 1: Write `webui/frontend/src/store/configStore.ts`**

```typescript
import { create } from 'zustand'

export interface SensorDataset {
  name: string
  attached_to_vehicle: boolean
  sensor_types: string[]
  fov: number
  width: number
  height: number
  camera_rig_file: string
  // LiDAR fields
  channels?: number
  points_per_second?: number
  rotation_frequency?: number
  range?: number
}

export interface ConfigFormState {
  // World
  map: string
  weather: string
  vehicle: string
  // Spawn
  spawn_points: number[]
  // Simulation
  steps: number
  min_distance: number
  synchronous_mode: boolean
  fixed_delta_seconds: number
  timeout: number
  // Traffic
  number_of_vehicles: number
  number_of_walkers: number
  large_vehicles: boolean
  sort_spawnpoints: boolean
  // Sensors
  datasets: SensorDataset[]
  // Options
  bev_camera: boolean
  invisible_ego: boolean
  three_d_boundingbox: boolean
  // Post-processing
  normalize_coords: boolean
  vehicle_masks: boolean
  combine_transforms: boolean
  generate_map: boolean
}

interface ConfigStore extends ConfigFormState {
  set: <K extends keyof ConfigFormState>(key: K, value: ConfigFormState[K]) => void
  setDataset: (index: number, dataset: SensorDataset) => void
  addDataset: () => void
  removeDataset: (index: number) => void
  toYAML: () => string
  reset: () => void
  loadFromYAML: (yaml: string) => void
}

const DEFAULT_DATASET: SensorDataset = {
  name: 'nuscenes',
  attached_to_vehicle: true,
  sensor_types: ['sensor.camera.rgb'],
  fov: 90,
  width: 1600,
  height: 900,
  camera_rig_file: 'camera/nuscenes/nuscenes_adjusted.json',
}

const DEFAULTS: ConfigFormState = {
  map: 'Town01',
  weather: 'ClearNoon',
  vehicle: 'vehicle.mini.cooper_s',
  spawn_points: [1],
  steps: 5,
  min_distance: 0.0,
  synchronous_mode: true,
  fixed_delta_seconds: 0.1,
  timeout: 720.0,
  number_of_vehicles: 5,
  number_of_walkers: 0,
  large_vehicles: false,
  sort_spawnpoints: false,
  datasets: [{ ...DEFAULT_DATASET }],
  bev_camera: true,
  invisible_ego: false,
  three_d_boundingbox: true,
  normalize_coords: true,
  vehicle_masks: true,
  combine_transforms: true,
  generate_map: true,
}

export const useConfigStore = create<ConfigStore>((set, get) => ({
  ...DEFAULTS,

  set: (key, value) => set({ [key]: value }),

  setDataset: (index, dataset) =>
    set((s) => {
      const datasets = [...s.datasets]
      datasets[index] = dataset
      return { datasets }
    }),

  addDataset: () =>
    set((s) => ({ datasets: [...s.datasets, { ...DEFAULT_DATASET, name: `dataset_${s.datasets.length}` }] })),

  removeDataset: (index) =>
    set((s) => ({ datasets: s.datasets.filter((_, i) => i !== index) })),

  toYAML: () => {
    const s = get()
    const dataset: Record<string, unknown> = {}
    for (const ds of s.datasets) {
      const sensor_info: Record<string, unknown> = {
        type: ds.sensor_types,
        fov: ds.fov,
        width: ds.width,
        height: ds.height,
      }
      dataset[ds.name] = {
        attached_to_vehicle: ds.attached_to_vehicle,
        sensor_info,
        transform_file_cams: ds.camera_rig_file,
      }
    }
    const config: Record<string, unknown> = {
      map: s.map,
      vehicle: s.vehicle,
      weather: s.weather,
      spawn_point: s.spawn_points,
      steps: s.steps,
      min_distance: s.min_distance,
      number_of_vehicles: s.number_of_vehicles,
      number_of_walkers: s.number_of_walkers,
      large_vehicles: s.large_vehicles,
      sort_spawnpoints: s.sort_spawnpoints,
      BEVCamera: s.bev_camera,
      invisible_ego: s.invisible_ego,
      '3Dboundingbox': s.three_d_boundingbox,
      data_dir: 'data',
      carla: {
        host: 'localhost',
        port: 2000,
        synchronous_mode: s.synchronous_mode,
        fixed_delta_seconds: s.fixed_delta_seconds,
        timeout: s.timeout,
      },
      dataset,
    }
    // Simple YAML serialization (use js-yaml in production)
    return JSON.stringify(config, null, 2)
  },

  reset: () => set(DEFAULTS),

  loadFromYAML: (_yaml: string) => {
    // TODO: parse YAML and populate form
  },
}))
```

NOTE: The `toYAML()` initially outputs JSON. In Task 8 Step 2, install `js-yaml` and use proper YAML serialization.

**Step 2: Install js-yaml**

```bash
cd webui/frontend && npm install js-yaml && npm install -D @types/js-yaml
```

Then update `toYAML()` to use `import yaml from 'js-yaml'` and `yaml.dump(config)`.

**Step 3: Write `webui/frontend/src/pages/ConfigBuilder.tsx`**

This is a large file. Key structure:

```tsx
import { useQuery } from '@tanstack/react-query'
import { useConfigStore } from '../store/configStore'
import { listMaps, listWeathers, listVehicles, listCameraRigs, createConfig, submitJob } from '../api'

// Section components (defined in same file initially, extract later if needed)
function WorldSection() { /* Map, Weather, Vehicle dropdowns */ }
function SpawnPointsSection() { /* Multi-select number inputs */ }
function SimulationSection() { /* Steps, min_distance, delta_seconds */ }
function TrafficSection() { /* Sliders for vehicles/walkers, toggles */ }
function SensorDatasetsSection() { /* Add/remove datasets, each with type checkboxes, resolution, FOV, rig picker */ }
function OptionsSection() { /* BEV, invisible, 3D bbox toggles */ }
function PostProcessingSection() { /* Normalize, masks, combine, map checkboxes */ }
function ActionsSection() { /* Save, Save & Run buttons */ }

export default function ConfigBuilder() {
  return (
    <div className="flex gap-6 h-[calc(100vh-5rem)]">
      <div className="flex-1 overflow-y-auto space-y-6 pr-4">
        <h1 className="text-2xl font-bold">Config Builder</h1>
        <WorldSection />
        <SpawnPointsSection />
        <SimulationSection />
        <TrafficSection />
        <SensorDatasetsSection />
        <OptionsSection />
        <PostProcessingSection />
        <ActionsSection />
      </div>
      <div className="w-[500px] border border-gray-800 rounded-lg bg-gray-900">
        {/* 3D Preview — Task 9 */}
        <div className="flex items-center justify-center h-full text-gray-500">
          3D Preview (coming next)
        </div>
      </div>
    </div>
  )
}
```

Each section component reads from `useConfigStore` and renders form controls with Tailwind styling. The full implementation of each section should follow standard React form patterns with controlled inputs.

**Step 4: Update `App.tsx` to use ConfigBuilder**

Replace the placeholder `ConfigBuilder` function with:

```tsx
import ConfigBuilder from './pages/ConfigBuilder'
```

And update the route.

**Step 5: Verify the form renders**

```bash
cd webui/frontend && npm run dev
# Visit http://localhost:5173/config — form should render with all sections
```

**Step 6: Commit**

```bash
git add webui/frontend/src/
git commit -m "feat(webui): implement Config Builder form with all sections"
```

---

### Task 9: 3D Scene Preview (react-three-fiber)

**Files:**
- Create: `webui/frontend/src/components/ScenePreview.tsx`
- Modify: `webui/frontend/src/pages/ConfigBuilder.tsx` (embed preview)

**Step 1: Install three.js dependencies**

```bash
cd webui/frontend
npm install three @react-three/fiber @react-three/drei
npm install -D @types/three
```

**Step 2: Write `webui/frontend/src/components/ScenePreview.tsx`**

```tsx
import { Canvas } from '@react-three/fiber'
import { OrbitControls, Grid } from '@react-three/drei'
import * as THREE from 'three'
import { useConfigStore } from '../store/configStore'
import { useQuery } from '@tanstack/react-query'
import { listCameraRigs } from '../api'

function CarModel() {
  // Simple box representing a car (2.0 x 1.5 x 4.5 meters)
  return (
    <mesh position={[0, 0.75, 0]}>
      <boxGeometry args={[2.0, 1.5, 4.5]} />
      <meshStandardMaterial color="#3b82f6" transparent opacity={0.6} />
    </mesh>
  )
}

interface CameraFrustumProps {
  position: [number, number, number]
  pitch: number
  yaw: number
  fov: number
  color: string
  label: string
}

function CameraFrustum({ position, pitch, yaw, fov, color, label }: CameraFrustumProps) {
  const length = 1.5
  const halfFov = (fov * Math.PI) / 360
  const halfW = Math.tan(halfFov) * length
  const halfH = halfW * 0.75

  const points = [
    new THREE.Vector3(0, 0, 0),
    new THREE.Vector3(-halfW, -halfH, length),
    new THREE.Vector3(halfW, -halfH, length),
    new THREE.Vector3(halfW, halfH, length),
    new THREE.Vector3(-halfW, halfH, length),
  ]

  const edges = [
    [0, 1], [0, 2], [0, 3], [0, 4],
    [1, 2], [2, 3], [3, 4], [4, 1],
  ]

  return (
    <group position={position} rotation={[pitch, yaw, 0]}>
      {edges.map(([a, b], i) => {
        const geom = new THREE.BufferGeometry().setFromPoints([points[a], points[b]])
        return <lineSegments key={i} geometry={geom}>
          <lineBasicMaterial color={color} />
        </lineSegments>
      })}
    </group>
  )
}

function CameraRigDisplay() {
  const datasets = useConfigStore((s) => s.datasets)
  const { data: rigs } = useQuery({ queryKey: ['camera-rigs'], queryFn: listCameraRigs })

  if (!rigs) return null

  const colors = ['#ef4444', '#22c55e', '#3b82f6', '#f59e0b', '#a855f7', '#06b6d4']

  return (
    <>
      {datasets.map((ds, di) => {
        const rig = rigs.find((r) => ds.camera_rig_file.includes(r.file))
        if (!rig) return null
        return rig.content.coordinates.map((coord, ci) => (
          <CameraFrustum
            key={`${di}-${ci}`}
            position={[coord[0], coord[2], coord[1]]}
            pitch={rig.content.pitchs[ci]}
            yaw={rig.content.yaws[ci]}
            fov={rig.content.fov?.[ci] ?? ds.fov}
            color={colors[di % colors.length]}
            label={`${ds.name}_${ci}`}
          />
        ))
      })}
    </>
  )
}

export default function ScenePreview() {
  return (
    <Canvas camera={{ position: [8, 6, 8], fov: 50 }}>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <Grid
        args={[50, 50]}
        cellSize={1}
        cellColor="#1e293b"
        sectionSize={5}
        sectionColor="#334155"
        fadeDistance={50}
        position={[0, 0, 0]}
      />
      <CarModel />
      <CameraRigDisplay />
      <OrbitControls />
      <axesHelper args={[3]} />
    </Canvas>
  )
}
```

**Step 3: Embed in ConfigBuilder**

Replace the "3D Preview (coming next)" placeholder with `<ScenePreview />`.

**Step 4: Verify 3D preview renders**

```bash
cd webui/frontend && npm run dev
# Visit http://localhost:5173/config — should see 3D car with camera frustums
```

**Step 5: Commit**

```bash
git add webui/frontend/src/components/ScenePreview.tsx
git commit -m "feat(webui): add 3D scene preview with camera frustums and car model"
```

---

## Milestone 3: Job Monitor Page

### Task 10: Job Monitor page — job list and detail

**Files:**
- Create: `webui/frontend/src/pages/JobMonitor.tsx`
- Modify: `webui/frontend/src/App.tsx` (import)

**Step 1: Write `webui/frontend/src/pages/JobMonitor.tsx`**

Key structure:

```tsx
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useState, useEffect, useRef } from 'react'
import { listJobs, cancelJob, rerunJob, connectJobWS } from '../api'
import type { Job } from '../types'

const STATUS_COLORS = {
  queued: 'bg-yellow-500',
  running: 'bg-blue-500 animate-pulse',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
  cancelled: 'bg-gray-500',
}

function JobList({ jobs, selectedId, onSelect }: { ... }) {
  // Filterable table of jobs
  // Columns: status dot, config name, map, created, duration
  // Click row to select
}

function JobDetail({ job }: { job: Job }) {
  // Header with status badge
  // Progress bar
  // Live log (WebSocket streaming)
  // Actions: Cancel, Re-run, Open in Viewer
  const [logLines, setLogLines] = useState<string[]>([])
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (job.status !== 'running') {
      setLogLines(job.log.split('\n').filter(Boolean))
      return
    }
    const ws = connectJobWS(job.id, (msg) => {
      if (msg.type === 'log') setLogLines((prev) => [...prev, msg.line as string])
    })
    return () => ws.close()
  }, [job.id, job.status])

  // Auto-scroll log
  useEffect(() => {
    logRef.current?.scrollTo(0, logRef.current.scrollHeight)
  }, [logLines])

  return (
    <div className="space-y-4">
      {/* Header, progress bar, log viewer, actions */}
    </div>
  )
}

export default function JobMonitor() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const { data: jobs = [] } = useQuery({
    queryKey: ['jobs'],
    queryFn: () => listJobs(),
    refetchInterval: 3000,
  })
  const selected = jobs.find((j) => j.id === selectedId)

  return (
    <div className="flex gap-6 h-[calc(100vh-5rem)]">
      <div className="flex-1 overflow-y-auto">
        <h1 className="text-2xl font-bold mb-4">Job Monitor</h1>
        <JobList jobs={jobs} selectedId={selectedId} onSelect={setSelectedId} />
      </div>
      <div className="w-[600px] border border-gray-800 rounded-lg bg-gray-900 p-4 overflow-y-auto">
        {selected ? <JobDetail job={selected} /> : (
          <p className="text-gray-500 text-center mt-20">Select a job to view details</p>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Update App.tsx**

Import and use `JobMonitor` component in the route.

**Step 3: Verify page renders**

```bash
cd webui/frontend && npm run dev
# Visit http://localhost:5173/jobs
```

**Step 4: Commit**

```bash
git add webui/frontend/src/pages/JobMonitor.tsx
git commit -m "feat(webui): implement Job Monitor page with WebSocket log streaming"
```

---

## Milestone 4: Data Viewer Page

### Task 11: Data Viewer page — dataset browser + image gallery

**Files:**
- Create: `webui/frontend/src/pages/DataViewer.tsx`
- Modify: `webui/frontend/src/App.tsx`

**Step 1: Write `webui/frontend/src/pages/DataViewer.tsx`**

```tsx
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { listDatasets, getTransforms } from '../api'
import type { DatasetNode } from '../types'

function DatasetTree({ nodes, onSelect }: { nodes: DatasetNode[]; onSelect: (path: string) => void }) {
  // Recursive collapsible tree
  // Each spawn_point node is clickable → selects it
}

function ImageGallery({ path, step }: { path: string; step: string }) {
  const { data: transforms } = useQuery({
    queryKey: ['transforms', path, step],
    queryFn: () => getTransforms(`${path}/${step}/ego_vehicle/nuscenes`),
  })

  if (!transforms) return <p>Loading...</p>

  const frames = (transforms as any).frames || []
  return (
    <div className="grid grid-cols-3 gap-4">
      {frames.map((frame: any, i: number) => {
        const filename = frame.file_path.split('/').pop()
        return (
          <div key={i} className="border border-gray-700 rounded overflow-hidden">
            <img
              src={`/api/datasets/${path}/${step}/ego_vehicle/nuscenes/images/${filename}`}
              alt={`Camera ${i}`}
              className="w-full"
            />
            <p className="text-xs text-gray-400 p-1">Camera {i}</p>
          </div>
        )
      })}
    </div>
  )
}

export default function DataViewer() {
  const { data: datasets = [] } = useQuery({ queryKey: ['datasets'], queryFn: listDatasets })
  const [selectedPath, setSelectedPath] = useState<string | null>(null)
  const [selectedStep, setSelectedStep] = useState<string>('step_0')
  const [activeTab, setActiveTab] = useState<'gallery' | '3d' | 'bev'>('gallery')

  return (
    <div className="flex gap-6 h-[calc(100vh-5rem)]">
      <div className="w-64 overflow-y-auto border-r border-gray-800 pr-4">
        <h2 className="text-lg font-bold mb-3">Datasets</h2>
        <DatasetTree nodes={datasets} onSelect={setSelectedPath} />
      </div>
      <div className="flex-1">
        <div className="flex gap-2 mb-4 border-b border-gray-800 pb-2">
          {['gallery', '3d', 'bev'].map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab as any)}
              className={`px-3 py-1 rounded ${activeTab === tab ? 'bg-blue-600' : 'bg-gray-800'}`}
            >
              {tab === 'gallery' ? 'Image Gallery' : tab === '3d' ? '3D Viewer' : 'BEV'}
            </button>
          ))}
        </div>
        {selectedPath ? (
          <>
            {activeTab === 'gallery' && <ImageGallery path={selectedPath} step={selectedStep} />}
            {activeTab === '3d' && <p className="text-gray-500">3D Viewer — Task 12</p>}
            {activeTab === 'bev' && (
              <img src={`/api/datasets/${selectedPath}/bev`} alt="BEV" className="max-w-lg" />
            )}
          </>
        ) : (
          <p className="text-gray-500 mt-10">Select a dataset from the sidebar</p>
        )}
      </div>
    </div>
  )
}
```

**Step 2: Update App.tsx, verify, commit**

```bash
git add webui/frontend/src/pages/DataViewer.tsx
git commit -m "feat(webui): implement Data Viewer with dataset tree and image gallery"
```

---

### Task 12: 3D Viewer tab (transforms + point cloud)

**Files:**
- Create: `webui/frontend/src/components/DataViewer3D.tsx`
- Modify: `webui/frontend/src/pages/DataViewer.tsx` (embed)

**Step 1: Write `webui/frontend/src/components/DataViewer3D.tsx`**

```tsx
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { useQuery } from '@tanstack/react-query'
import { getTransforms } from '../api'

function TransformFrustums({ path, step }: { path: string; step: string }) {
  const { data } = useQuery({
    queryKey: ['transforms-3d', path, step],
    queryFn: () => getTransforms(`${path}/${step}/ego_vehicle/nuscenes`),
  })

  if (!data) return null

  const frames = (data as any).frames || []
  return (
    <>
      {frames.map((frame: any, i: number) => {
        const m = frame.transform_matrix
        if (!m) return null
        const mat = new THREE.Matrix4()
        mat.set(
          m[0][0], m[0][1], m[0][2], m[0][3],
          m[1][0], m[1][1], m[1][2], m[1][3],
          m[2][0], m[2][1], m[2][2], m[2][3],
          m[3][0], m[3][1], m[3][2], m[3][3],
        )
        const pos = new THREE.Vector3()
        pos.setFromMatrixPosition(mat)

        return (
          <mesh key={i} position={pos}>
            <sphereGeometry args={[0.3]} />
            <meshStandardMaterial color="#ef4444" />
          </mesh>
        )
      })}
    </>
  )
}

export default function DataViewer3D({ path, step }: { path: string; step: string }) {
  return (
    <div className="h-[600px] border border-gray-700 rounded-lg overflow-hidden">
      <Canvas camera={{ position: [20, 15, 20], fov: 50 }}>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} />
        <gridHelper args={[100, 100, '#1e293b', '#334155']} />
        <TransformFrustums path={path} step={step} />
        <OrbitControls />
        <axesHelper args={[5]} />
      </Canvas>
    </div>
  )
}
```

**Step 2: Embed in DataViewer, verify, commit**

```bash
git add webui/frontend/src/components/DataViewer3D.tsx
git commit -m "feat(webui): add 3D viewer for camera transforms visualization"
```

---

## Milestone 5: Polish & Integration

### Task 13: End-to-end integration test

**Files:**
- Create: `tests/webui/test_integration.py`

Write an integration test that:
1. Creates a config via API
2. Validates it
3. Lists configs
4. Submits a job (won't actually run CARLA, but tests the flow)
5. Lists jobs and checks status

```bash
python3 -m pytest tests/webui/test_integration.py -v
```

**Commit:**

```bash
git commit -m "test(webui): add end-to-end integration test"
```

---

### Task 14: Dev startup script

**Files:**
- Create: `webui/dev.sh`

```bash
#!/bin/bash
# Start both backend and frontend for development
echo "Starting SEED4D Web UI..."

# Start backend
cd "$(dirname "$0")"
echo "Starting backend on :8000..."
(cd .. && python -m uvicorn webui.backend.main:app --reload --port 8000) &
BACKEND_PID=$!

# Start frontend
echo "Starting frontend on :5173..."
(cd frontend && npm run dev) &
FRONTEND_PID=$!

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "API docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both servers"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
```

```bash
chmod +x webui/dev.sh
git add webui/dev.sh
git commit -m "feat(webui): add dev startup script"
```

---

## Summary

| Milestone | Tasks | What you get |
|-----------|-------|-------------|
| 1. Backend Foundation | Tasks 1-5 | Full REST API + WebSocket, SQLite DB, all endpoints working |
| 2. Frontend + Config Builder | Tasks 6-9 | React app with config form, 3D camera preview, YAML generation |
| 3. Job Monitor | Task 10 | Job list, detail panel, live log streaming |
| 4. Data Viewer | Tasks 11-12 | Dataset tree, image gallery, 3D transform viewer, BEV playback |
| 5. Polish | Tasks 13-14 | Integration tests, dev script |

**Total: 14 tasks, ~5 milestones**

Each milestone produces a working, testable increment. You can start using the tool after Milestone 2 (config building) and progressively add monitoring and visualization.
