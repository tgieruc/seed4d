import os
import yaml
import tempfile
import pytest


def test_generates_valid_yaml():
    """Generated scenario config has all required fields."""
    from utils.generate_random_scenario_configs import generate_scenario_config

    config = generate_scenario_config(
        camera_config_path="/seed4d/config/camera/random/random_4cam_0000.json",
        map_name="Town01",
        weather="ClearNoon",
        vehicle="vehicle.tesla.invisible",
        spawn_point=0,
    )

    assert config["map"] == "Town01"
    assert config["weather"] == "ClearNoon"
    assert config["vehicle"] == "vehicle.tesla.invisible"
    assert config["spawn_point"] == [0]
    assert "dataset" in config
    assert "nuscenes" in config["dataset"]
    assert config["dataset"]["nuscenes"]["transform_file_cams"] == "/seed4d/config/camera/random/random_4cam_0000.json"


def test_batch_generation():
    """Batch generates multiple configs with different camera setups."""
    from utils.generate_random_scenario_configs import generate_batch_configs

    with tempfile.TemporaryDirectory() as tmpdir:
        camera_dir = os.path.join(tmpdir, "cameras")
        config_dir = os.path.join(tmpdir, "configs")

        configs = generate_batch_configs(
            camera_dir=camera_dir,
            config_dir=config_dir,
            num_configs=5,
            maps=["Town01"],
            weathers=["ClearNoon"],
            spawn_points=[0, 1, 2],
            seed=42,
        )

        assert len(configs) == 5
        assert os.path.isdir(config_dir)
        yaml_files = [f for f in os.listdir(config_dir) if f.endswith(".yaml")]
        assert len(yaml_files) == 5
