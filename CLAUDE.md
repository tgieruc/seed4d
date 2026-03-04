# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SEED4D (Synthetic Ego-Exo Dynamic 4D) is a synthetic dataset generator for autonomous driving research (WACV 2025). It uses the CARLA simulator (v0.9.16) to generate multi-view camera and LiDAR data in Nerfstudio-compatible format. Runs inside Docker based on `carlasim/carla:0.9.16`.

## Commands

### Running Tests
```bash
python3 -m pytest tests/ -v
```
Run a single test file:
```bash
python3 -m pytest tests/test_random_camera_config.py -v
```

### Dataset Generation (inside Docker)
```bash
# Single config
python3 main.py --config config/nuscenes.yaml --data_dir data

# Directory of configs
python3 main.py --config_dir config/dynamic/ --data_dir data

# Direct generator (single scenario)
python3 generator.py --config config/nuscenes.yaml --data_dir data --carla_executable /workspace/CarlaUE4.sh
```

### Utility Scripts
```bash
# Generate random camera configs
python3 utils/generate_random_camera_config.py --output_dir config/camera/random --num_configs 10

# Generate batch YAML scenario configs
python3 utils/generate_random_scenario_configs.py --output_dir config/random --num_configs 50

# Generate camera config (sphere/nuscenes layouts)
python3 utils/generate_camera_config.py
```

### Docker
```bash
docker build -t seed4d .
```

## Architecture

### Execution Flow
`main.py` → iterates YAML configs → spawns `generator.py` as a subprocess per config → optionally runs post-processing (normalize coords, masks, combined transforms, map generation).

### Core Components
- **`generator.py`** — `Generator` class (context manager). Connects to CARLA, sets up world/weather, spawns ego vehicle + traffic, attaches sensors via `SensorManager`, ticks simulation for N steps, saves all outputs (images, depth, segmentation, LiDAR, transforms).
- **`common/sensor.py`** — `Sensor`, `BEVCamera`, `SensorManager` classes. `SensorManager._get_carla_transforms()` converts camera config JSON to CARLA transforms (applies +90° yaw correction).
- **`common/vehicle.py`** — `Vehicle` class for spawning and managing the ego vehicle with attached sensors and autopilot.
- **`common/pose.py`** — Coordinate transforms between CARLA (left-handed, Z-up) and NeRF/OpenGL (right-handed, Y-up) conventions.
- **`common/environment.py`** — CARLA world initialization (weather, synchronous mode, tick settings).
- **`common/generate_traffic.py`** — NPC vehicle and pedestrian spawning.

### Configuration System
- **YAML scenario configs** (`config/*.yaml`) — define map, weather, vehicle, spawn points, sensor setups, and simulation parameters. Parsed by `configargparse` in `common/parser.py`.
- **Camera config JSON** (`config/camera/<rig>/*.json`) — format: `{"coordinates": [[x,y,z],...], "pitchs": [...], "yaws": [...], "fov": [...]}`. Positions in meters relative to vehicle, angles in radians.
- **LiDAR config JSON** (`config/lidar/`) — similar structure for LiDAR placement.

### Output Format
Nerfstudio-compatible `transforms.json` per timestep/sensor group, with `camera_model: OPENCV`, per-frame 4×4 `transform_matrix` (OpenGL convention), and camera intrinsics. Data saved under `data/<map>/<weather>/<vehicle>/spawn_point_<id>/`.

### Utility Scripts (`utils/`)
Post-processing and config generation tools. Key ones:
- `generate_random_camera_config.py` — random camera rig JSON with configurable bounds
- `generate_random_scenario_configs.py` — batch YAML scenario configs across towns/weather/vehicles
- `generate_normalized_coordinates.py` — normalize world coordinates
- `generate_masks.py` — vehicle mask generation
- `generate_single_transforms.py` — combine per-timestep transforms into one file

## Key Conventions
- CARLA paths in configs and `main.py` use absolute Docker paths (e.g., `/seed4d/utils/`, `/workspace/CarlaUE4.sh`)
- Camera angles (pitch, yaw) stored in radians in JSON configs
- No linting/formatting tools are configured
- No CI/CD pipelines; tests run manually with pytest
- `conftest.py` at repo root adds the project root to `sys.path` for test imports
