import json

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
