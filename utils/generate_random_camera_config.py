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
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
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
