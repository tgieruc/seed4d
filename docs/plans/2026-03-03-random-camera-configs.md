# Random Camera Configuration for Variable-Camera Training

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create tooling to generate random camera configurations for seed4d, producing training data with 1-N cameras at arbitrary viewpoints for 6Img-to-3D's variable camera support.

**Architecture:** A Python script generates random camera JSON configs (positions, angles, FOVs), and a companion script creates YAML scenario configs referencing them. seed4d's existing pipeline handles the rest — no core code changes needed.

**Tech Stack:** Python, JSON, YAML, seed4d camera config format

**Design doc:** `6Img-to-3D/docs/plans/2026-03-03-variable-camera-support-design.md`

---

### Task 1: Random camera config generator script

**Files:**
- Create: `utils/generate_random_camera_config.py`
- Create: `tests/test_random_camera_config.py`

**Step 1: Write the failing test**

Create `tests/test_random_camera_config.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/tgieruc/Documents/seed4d && python3 -m pytest tests/test_random_camera_config.py -v`

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

Create `utils/generate_random_camera_config.py`:

```python
"""Generate random camera configuration JSONs for seed4d.

Creates camera configs with random positions, orientations, and FOVs
for use with seed4d's data generation pipeline, producing training data
with variable camera counts for 6Img-to-3D.

Usage:
    python utils/generate_random_camera_config.py --num-cameras 4 --output config/camera/random/random_4cam.json
    python utils/generate_random_camera_config.py --num-cameras random --count 10 --output-dir config/camera/random/
"""

import argparse
import json
import math
import os
import random


# Vehicle-mounted camera bounds (meters, radians)
POSITION_BOUNDS = {
    "x": (-1.5, 2.0),   # longitudinal (negative=rear, positive=front)
    "y": (-1.0, 1.0),   # lateral (negative=right, positive=left)
    "z": (1.0, 2.5),    # height above ground
}
PITCH_BOUNDS = (-math.pi / 4, math.pi / 6)  # -45° to +30° (radians)
YAW_BOUNDS = (0, 2 * math.pi)               # full 360° (radians)
FOV_BOUNDS = (60.0, 120.0)                   # degrees
MIN_CAMS = 1
MAX_CAMS = 6


def generate_random_camera_config(num_cameras="random", seed=None,
                                   min_cams=MIN_CAMS, max_cams=MAX_CAMS):
    """Generate a random camera configuration dict.

    Args:
        num_cameras: int or "random". If "random", picks uniformly from [min_cams, max_cams].
        seed: Random seed for reproducibility.
        min_cams: Minimum cameras when num_cameras="random".
        max_cams: Maximum cameras when num_cameras="random".

    Returns:
        dict with keys: coordinates, pitchs, yaws, fov
    """
    rng = random.Random(seed)

    if num_cameras == "random":
        num_cameras = rng.randint(min_cams, max_cams)

    coordinates = []
    pitchs = []
    yaws = []
    fovs = []

    for _ in range(num_cameras):
        x = rng.uniform(*POSITION_BOUNDS["x"])
        y = rng.uniform(*POSITION_BOUNDS["y"])
        z = rng.uniform(*POSITION_BOUNDS["z"])
        coordinates.append([round(x, 6), round(y, 6), round(z, 6)])

        pitch = rng.uniform(*PITCH_BOUNDS)
        pitchs.append(round(pitch, 6))

        yaw = rng.uniform(*YAW_BOUNDS)
        yaws.append(round(yaw, 6))

        fov = rng.uniform(*FOV_BOUNDS)
        fovs.append(round(fov, 1))

    return {
        "coordinates": coordinates,
        "pitchs": pitchs,
        "yaws": yaws,
        "fov": fovs,
    }


def save_camera_config(config, output_path):
    """Save camera config dict to JSON file."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(config, f, indent=4)


def main():
    parser = argparse.ArgumentParser(
        description="Generate random camera configurations for seed4d"
    )
    parser.add_argument(
        "--num-cameras", type=str, default="random",
        help="Number of cameras (int or 'random')"
    )
    parser.add_argument(
        "--count", type=int, default=1,
        help="Number of configs to generate (for batch mode)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Base random seed"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output JSON path (single config mode)"
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory (batch mode)"
    )
    parser.add_argument(
        "--min-cams", type=int, default=MIN_CAMS,
        help="Minimum cameras when --num-cameras=random"
    )
    parser.add_argument(
        "--max-cams", type=int, default=MAX_CAMS,
        help="Maximum cameras when --num-cameras=random"
    )
    args = parser.parse_args()

    num_cams = args.num_cameras if args.num_cameras == "random" else int(args.num_cameras)

    if args.count == 1 and args.output:
        config = generate_random_camera_config(
            num_cameras=num_cams, seed=args.seed,
            min_cams=args.min_cams, max_cams=args.max_cams)
        save_camera_config(config, args.output)
        print(f"Saved {len(config['coordinates'])}-camera config to {args.output}")
    elif args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        for i in range(args.count):
            seed = (args.seed + i) if args.seed is not None else None
            config = generate_random_camera_config(
                num_cameras=num_cams, seed=seed,
                min_cams=args.min_cams, max_cams=args.max_cams)
            n = len(config["coordinates"])
            path = os.path.join(args.output_dir, f"random_{n}cam_{i:04d}.json")
            save_camera_config(config, path)
            print(f"Saved {n}-camera config to {path}")
    else:
        parser.error("Specify --output (single) or --output-dir (batch)")


if __name__ == "__main__":
    main()
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/tgieruc/Documents/seed4d && python3 -m pytest tests/test_random_camera_config.py -v`

Expected: 7 PASSED

**Step 5: Commit**

```bash
git add utils/generate_random_camera_config.py tests/test_random_camera_config.py
git commit -m "feat: random camera config generator for variable-camera training"
```

---

### Task 2: Batch YAML scenario config generator

**Files:**
- Create: `utils/generate_random_scenario_configs.py`
- Create: `tests/test_random_scenario_configs.py`

**Step 1: Write the failing test**

Create `tests/test_random_scenario_configs.py`:

```python
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
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/tgieruc/Documents/seed4d && python3 -m pytest tests/test_random_scenario_configs.py -v`

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write implementation**

Create `utils/generate_random_scenario_configs.py`:

```python
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
from generate_random_camera_config import generate_random_camera_config, save_camera_config


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
            num_cameras="random", seed=cam_seed,
            min_cams=min_cams, max_cams=max_cams)

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
    parser = argparse.ArgumentParser(
        description="Generate batch YAML scenario configs with random cameras"
    )
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
```

**Step 4: Run test to verify it passes**

Run: `cd /Users/tgieruc/Documents/seed4d && python3 -m pytest tests/test_random_scenario_configs.py -v`

Expected: 2 PASSED

**Step 5: Commit**

```bash
git add utils/generate_random_scenario_configs.py tests/test_random_scenario_configs.py
git commit -m "feat: batch YAML scenario config generator with random cameras"
```

---

### Task 3: Verify 6Img-to-3D loads seed4d output with variable cameras

**Files:**
- Create: `6Img-to-3D/tests/test_seed4d_compatibility.py` (at `/Users/tgieruc/Documents/6Img-to-3D/tests/test_seed4d_compatibility.py`)

This test verifies that a transforms_ego.json produced by seed4d (with variable cameras and per-camera intrinsics) loads correctly in 6Img-to-3D's dataset.

**Step 1: Write the test**

Create `/Users/tgieruc/Documents/6Img-to-3D/tests/test_seed4d_compatibility.py`:

```python
"""Verify 6Img-to-3D correctly loads seed4d data with variable camera counts."""
import json
import numpy as np
import os
import tempfile
import pytest


def _make_transforms_ego(num_cams, per_camera_intrinsics=False):
    """Create a synthetic transforms_ego.json matching seed4d output format."""
    data = {
        "camera_model": "OPENCV",
        "k1": 0, "k2": 0, "p1": 0, "p2": 0,
        "frames": [],
    }

    if not per_camera_intrinsics:
        data["fl_x"] = 500.0
        data["fl_y"] = 500.0
        data["cx"] = 50.0
        data["cy"] = 50.0
        data["w"] = 100
        data["h"] = 100

    for i in range(num_cams):
        frame = {
            "file_path": f"../sensors/{i}_rgb.png",
            "transform_matrix": np.eye(4).tolist(),
        }
        if per_camera_intrinsics:
            frame["fl_x"] = 400.0 + i * 20
            frame["fl_y"] = 400.0 + i * 20
            frame["cx"] = 50.0
            frame["cy"] = 50.0
            frame["w"] = 100
            frame["h"] = 100
        data["frames"].append(frame)

    return data


def test_load_global_intrinsics():
    """6Img-to-3D reads global intrinsics when per-frame not present."""
    from dataloader.dataset import build_pose_intrinsics_vector

    data = _make_transforms_ego(4, per_camera_intrinsics=False)

    num_cams = len(data["frames"])
    K = np.zeros((num_cams, 3, 4))
    all_c2w = []
    for cam_idx, frame in enumerate(data["frames"]):
        fx = frame.get("fl_x", data.get("fl_x", 0))
        fy = frame.get("fl_y", data.get("fl_y", 0))
        cx = frame.get("cx", data.get("cx", 0))
        cy = frame.get("cy", data.get("cy", 0))
        K[cam_idx, 0, 0] = fx
        K[cam_idx, 1, 1] = fy
        K[cam_idx, 2, 2] = 1
        K[cam_idx, 0, 2] = cx
        K[cam_idx, 1, 2] = cy
        all_c2w.append(frame["transform_matrix"])

    assert K.shape == (4, 3, 4)
    # All cameras should have same intrinsics (global)
    assert np.allclose(K[0, 0, 0], K[3, 0, 0])  # same fx

    vec = build_pose_intrinsics_vector(all_c2w, K)
    assert vec.shape == (4, 20)


def test_load_per_camera_intrinsics():
    """6Img-to-3D reads per-frame intrinsics when present."""
    from dataloader.dataset import build_pose_intrinsics_vector

    data = _make_transforms_ego(3, per_camera_intrinsics=True)

    num_cams = len(data["frames"])
    K = np.zeros((num_cams, 3, 4))
    all_c2w = []
    for cam_idx, frame in enumerate(data["frames"]):
        fx = frame.get("fl_x", data.get("fl_x", 0))
        fy = frame.get("fl_y", data.get("fl_y", 0))
        cx = frame.get("cx", data.get("cx", 0))
        cy = frame.get("cy", data.get("cy", 0))
        K[cam_idx, 0, 0] = fx
        K[cam_idx, 1, 1] = fy
        K[cam_idx, 2, 2] = 1
        K[cam_idx, 0, 2] = cx
        K[cam_idx, 1, 2] = cy
        all_c2w.append(frame["transform_matrix"])

    assert K.shape == (3, 3, 4)
    # Per-camera intrinsics should differ
    assert K[0, 0, 0] != K[2, 0, 0]  # different fx

    vec = build_pose_intrinsics_vector(all_c2w, K)
    assert vec.shape == (3, 20)
    # Verify intrinsics are in the vector
    assert np.isclose(vec[0, 16], 400.0)  # fx of camera 0
    assert np.isclose(vec[2, 16], 440.0)  # fx of camera 2


def test_collate_with_seed4d_format():
    """Collate function handles seed4d-style data with variable cameras."""
    from dataloader.dataset import build_pose_intrinsics_vector
    from dataloader.dataset_wrapper import custom_collate_fn

    # Simulate 2 samples: 3 cameras and 5 cameras
    samples = []
    for n_cams in [3, 5]:
        data = _make_transforms_ego(n_cams)
        K = np.zeros((n_cams, 3, 4))
        all_c2w = []
        for cam_idx, frame in enumerate(data["frames"]):
            K[cam_idx, 0, 0] = frame.get("fl_x", data.get("fl_x", 0))
            K[cam_idx, 1, 1] = frame.get("fl_y", data.get("fl_y", 0))
            K[cam_idx, 2, 2] = 1
            K[cam_idx, 0, 2] = frame.get("cx", data.get("cx", 0))
            K[cam_idx, 1, 2] = frame.get("cy", data.get("cy", 0))
            all_c2w.append(frame["transform_matrix"])

        imgs = np.random.randn(n_cams, 100, 100, 3).astype(np.float32)
        meta = dict(
            K=K,
            c2w=all_c2w,
            img_shape=[(100, 100, 3)] * n_cams,
            pose_intrinsics=build_pose_intrinsics_vector(all_c2w, K),
            num_cams=n_cams,
        )
        samples.append((imgs, meta, None))

    img_batch, meta_batch, _ = custom_collate_fn(samples)

    assert img_batch.shape == (2, 5, 3, 100, 100)  # padded to max=5
    assert meta_batch[0]["cam_mask"][:3].all()
    assert not meta_batch[0]["cam_mask"][3:].any()
    assert meta_batch[1]["cam_mask"].all()
```

**Step 2: Run the test**

Run: `cd /Users/tgieruc/Documents/6Img-to-3D && python3 -m pytest tests/test_seed4d_compatibility.py -v`

Expected: 3 PASSED

**Step 3: Commit**

```bash
cd /Users/tgieruc/Documents/6Img-to-3D
git add tests/test_seed4d_compatibility.py
git commit -m "test: verify seed4d data format compatibility with variable cameras"
```

---

## Task Dependency Order

```
Task 1 (random camera generator) ── independent
Task 2 (scenario config generator) ── depends on Task 1
Task 3 (compatibility test) ── independent
```

Tasks 1 and 3 can run in parallel. Task 2 depends on Task 1.
