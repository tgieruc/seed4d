"""End-to-end integration test for the SEED4D Web UI API.

Tests the full workflow: create config → validate → list → submit job → list jobs.
"""

import pytest
from fastapi.testclient import TestClient

from webui.backend.database import Base, engine
from webui.backend.main import app

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


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


client = TestClient(app)


def test_full_workflow():
    """Test complete flow: create config → validate → list → submit job → check job."""
    # 1. Create a config
    resp = client.post("/api/configs", json={"name": "integration-test", "yaml_content": SAMPLE_YAML})
    assert resp.status_code == 201
    config = resp.json()
    config_id = config["id"]
    assert config["name"] == "integration-test"

    # 2. Validate the config
    resp = client.post(f"/api/configs/{config_id}/validate")
    assert resp.status_code == 200
    validation = resp.json()
    assert validation["valid"] is True
    assert validation["errors"] == []

    # 3. List configs — should contain our config
    resp = client.get("/api/configs")
    assert resp.status_code == 200
    configs = resp.json()
    assert len(configs) >= 1
    assert any(c["id"] == config_id for c in configs)

    # 4. Submit a job (won't actually run CARLA, but tests the API flow)
    resp = client.post("/api/jobs", json={"config_id": config_id})
    assert resp.status_code == 201
    job = resp.json()
    job_id = job["id"]
    assert job["status"] == "queued"
    assert job["config_id"] == config_id
    assert job["config_name"] == "integration-test"

    # 5. List jobs and verify our job is there
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    jobs = resp.json()
    assert len(jobs) >= 1
    assert any(j["id"] == job_id for j in jobs)

    # 6. Get specific job and verify details
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 200
    job_detail = resp.json()
    assert job_detail["id"] == job_id
    assert job_detail["config_id"] == config_id

    # 7. Filter jobs by status
    resp = client.get("/api/jobs?status=queued")
    assert resp.status_code == 200
    queued = resp.json()
    assert any(j["id"] == job_id for j in queued)


def test_workflow_with_update_and_rerun():
    """Test config update and job rerun flow."""
    # Create and submit initial job
    resp = client.post("/api/configs", json={"name": "original", "yaml_content": SAMPLE_YAML})
    config_id = resp.json()["id"]
    resp = client.post("/api/jobs", json={"config_id": config_id})
    job_id = resp.json()["id"]

    # Update the config name
    resp = client.put(f"/api/configs/{config_id}", json={"name": "updated", "yaml_content": SAMPLE_YAML})
    assert resp.status_code == 200
    assert resp.json()["name"] == "updated"

    # Rerun the job
    resp = client.post(f"/api/jobs/{job_id}/rerun")
    assert resp.status_code == 201
    new_job = resp.json()
    assert new_job["id"] != job_id
    assert new_job["config_id"] == config_id
    assert new_job["status"] == "queued"


def test_invalid_config_workflow():
    """Test that invalid configs are caught by validation."""
    bad_yaml = "map: Town01\nvehicle: car\n"
    resp = client.post("/api/configs", json={"name": "bad-config", "yaml_content": bad_yaml})
    assert resp.status_code == 201
    config_id = resp.json()["id"]

    # Validation should fail
    resp = client.post(f"/api/configs/{config_id}/validate")
    assert resp.status_code == 200
    assert resp.json()["valid"] is False
    assert len(resp.json()["errors"]) > 0


def test_nonexistent_config_job():
    """Test submitting a job with a nonexistent config returns 404."""
    resp = client.post("/api/jobs", json={"config_id": "nonexistent-id"})
    assert resp.status_code == 404


def test_health_endpoint():
    """Test the health check endpoint."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
