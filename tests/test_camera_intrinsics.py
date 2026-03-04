"""Tests for camera intrinsics computation in common/sensor.py."""

import math
import sys

import tests.mock_carla as mock_carla

sys.modules["carla"] = mock_carla

from common.sensor import SensorManager  # noqa: E402


class TestCameraIntrinsicsFromFov:
    """Tests for SensorManager.get_camera_intrinsics_from_fov static method."""

    def test_fov_90_focal_length(self):
        """FOV=90° → fx = width / 2."""
        result = SensorManager.get_camera_intrinsics_from_fov(fov=90, width=800, height=600)
        assert abs(result["fx"] - 400.0) < 1e-6

    def test_principal_point_centered(self):
        """cx = width/2, cy = height/2."""
        result = SensorManager.get_camera_intrinsics_from_fov(fov=90, width=800, height=600)
        assert abs(result["cx"] - 400.0) < 1e-10
        assert abs(result["cy"] - 300.0) < 1e-10

    def test_fx_equals_fy(self):
        """Square pixels: fx == fy."""
        result = SensorManager.get_camera_intrinsics_from_fov(fov=70, width=1920, height=1080)
        assert abs(result["fx"] - result["fy"]) < 1e-10

    def test_fov_60(self):
        """FOV=60° → fx = 0.5*width / tan(30°) = 0.5*width / (1/√3) = 0.5*width*√3."""
        width = 1000
        expected_fx = 0.5 * width / math.tan(math.radians(30))
        result = SensorManager.get_camera_intrinsics_from_fov(fov=60, width=width, height=500)
        assert abs(result["fx"] - expected_fx) < 1e-6

    def test_fov_120(self):
        """FOV=120° → fx = 0.5*width / tan(60°)."""
        width = 1200
        expected_fx = 0.5 * width / math.tan(math.radians(60))
        result = SensorManager.get_camera_intrinsics_from_fov(fov=120, width=width, height=800)
        assert abs(result["fx"] - expected_fx) < 1e-6

    def test_narrow_fov_large_focal(self):
        """Narrower FOV → larger focal length."""
        narrow = SensorManager.get_camera_intrinsics_from_fov(fov=30, width=800, height=600)
        wide = SensorManager.get_camera_intrinsics_from_fov(fov=90, width=800, height=600)
        assert narrow["fx"] > wide["fx"]

    def test_wider_image_larger_focal(self):
        """Same FOV, wider image → proportionally larger focal length."""
        small = SensorManager.get_camera_intrinsics_from_fov(fov=90, width=400, height=300)
        large = SensorManager.get_camera_intrinsics_from_fov(fov=90, width=800, height=600)
        assert abs(large["fx"] / small["fx"] - 2.0) < 1e-6
