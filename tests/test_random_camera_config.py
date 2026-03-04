import json
import os
import tempfile
import pytest


def test_generates_valid_json():
    """Generated config has required fields with correct array lengths."""
    from utils.generate_random_camera_config import generate_random_camera_config

    config = generate_random_camera_config(num_cameras=4, seed=42)

    assert "coordinates" in config
    assert "pitchs" in config
    assert "yaws" in config
    assert "fov" in config
    assert len(config["coordinates"]) == 4
    assert len(config["pitchs"]) == 4
    assert len(config["yaws"]) == 4
    assert len(config["fov"]) == 4


def test_coordinate_bounds():
    """Camera positions are within vehicle-mounted bounds."""
    from utils.generate_random_camera_config import generate_random_camera_config

    config = generate_random_camera_config(num_cameras=6, seed=42)

    for coord in config["coordinates"]:
        x, y, z = coord
        assert -1.5 <= x <= 2.0, f"x={x} out of bounds"
        assert -1.0 <= y <= 1.0, f"y={y} out of bounds"
        assert 1.0 <= z <= 2.5, f"z={z} out of bounds"


def test_angle_bounds():
    """Pitch and yaw are within reasonable ranges."""
    import math
    from utils.generate_random_camera_config import generate_random_camera_config

    config = generate_random_camera_config(num_cameras=6, seed=42)

    for pitch in config["pitchs"]:
        assert -math.pi / 4 <= pitch <= math.pi / 6, f"pitch={pitch} out of bounds"

    for yaw in config["yaws"]:
        assert 0 <= yaw <= 2 * math.pi, f"yaw={yaw} out of bounds"


def test_fov_bounds():
    """FOV values are in reasonable range."""
    from utils.generate_random_camera_config import generate_random_camera_config

    config = generate_random_camera_config(num_cameras=3, seed=42)

    for fov in config["fov"]:
        assert 60.0 <= fov <= 120.0, f"fov={fov} out of bounds"


def test_random_count():
    """When num_cameras='random', produces 1-6 cameras."""
    from utils.generate_random_camera_config import generate_random_camera_config

    counts = set()
    for seed in range(50):
        config = generate_random_camera_config(num_cameras="random", seed=seed)
        n = len(config["coordinates"])
        assert 1 <= n <= 6
        counts.add(n)

    # Over 50 seeds, should see at least 3 different counts
    assert len(counts) >= 3


def test_deterministic_with_seed():
    """Same seed produces identical config."""
    from utils.generate_random_camera_config import generate_random_camera_config

    config1 = generate_random_camera_config(num_cameras=4, seed=123)
    config2 = generate_random_camera_config(num_cameras=4, seed=123)

    assert config1 == config2


def test_save_to_file():
    """Config can be saved to JSON file."""
    from utils.generate_random_camera_config import generate_random_camera_config, save_camera_config

    config = generate_random_camera_config(num_cameras=3, seed=42)

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        save_camera_config(config, f.name)
        f.flush()

        with open(f.name, "r") as rf:
            loaded = json.load(rf)

        assert loaded == config
        os.unlink(f.name)
