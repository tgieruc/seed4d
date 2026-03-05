# Copyright (C) 2025 co-pace GmbH (subsidiary of Continental AG).
# Licensed under the BSD-3-Clause License.
# @author: Marius Kästingschäfer and Théo Gieruc
# ==============================================================================

import argparse
import logging
import os
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import psutil
import yaml
from tqdm import tqdm

logger = logging.getLogger(__name__)


def data_exists(config_path, data_dir):
    config = yaml.safe_load(Path(config_path).read_text())

    return os.path.exists(
        os.path.join(
            data_dir,
            config["map"],
            config["weather"],
            config["vehicle"],
            f"spawn_point_{config['spawn_point'][0]}",
        )
    )


def _run_single_config(config_path, args, carla_port=2000):
    """
    Run generator + post-processing for a single config.
    Returns (config_path, success: bool).
    Each worker uses a different CARLA port to avoid conflicts.
    """
    cwd = "/seed4d/utils"

    # Run generator with assigned port
    process = psutil.Popen(
        [
            "python3",
            "generator.py",
            "--config",
            config_path,
            "--data_dir",
            args.data_dir,
            "--carla_executable",
            args.carla_executable,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Set CARLA port via environment variable for parallel runs
        env={**os.environ, "CARLA_PORT": str(carla_port)},
    )

    process.wait()
    if process.returncode != 0:
        return (config_path, False)

    # Load config once for post-processing paths
    config = yaml.safe_load(Path(config_path).read_text())
    save_path = os.path.join(
        args.data_dir,
        config["map"],
        config["weather"],
        config["vehicle"],
        "spawn_point_" + str(config["spawn_point"][0]),
    )

    # Run post-processing steps sequentially (they depend on generator output)
    if args.normalize_coords:
        command = [
            "python3",
            "/seed4d/utils/generate_normalized_coordinates.py",
            "--data_dir",
            save_path,
            "--elements",
            "nuscenes",
        ]
        subprocess.Popen(command, cwd=cwd).wait()

    if args.vehicle_masks:
        command = [
            "python3",
            "/seed4d/utils/generate_masks.py",
            "--data_dir",
            save_path + "/",
        ]
        subprocess.Popen(command, cwd=cwd).wait()

    if args.combine_transforms:
        command = [
            "python3",
            "/seed4d/utils/generate_single_transforms.py",
            "--data_dir",
            save_path + "/",
        ]
        subprocess.Popen(command, cwd=cwd).wait()

    if args.map:
        command = ["python3", "/seed4d/utils/generate_map.py", "--data_dir", save_path + "/"]
        subprocess.Popen(command, cwd=cwd).wait()

    return (config_path, True)


def main(args):
    """
    Run the generator for all the config files in the specified directory.
    Supports parallel execution when --parallel > 1.

    Parameters:
        args (argparse.Namespace): The parsed arguments from the command line.
    """

    fails = []
    if args.config:
        config_files = [args.config]
    elif args.config_dir:
        config_files = [
            os.path.join(args.config_dir, f) for f in sorted(os.listdir(args.config_dir)) if f.endswith(".yaml")
        ]

    # Filter already-completed configs
    if args.only_missing:
        config_files = [c for c in config_files if not data_exists(c, args.data_dir)]

    logger.info("Loaded %d config files (%d after filtering)", len(config_files), len(config_files))

    if args.parallel > 1 and len(config_files) > 1:
        # Parallel execution: each worker gets a unique CARLA port
        n_workers = min(args.parallel, len(config_files))
        logger.info("Running %d configs in parallel with %d workers", len(config_files), n_workers)

        base_port = 2000
        with ProcessPoolExecutor(max_workers=n_workers) as executor:
            futures = {}
            for i, config_path in enumerate(config_files):
                port = base_port + (i % n_workers) * 10  # space ports by 10
                future = executor.submit(_run_single_config, config_path, args, port)
                futures[future] = config_path

            progress = tqdm(total=len(config_files), desc="Generating data")
            for future in as_completed(futures):
                config_path, success = future.result()
                if not success:
                    fails.append(config_path)
                progress.update(1)
            progress.close()
    else:
        # Sequential execution (original behavior)
        for config_path in tqdm(config_files, total=len(config_files)):
            _, success = _run_single_config(config_path, args, carla_port=2000)
            if not success:
                fails.append(config_path)

    if len(fails) > 0:
        logger.error("Failed to generate data for %d configs", len(fails))

        os.makedirs(os.path.join(args.data_dir, "failed_configs"), exist_ok=True)
        for i, fail_path in enumerate(fails):
            with open(fail_path) as src:
                config_data = yaml.safe_load(src)
            with open(os.path.join(args.data_dir, "failed_configs", f"config_{i}.yaml"), "w") as f:
                yaml.dump(config_data, f)


def str2bool(v):
    if isinstance(v, bool):
        return v
    if v.lower() in ("yes", "true", "t", "y", "1"):
        return True
    elif v.lower() in ("no", "false", "f", "n", "0"):
        return False
    else:
        raise argparse.ArgumentTypeError("Boolean value expected.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default=None, help=".yaml config file path")
    parser.add_argument("--config_dir", type=str, default=None, help="Directory of .yaml config files")
    parser.add_argument(
        "--only_missing",
        action="store_true",
        default=False,
        help="Only generate data for configs that don't already have data",
    )
    parser.add_argument(
        "--carla_executable", type=str, default="/workspace/CarlaUE4.sh", help="Location of the CarlaUE4.sh executable"
    )
    parser.add_argument("--data_dir", type=str, default="data")
    parser.add_argument(
        "--normalize_coords",
        type=str2bool,
        default=True,
        help="Whether to generate normalized coordinates",
    )
    parser.add_argument(
        "--vehicle_masks",
        type=str2bool,
        default=True,
        help="Generate vehicle masks + vehicle only images",
    )
    parser.add_argument(
        "--combine_transforms",
        type=str2bool,
        default=True,
        help="Write a single transform across timepoints",
    )
    parser.add_argument(
        "--map",
        type=str2bool,
        default=True,
        help="Creates a map overview and a single file containing all positions",
    )
    parser.add_argument(
        "--quiet",
        type=str2bool,
        default=True,
        help="Disable progress bar and all logging except for errors",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help="Number of parallel generator workers (each needs its own CARLA instance). Default: 1 (sequential)",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR if args.quiet else logging.INFO)

    logger.info("Arguments: %s", args)

    assert args.config or args.config_dir, "Please specify either a config file or a directory of config files"

    main(args)
