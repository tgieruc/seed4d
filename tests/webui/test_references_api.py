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
