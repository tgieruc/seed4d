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
                    vehicle_node["children"].append(
                        {
                            "name": spawn_dir.name,
                            "type": "spawn_point",
                            "steps": steps,
                            "path": str(spawn_dir.relative_to(DATA_DIR)),
                        }
                    )
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
