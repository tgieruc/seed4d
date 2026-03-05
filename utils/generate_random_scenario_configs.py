"""Generate batch YAML scenario configs with random camera setups for seed4d.

Creates YAML configs that reference randomly-generated camera JSON files,
covering different maps, weathers, spawn points, and camera configurations.

Usage:
    python utils/generate_random_scenario_configs.py \
        --num-configs 100 \
        --camera-dir config/camera/random/ \
        --config-dir config/random_scenarios/ \
        --maps Town01 Town03 Town04 \
        --weathers ClearNoon CloudyNoon \
        --seed 42
"""

import argparse
import os
import random

import yaml

from utils.generate_random_camera_config import generate_random_camera_config, save_camera_config

# Default sensor setup matching existing nuscenes config
DEFAULT_SENSOR_INFO = {
    "fov": 90,
    "height": 928,
    "width": 1600,
    "type": [
        "sensor.camera.rgb",
        "sensor.camera.semantic_segmentation",
        "sensor.camera.instance_segmentation",
        "sensor.camera.depth",
    ],
}

DEFAULT_MAPS = ["Town01", "Town03", "Town04", "Town05", "Town06", "Town07", "Town10HD"]
DEFAULT_WEATHERS = ["ClearNoon"]


def generate_scenario_config(
    camera_config_path,
    map_name,
    weather,
    vehicle="vehicle.tesla.invisible",
    spawn_point=0,
    sensor_info=None,
    num_steps=10,
    num_vehicles=0,
    num_walkers=0,
):
    """Generate a single scenario YAML config dict.

    Args:
        camera_config_path: Absolute path to camera JSON config.
        map_name: CARLA map name.
        weather: CARLA weather preset.
        vehicle: Vehicle blueprint name.
        spawn_point: Spawn point index.
        sensor_info: Sensor configuration dict (uses default if None).
        num_steps: Number of timesteps to capture.
        num_vehicles: Number of other vehicles.
        num_walkers: Number of pedestrians.

    Returns:
        dict suitable for yaml.dump
    """
    if sensor_info is None:
        sensor_info = DEFAULT_SENSOR_INFO.copy()

    return {
        "map": map_name,
        "weather": weather,
        "vehicle": vehicle,
        "spawn_point": [spawn_point],
        "num_steps": num_steps,
        "num_vehicles": num_vehicles,
        "num_walkers": num_walkers,
        "BEVCamera": False,
        "invisible_ego": True,
        "3Dboundingbox": False,
        "other_vehicles_have_sensors": False,
        "dataset": {
            "nuscenes": {
                "attached_to_vehicle": True,
                "sensor_info": sensor_info,
                "transform_file_cams": camera_config_path,
            },
        },
    }


def generate_batch_configs(
    camera_dir,
    config_dir,
    num_configs,
    maps=None,
    weathers=None,
    spawn_points=None,
    seed=None,
    min_cams=1,
    max_cams=6,
):
    """Generate multiple scenario configs with random camera setups.

    Args:
        camera_dir: Directory to save camera JSON configs.
        config_dir: Directory to save YAML scenario configs.
        num_configs: Number of configs to generate.
        maps: List of CARLA map names.
        weathers: List of CARLA weather presets.
        spawn_points: List of spawn point indices.
        seed: Base random seed.
        min_cams: Minimum cameras per config.
        max_cams: Maximum cameras per config.

    Returns:
        List of generated config paths.
    """
    if maps is None:
        maps = DEFAULT_MAPS
    if weathers is None:
        weathers = DEFAULT_WEATHERS
    if spawn_points is None:
        spawn_points = list(range(100))

    os.makedirs(camera_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)

    rng = random.Random(seed)
    config_paths = []

    for i in range(num_configs):
        # Generate random camera config
        cam_seed = (seed + i) if seed is not None else None
        cam_config = generate_random_camera_config(
            num_cameras="random", seed=cam_seed, min_cams=min_cams, max_cams=max_cams
        )

        n_cams = len(cam_config["coordinates"])
        cam_path = os.path.join(os.path.abspath(camera_dir), f"random_{n_cams}cam_{i:04d}.json")
        save_camera_config(cam_config, cam_path)

        # Generate scenario config
        map_name = rng.choice(maps)
        weather = rng.choice(weathers)
        spawn_point = rng.choice(spawn_points)

        scenario = generate_scenario_config(
            camera_config_path=cam_path,
            map_name=map_name,
            weather=weather,
            spawn_point=spawn_point,
        )

        config_path = os.path.join(config_dir, f"scenario_{i:04d}.yaml")
        with open(config_path, "w") as f:
            yaml.dump(scenario, f, default_flow_style=False)

        config_paths.append(config_path)

    return config_paths


def main():
    parser = argparse.ArgumentParser(description="Generate batch YAML scenario configs with random cameras")
    parser.add_argument("--num-configs", type=int, default=10)
    parser.add_argument("--camera-dir", type=str, default="config/camera/random/")
    parser.add_argument("--config-dir", type=str, default="config/random_scenarios/")
    parser.add_argument("--maps", nargs="+", default=DEFAULT_MAPS)
    parser.add_argument("--weathers", nargs="+", default=DEFAULT_WEATHERS)
    parser.add_argument("--spawn-points", nargs="+", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-cams", type=int, default=1)
    parser.add_argument("--max-cams", type=int, default=6)
    args = parser.parse_args()

    configs = generate_batch_configs(
        camera_dir=args.camera_dir,
        config_dir=args.config_dir,
        num_configs=args.num_configs,
        maps=args.maps,
        weathers=args.weathers,
        spawn_points=args.spawn_points,
        seed=args.seed,
        min_cams=args.min_cams,
        max_cams=args.max_cams,
    )

    print(f"Generated {len(configs)} scenario configs in {args.config_dir}")


if __name__ == "__main__":
    main()
