import pytest
from fastapi.testclient import TestClient

from webui.backend.database import Base, engine
from webui.backend.main import app


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
