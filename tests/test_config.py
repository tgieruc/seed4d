"""Tests for common/config.py Pydantic validation models."""

import glob
import os

import pytest
from pydantic import ValidationError

from common.config import (
    CameraConfig,
    LidarConfig,
    ScenarioConfig,
    load_camera_config,
    load_lidar_config,
    load_scenario_config,
)

CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "config")


# ---------------------------------------------------------------------------
# Validate all existing YAML configs
# ---------------------------------------------------------------------------
class TestExistingYamlConfigs:
    @pytest.fixture(params=sorted(glob.glob(os.path.join(CONFIG_DIR, "*.yaml"))))
    def yaml_path(self, request):
        return request.param

    def test_loads_successfully(self, yaml_path):
        result = load_scenario_config(yaml_path)
        assert isinstance(result, dict)
        assert "map" in result
        assert "vehicle" in result
        assert "weather" in result
        assert "dataset" in result


# ---------------------------------------------------------------------------
# Validate existing camera/lidar JSON configs
# ---------------------------------------------------------------------------
class TestExistingCameraConfigs:
    @pytest.fixture(
        params=[
            p
            for p in sorted(glob.glob(os.path.join(CONFIG_DIR, "camera", "**", "*.json"), recursive=True))
            if "original-calibration" not in p  # different format
        ]
    )
    def camera_json_path(self, request):
        return request.param

    def test_loads_successfully(self, camera_json_path):
        # waymo.json has a known fov/coordinates length mismatch
        if "waymo.json" in camera_json_path:
            with pytest.raises(Exception, match="fov length"):
                load_camera_config(camera_json_path)
        else:
            result = load_camera_config(camera_json_path)
            assert isinstance(result, dict)
            assert "coordinates" in result
            assert "pitchs" in result
            assert "yaws" in result


class TestExistingLidarConfigs:
    @pytest.fixture(params=sorted(glob.glob(os.path.join(CONFIG_DIR, "lidar", "**", "*.json"), recursive=True)))
    def lidar_json_path(self, request):
        return request.param

    def test_loads_successfully(self, lidar_json_path):
        result = load_lidar_config(lidar_json_path)
        assert isinstance(result, dict)
        assert "coordinates" in result


# ---------------------------------------------------------------------------
# Rejection of invalid configs
# ---------------------------------------------------------------------------
class TestInvalidConfigs:
    def test_missing_required_yaml_fields(self):
        with pytest.raises(ValidationError):
            ScenarioConfig(map="Town01")  # missing many required fields

    def test_mismatched_camera_array_lengths(self):
        with pytest.raises(Exception, match="pitchs length"):
            CameraConfig(
                coordinates=[[1, 2, 3], [4, 5, 6]],
                pitchs=[0.1],  # wrong length
                yaws=[0.2, 0.3],
            )

    def test_non_3d_coordinates(self):
        with pytest.raises(Exception, match="expected 3"):
            CameraConfig(
                coordinates=[[1, 2]],  # 2D, not 3D
                pitchs=[0.1],
                yaws=[0.2],
            )

    def test_mismatched_lidar_array_lengths(self):
        with pytest.raises(Exception, match="yaws length"):
            LidarConfig(
                coordinates=[[1, 2, 3]],
                pitchs=[0.1],
                yaws=[0.2, 0.3],  # wrong length
            )

    def test_camera_type_missing_fov(self):
        """Camera sensor type but no fov/width/height should fail."""
        minimal_yaml = {
            "map": "Town01",
            "vehicle": "vehicle.audi.tt",
            "weather": "ClearNoon",
            "spawn_point": [1],
            "carla": {"host": "localhost", "port": 2000},
            "number_of_vehicles": 0,
            "number_of_walkers": 0,
            "steps": 1,
            "min_distance": 0.0,
            "dataset": {
                "test": {
                    "attached_to_vehicle": True,
                    "sensor_info": {
                        "type": ["sensor.camera.rgb"],
                        # missing fov, width, height
                    },
                    "transform_file_cams": "dummy.json",
                }
            },
        }
        with pytest.raises(Exception, match="Camera types present but missing"):
            ScenarioConfig(**minimal_yaml)

    def test_lidar_type_missing_channels(self):
        """LiDAR sensor type but no lidar fields should fail."""
        minimal_yaml = {
            "map": "Town01",
            "vehicle": "vehicle.audi.tt",
            "weather": "ClearNoon",
            "spawn_point": [1],
            "carla": {"host": "localhost", "port": 2000},
            "number_of_vehicles": 0,
            "number_of_walkers": 0,
            "steps": 1,
            "min_distance": 0.0,
            "dataset": {
                "test": {
                    "attached_to_vehicle": True,
                    "sensor_info": {
                        "type": ["sensor.lidar.ray_cast"],
                        # missing channels, points_per_second, etc.
                    },
                    "transform_file_lidar": "dummy.json",
                }
            },
        }
        with pytest.raises(Exception, match="LiDAR type present but missing"):
            ScenarioConfig(**minimal_yaml)

    def test_valid_minimal_config(self):
        """A valid minimal config should pass."""
        minimal = {
            "map": "Town01",
            "vehicle": "vehicle.audi.tt",
            "weather": "ClearNoon",
            "spawn_point": [1],
            "carla": {},
            "number_of_vehicles": 0,
            "number_of_walkers": 0,
            "steps": 1,
            "min_distance": 0.0,
            "dataset": {
                "nuscenes": {
                    "attached_to_vehicle": True,
                    "sensor_info": {
                        "type": ["sensor.camera.rgb"],
                        "fov": 90,
                        "width": 800,
                        "height": 600,
                    },
                    "transform_file_cams": "camera/nuscenes/nuscenes.json",
                }
            },
        }
        config = ScenarioConfig(**minimal)
        assert config.map == "Town01"

    def test_3d_bounding_box_alias(self):
        """The '3Dboundingbox' alias should work."""
        minimal = {
            "map": "Town01",
            "vehicle": "vehicle.audi.tt",
            "weather": "ClearNoon",
            "spawn_point": [1],
            "carla": {},
            "number_of_vehicles": 0,
            "number_of_walkers": 0,
            "steps": 1,
            "min_distance": 0.0,
            "3Dboundingbox": True,
            "dataset": {
                "nuscenes": {
                    "attached_to_vehicle": True,
                    "sensor_info": {
                        "type": ["sensor.camera.rgb"],
                        "fov": 90,
                        "width": 800,
                        "height": 600,
                    },
                }
            },
        }
        config = ScenarioConfig(**minimal)
        assert config.three_d_boundingbox is True
        dumped = config.model_dump(by_alias=True)
        assert dumped["3Dboundingbox"] is True
