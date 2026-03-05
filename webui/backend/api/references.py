import json
from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["references"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

MAPS = [
    "Town01",
    "Town02",
    "Town03",
    "Town04",
    "Town05",
    "Town06",
    "Town07",
    "Town10HD",
    "Town12",
    "Town15",
]

WEATHERS = [
    "ClearNoon",
    "CloudyNoon",
    "WetNoon",
    "WetCloudyNoon",
    "MidRainyNoon",
    "HardRainNoon",
    "SoftRainNoon",
    "ClearSunset",
    "CloudySunset",
    "WetSunset",
    "WetCloudySunset",
    "MidRainSunset",
    "HardRainSunset",
    "SoftRainSunset",
]

# Common CARLA 0.9.16 vehicle blueprints
VEHICLES = [
    "vehicle.audi.a2",
    "vehicle.audi.etron",
    "vehicle.audi.tt",
    "vehicle.bmw.grandtourer",
    "vehicle.chevrolet.impala",
    "vehicle.citroen.c3",
    "vehicle.dodge.charger_2020",
    "vehicle.dodge.charger_police",
    "vehicle.ford.mustang",
    "vehicle.jeep.wrangler_rubicon",
    "vehicle.lincoln.mkz_2017",
    "vehicle.lincoln.mkz_2020",
    "vehicle.mercedes.coupe",
    "vehicle.mercedes.coupe_2020",
    "vehicle.micro.microlino",
    "vehicle.mini.cooper_s",
    "vehicle.mini.cooper_s_2021",
    "vehicle.nissan.micra",
    "vehicle.nissan.patrol",
    "vehicle.nissan.patrol_2021",
    "vehicle.seat.leon",
    "vehicle.tesla.model3",
    "vehicle.toyota.prius",
    "vehicle.volkswagen.t2",
    "vehicle.volkswagen.t2_2021",
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


@router.get("/api/configs/filesystem")
def list_filesystem_configs() -> list[dict]:
    """List existing YAML config files from the config/ directory."""
    configs = []
    if not CONFIG_DIR.exists():
        return configs
    for yaml_file in sorted(CONFIG_DIR.glob("*.yaml")):
        with open(yaml_file) as f:
            content = f.read()
        configs.append(
            {
                "name": yaml_file.stem,
                "filename": yaml_file.name,
                "path": str(yaml_file.relative_to(PROJECT_ROOT)),
                "content": content,
            }
        )
    # Also scan subdirectories (e.g., config/dynamic/)
    for subdir in sorted(CONFIG_DIR.iterdir()):
        if not subdir.is_dir() or subdir.name in ("camera", "lidar"):
            continue
        for yaml_file in sorted(subdir.glob("*.yaml")):
            with open(yaml_file) as f:
                content = f.read()
            configs.append(
                {
                    "name": f"{subdir.name}/{yaml_file.stem}",
                    "filename": yaml_file.name,
                    "path": str(yaml_file.relative_to(PROJECT_ROOT)),
                    "content": content,
                }
            )
    return configs


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
            rigs.append(
                {
                    "name": rig_dir.name,
                    "file": str(json_file.relative_to(CONFIG_DIR)),
                    "filename": json_file.name,
                    "num_cameras": num_cameras,
                    "content": content,
                }
            )
    return rigs
