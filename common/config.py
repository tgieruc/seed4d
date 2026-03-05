"""Pydantic models for validating YAML scenario configs and JSON camera/lidar configs."""

import json
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


# ---------------------------------------------------------------------------
# Camera / LiDAR JSON config models
# ---------------------------------------------------------------------------
class CameraConfig(BaseModel):
    """Camera rig JSON config: coordinates, pitchs, yaws, optional fov/width/height."""

    coordinates: list[list[float]]
    pitchs: list[float]
    yaws: list[float]
    fov: list[float] | None = None
    width: list[int] | None = None
    height: list[int] | None = None

    @model_validator(mode="after")
    def _arrays_same_length(self):
        n = len(self.coordinates)
        if len(self.pitchs) != n:
            raise ValueError(f"pitchs length {len(self.pitchs)} != coordinates length {n}")
        if len(self.yaws) != n:
            raise ValueError(f"yaws length {len(self.yaws)} != coordinates length {n}")
        if self.fov is not None and len(self.fov) != n:
            raise ValueError(f"fov length {len(self.fov)} != coordinates length {n}")
        if self.width is not None and len(self.width) != n:
            raise ValueError(f"width length {len(self.width)} != coordinates length {n}")
        if self.height is not None and len(self.height) != n:
            raise ValueError(f"height length {len(self.height)} != coordinates length {n}")
        return self

    @model_validator(mode="after")
    def _coordinates_are_3d(self):
        for i, coord in enumerate(self.coordinates):
            if len(coord) != 3:
                raise ValueError(f"coordinate[{i}] has {len(coord)} elements, expected 3")
        return self


class LidarConfig(BaseModel):
    """LiDAR rig JSON config: coordinates, pitchs, yaws."""

    coordinates: list[list[float]]
    pitchs: list[float]
    yaws: list[float]

    @model_validator(mode="after")
    def _arrays_same_length(self):
        n = len(self.coordinates)
        if len(self.pitchs) != n:
            raise ValueError(f"pitchs length {len(self.pitchs)} != coordinates length {n}")
        if len(self.yaws) != n:
            raise ValueError(f"yaws length {len(self.yaws)} != coordinates length {n}")
        return self

    @model_validator(mode="after")
    def _coordinates_are_3d(self):
        for i, coord in enumerate(self.coordinates):
            if len(coord) != 3:
                raise ValueError(f"coordinate[{i}] has {len(coord)} elements, expected 3")
        return self


# ---------------------------------------------------------------------------
# YAML scenario config models
# ---------------------------------------------------------------------------
class CarlaConfig(BaseModel):
    """CARLA connection settings."""

    host: str = "localhost"
    port: int = 2000
    synchronous_mode: bool = True
    fixed_delta_seconds: float = 0.1
    timeout: float = 40.0


class SensorInfo(BaseModel):
    """Sensor type list + camera/lidar fields."""

    model_config = ConfigDict(extra="allow")

    type: list[str]
    # Camera fields
    fov: float | None = None
    width: int | None = None
    height: int | None = None
    # LiDAR fields
    channels: int | None = None
    points_per_second: int | None = None
    rotation_frequency: int | None = None
    range: float | int | None = None

    @model_validator(mode="after")
    def _camera_fields_required(self):
        camera_types = {
            "sensor.camera.rgb",
            "sensor.camera.semantic_segmentation",
            "sensor.camera.instance_segmentation",
            "sensor.camera.depth",
            "sensor.camera.optical_flow",
        }
        has_camera = any(t in camera_types for t in self.type)
        if has_camera:
            missing = []
            if self.fov is None:
                missing.append("fov")
            if self.width is None:
                missing.append("width")
            if self.height is None:
                missing.append("height")
            if missing:
                raise ValueError(f"Camera types present but missing fields: {missing}")
        return self

    @model_validator(mode="after")
    def _lidar_fields_required(self):
        if "sensor.lidar.ray_cast" in self.type:
            missing = []
            if self.channels is None:
                missing.append("channels")
            if self.points_per_second is None:
                missing.append("points_per_second")
            if self.rotation_frequency is None:
                missing.append("rotation_frequency")
            if self.range is None:
                missing.append("range")
            if missing:
                raise ValueError(f"LiDAR type present but missing fields: {missing}")
        return self


class DatasetEntryConfig(BaseModel):
    """Single dataset setup (e.g. nuscenes, sphere)."""

    attached_to_vehicle: bool
    sensor_info: SensorInfo
    transform_file_cams: str | None = None
    transform_file_lidar: str | None = None


class TrafficVehiclesConfig(BaseModel):
    """Optional traffic vehicles block."""

    dataset: dict[str, DatasetEntryConfig]


class ScenarioConfig(BaseModel):
    """Top-level YAML scenario config. Validates all fields from existing configs."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    # Required fields
    map: str
    vehicle: str
    weather: str
    spawn_point: list[int]
    carla: CarlaConfig
    dataset: dict[str, DatasetEntryConfig]
    number_of_vehicles: int
    number_of_walkers: int
    steps: int
    min_distance: float

    # Optional fields with defaults
    data_dir: str = "data"
    BEVCamera: bool = False
    large_vehicles: bool = False
    invisible_ego: bool = False
    invisible_all: bool = False
    invisible_only: bool = False
    sort_spawnpoints: bool = False
    other_vehicles_have_sensors: bool = False

    # digit-prefixed key
    three_d_boundingbox: bool = Field(default=False, alias="3Dboundingbox")

    # Some configs use "invisible" instead of "invisible_ego"
    invisible: bool | None = None

    # Optional traffic vehicles
    traffic_vehicles: TrafficVehiclesConfig | None = None


# ---------------------------------------------------------------------------
# Helper functions: validate-then-dump
# ---------------------------------------------------------------------------
def load_scenario_config(path: str) -> dict[str, Any]:
    """Load a YAML scenario config, validate with Pydantic, return as dict."""
    with open(path) as f:
        raw = yaml.safe_load(f)
    validated = ScenarioConfig(**raw)
    return validated.model_dump(by_alias=True)


def load_camera_config(path: str) -> dict[str, Any]:
    """Load a camera JSON config, validate with Pydantic, return as dict."""
    with open(path) as f:
        raw = json.load(f)
    validated = CameraConfig(**raw)
    return validated.model_dump()


def load_lidar_config(path: str) -> dict[str, Any]:
    """Load a lidar JSON config, validate with Pydantic, return as dict."""
    with open(path) as f:
        raw = json.load(f)
    validated = LidarConfig(**raw)
    return validated.model_dump()
