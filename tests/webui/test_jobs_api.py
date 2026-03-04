import pytest
from fastapi.testclient import TestClient

from webui.backend.database import Base, engine
from webui.backend.main import app

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
