"""Tests for common/pose.py coordinate transforms and sphere generation."""

import math
import sys

import tests.mock_carla as mock_carla

sys.modules["carla"] = mock_carla

import numpy as np  # noqa: E402
from scipy.spatial.transform import Rotation as R  # noqa: E402

import common.pose as pose  # noqa: E402
from tests.mock_carla import Location, Rotation, Transform  # noqa: E402


# ---------------------------------------------------------------------------
# fibonacci_sphere
# ---------------------------------------------------------------------------
class TestFibonacciSphere:
    def test_correct_count(self):
        for n in [1, 5, 50, 100]:
            pts = pose.fibonacci_sphere(span=1.0, N=n)
            assert len(pts) == n

    def test_points_are_3d(self):
        pts = pose.fibonacci_sphere(span=1.0, N=10)
        for pt in pts:
            assert len(pt) == 3

    def test_span_scaling(self):
        pts1 = pose.fibonacci_sphere(span=1.0, N=20)
        pts5 = pose.fibonacci_sphere(span=5.0, N=20)
        for p1, p5 in zip(pts1, pts5):
            for a, b in zip(p1, p5):
                assert abs(b - 5.0 * a) < 1e-10

    def test_half_sphere_z_nonnegative(self):
        pts = pose.fibonacci_sphere(span=1.0, N=50)
        for pt in pts:
            assert pt[2] >= -1e-10, f"z={pt[2]} is negative"

    def test_approximate_unit_radius(self):
        pts = pose.fibonacci_sphere(span=1.0, N=50)
        for pt in pts:
            r = math.sqrt(pt[0] ** 2 + pt[1] ** 2 + pt[2] ** 2)
            assert abs(r - 1.0) < 1e-6, f"radius={r}, expected ~1.0"

    def test_boundary_points(self):
        pts = pose.fibonacci_sphere(span=1.0, N=50)
        # First point: y=0 -> z=0, on equator
        assert abs(pts[0][2]) < 1e-10
        # Last point: y=1 -> z=1, at pole
        assert abs(pts[-1][2] - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# generate_sphere_transforms
# ---------------------------------------------------------------------------
class TestGenerateSphereTransforms:
    def test_output_keys_and_shape(self):
        result = pose.generate_sphere_transforms(origin=[0, 0, 0], z_offset=0.0, radius=5.0, N=20)
        assert "coordinates" in result
        assert "pitchs" in result
        assert "yaws" in result
        assert len(result["coordinates"]) == 20
        assert len(result["pitchs"]) == 20
        assert len(result["yaws"]) == 20

    def test_radius_scaling(self):
        r1 = pose.generate_sphere_transforms(origin=[0, 0, 0], z_offset=0.0, radius=1.0, N=10)
        r5 = pose.generate_sphere_transforms(origin=[0, 0, 0], z_offset=0.0, radius=5.0, N=10)
        # Coordinates should scale by radius (minus z_offset=0)
        np.testing.assert_allclose(r5["coordinates"], 5.0 * r1["coordinates"], atol=1e-10)

    def test_z_offset_shift(self):
        r0 = pose.generate_sphere_transforms(origin=[0, 0, 0], z_offset=0.0, radius=5.0, N=10)
        r3 = pose.generate_sphere_transforms(origin=[0, 0, 0], z_offset=3.0, radius=5.0, N=10)
        diffs = r3["coordinates"] - r0["coordinates"]
        # Only z should differ, by z_offset
        np.testing.assert_allclose(diffs[:, 0], 0.0, atol=1e-10)
        np.testing.assert_allclose(diffs[:, 1], 0.0, atol=1e-10)
        np.testing.assert_allclose(diffs[:, 2], 3.0, atol=1e-10)

    def test_pitch_range(self):
        result = pose.generate_sphere_transforms(origin=[0, 0, 0], z_offset=0.0, radius=5.0, N=50)
        # Pitchs are arcsin of z-component of unit sphere points
        # z ranges from 0 to 1 on half sphere, so pitch in [0, pi/2]
        assert np.all(result["pitchs"] >= -1e-10)
        assert np.all(result["pitchs"] <= math.pi / 2 + 1e-10)


# ---------------------------------------------------------------------------
# carla_to_nerf_unnormalized
# ---------------------------------------------------------------------------
class TestCarlaToNerfUnnormalized:
    def test_location_swap(self):
        """CARLA (x,y,z) -> NeRF (-z, x, y) for location."""
        t = Transform(Location(x=1.0, y=2.0, z=3.0), Rotation(pitch=0, yaw=0, roll=0))
        mat = pose.carla_to_nerf_unnormalized(t)
        mat = np.array(mat)
        # Translation column
        assert abs(mat[0, 3] - (-3.0)) < 1e-6  # -z
        assert abs(mat[1, 3] - 1.0) < 1e-6  # x
        assert abs(mat[2, 3] - 2.0) < 1e-6  # y

    def test_valid_rotation_matrix(self):
        """Output 3x3 must be orthogonal with det=1."""
        t = Transform(Location(1, 2, 3), Rotation(pitch=30, yaw=45, roll=10))
        mat = np.array(pose.carla_to_nerf_unnormalized(t))
        rot = mat[:3, :3]
        # Orthogonality: R^T R = I
        np.testing.assert_allclose(rot.T @ rot, np.eye(3), atol=1e-6)
        # Proper rotation: det = 1
        assert abs(np.linalg.det(rot) - 1.0) < 1e-6

    def test_multiple_rotations(self):
        """Test various rotation angles produce valid rotation matrices."""
        for pitch in [0, 45, -30, 90]:
            for yaw in [0, 90, 180, -45]:
                for roll in [0, 15, -15]:
                    t = Transform(Location(0, 0, 0), Rotation(pitch=pitch, yaw=yaw, roll=roll))
                    mat = np.array(pose.carla_to_nerf_unnormalized(t))
                    rot = mat[:3, :3]
                    np.testing.assert_allclose(rot.T @ rot, np.eye(3), atol=1e-6)
                    assert abs(np.linalg.det(rot) - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# carla_to_nerf_normalized
# ---------------------------------------------------------------------------
class TestCarlaToNerfNormalized:
    def test_centering_and_scaling(self):
        origin = Transform(Location(x=10, y=20, z=30), Rotation())
        radius = 5.0
        cam = Transform(Location(x=15, y=25, z=35), Rotation(pitch=0, yaw=0, roll=0))
        mat = np.array(pose.carla_to_nerf_normalized(cam, origin, radius))
        # Normalized location: (15-10)/5=1, (25-20)/5=1, (35-30)/5=1
        # Then swap: (-nz, nx, ny) = (-1, 1, 1)
        assert abs(mat[0, 3] - (-1.0)) < 1e-6
        assert abs(mat[1, 3] - 1.0) < 1e-6
        assert abs(mat[2, 3] - 1.0) < 1e-6

    def test_valid_rotation(self):
        origin = Transform(Location(0, 0, 0), Rotation())
        cam = Transform(Location(1, 2, 3), Rotation(pitch=20, yaw=40, roll=5))
        mat = np.array(pose.carla_to_nerf_normalized(cam, origin, 10.0))
        rot = mat[:3, :3]
        np.testing.assert_allclose(rot.T @ rot, np.eye(3), atol=1e-6)
        assert abs(np.linalg.det(rot) - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# extract_xyz_yaw_pitch_roll
# ---------------------------------------------------------------------------
class TestExtractXyzYawPitchRoll:
    def test_identity_matrix(self):
        mat = np.eye(4)
        x, y, z, yaw, pitch, roll = pose.extract_xyz_yaw_pitch_roll(mat)
        assert abs(x) < 1e-10
        assert abs(y) < 1e-10
        assert abs(z) < 1e-10
        assert abs(yaw) < 1e-6
        assert abs(pitch) < 1e-6
        assert abs(roll) < 1e-6

    def test_translation_extraction(self):
        mat = np.eye(4)
        mat[0, 3] = 5.0
        mat[1, 3] = -3.0
        mat[2, 3] = 7.0
        x, y, z, _yaw, _pitch, _roll = pose.extract_xyz_yaw_pitch_roll(mat)
        assert abs(x - 5.0) < 1e-10
        assert abs(y - (-3.0)) < 1e-10
        assert abs(z - 7.0) < 1e-10

    def test_known_90_yaw(self):
        """90 degree yaw rotation around Z-axis."""
        mat = np.eye(4)
        mat[:3, :3] = R.from_euler("Z", 90, degrees=True).as_matrix()
        _x, _y, _z, yaw, _pitch, _roll = pose.extract_xyz_yaw_pitch_roll(mat)
        assert abs(yaw - 90.0) < 1e-4

    def test_roundtrip_with_scipy(self):
        """Build a matrix from known angles, extract, verify consistency."""
        for angles in [(30, 15, -10), (0, 0, 0), (90, 45, 20), (-60, 10, 5)]:
            yaw_in, pitch_in, roll_in = angles
            # Build rotation: ZYX convention with pitch negated (matching extract function)
            rot = R.from_euler("ZYX", [yaw_in, -pitch_in, roll_in], degrees=True)
            mat = np.eye(4)
            mat[:3, :3] = rot.as_matrix()
            mat[0, 3], mat[1, 3], mat[2, 3] = 1.0, 2.0, 3.0

            x, y, z, yaw_out, pitch_out, roll_out = pose.extract_xyz_yaw_pitch_roll(mat)

            assert abs(x - 1.0) < 1e-10
            assert abs(y - 2.0) < 1e-10
            assert abs(z - 3.0) < 1e-10
            assert abs(yaw_out - yaw_in) < 1e-4, f"yaw: {yaw_out} vs {yaw_in}"
            assert abs(pitch_out - pitch_in) < 1e-4, f"pitch: {pitch_out} vs {pitch_in}"
            assert abs(roll_out - roll_in) < 1e-4, f"roll: {roll_out} vs {roll_in}"
