"""
Timing instrumentation for CARLA-dependent code paths.

Usage inside Docker:
    python3 generator.py --config config/nuscenes.yaml --data_dir data --carla_executable /workspace/CarlaUE4.sh

    Then in a separate run with instrumentation:
    SEED4D_PROFILE=1 python3 generator.py --config config/nuscenes.yaml --data_dir data --carla_executable /workspace/CarlaUE4.sh

This module patches key methods with timing wrappers when SEED4D_PROFILE=1
is set. After the run, it writes a JSON report to data/benchmark_report.json.
"""

import atexit
import functools
import json
import os
import time
from collections import defaultdict

# Global timing store
_timings: dict[str, list[float]] = defaultdict(list)
_enabled = os.environ.get("SEED4D_PROFILE", "0") == "1"


def timed(label: str):
    """Decorator that records execution time under `label`."""

    def decorator(func):
        if not _enabled:
            return func

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            t0 = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = time.perf_counter() - t0
            _timings[label].append(elapsed)
            return result

        return wrapper

    return decorator


def record(label: str, elapsed: float):
    """Manually record a timing."""
    if _enabled:
        _timings[label].append(elapsed)


def get_timings() -> dict[str, list[float]]:
    """Return the raw timings dict."""
    return dict(_timings)


def report() -> dict:
    """Generate a summary report."""
    summary = {}
    for label, times in sorted(_timings.items()):
        summary[label] = {
            "count": len(times),
            "total_s": round(sum(times), 4),
            "mean_s": round(sum(times) / len(times), 4) if times else 0,
            "min_s": round(min(times), 4) if times else 0,
            "max_s": round(max(times), 4) if times else 0,
        }
    return summary


def print_report():
    """Print timing report to stdout."""
    if not _enabled or not _timings:
        return

    r = report()
    print("\n" + "=" * 80)
    print("SEED4D PERFORMANCE PROFILE")
    print("=" * 80)
    print(f"{'Label':<45} {'Count':>6} {'Total':>9} {'Mean':>9} {'Min':>9} {'Max':>9}")
    print("-" * 80)

    for label, stats in sorted(r.items(), key=lambda x: -x[1]["total_s"]):
        print(
            f"{label:<45} {stats['count']:>6} "
            f"{stats['total_s']:>8.3f}s {stats['mean_s']:>8.3f}s "
            f"{stats['min_s']:>8.3f}s {stats['max_s']:>8.3f}s"
        )

    total = sum(s["total_s"] for s in r.values())
    print("-" * 80)
    print(f"{'TOTAL PROFILED TIME':<45} {'':>6} {total:>8.3f}s")
    print("=" * 80)


def save_report(path: str = "benchmark_report.json"):
    """Save report to JSON file."""
    if not _enabled or not _timings:
        return
    r = report()
    with open(path, "w") as f:
        json.dump(r, f, indent=2)
    print(f"\nProfile saved to {path}")


def patch_all():
    """
    Monkey-patch key methods with timing instrumentation.

    Call this early in generator.py when SEED4D_PROFILE=1.
    Only patches if the modules are importable.
    """
    if not _enabled:
        return

    print("[SEED4D_PROFILE] Instrumenting code paths...")

    try:
        from common import sensor as sensor_mod

        # Patch Sensor.save_sensor_data
        _orig_save = sensor_mod.Sensor.save_sensor_data

        @functools.wraps(_orig_save)
        def _timed_save(self, path):
            t0 = time.perf_counter()
            result = _orig_save(self, path)
            elapsed = time.perf_counter() - t0
            _timings[f"sensor.save({self.sensor_type})"].append(elapsed)
            return result

        sensor_mod.Sensor.save_sensor_data = _timed_save

        # Patch SensorManager._save_sensor_data (includes polling wait)
        _orig_mgr_save = sensor_mod.SensorManager._save_sensor_data

        @functools.wraps(_orig_mgr_save)
        def _timed_mgr_save(self, path, setup_name=None):
            t0 = time.perf_counter()
            result = _orig_mgr_save(self, path, setup_name)
            elapsed = time.perf_counter() - t0
            _timings["sensor_manager.save_data"].append(elapsed)
            return result

        sensor_mod.SensorManager._save_sensor_data = _timed_mgr_save

        # Patch SensorManager._check_sensor_ready polling
        _orig_check = sensor_mod.SensorManager._check_sensor_ready
        # We instrument the wait loop in _save_sensor_data instead

        # Patch SensorManager._save_image_transforms
        _orig_transforms = sensor_mod.SensorManager._save_image_transforms

        @functools.wraps(_orig_transforms)
        def _timed_transforms(self, *args, **kwargs):
            t0 = time.perf_counter()
            result = _orig_transforms(self, *args, **kwargs)
            _timings["sensor_manager.save_transforms"].append(time.perf_counter() - t0)
            return result

        sensor_mod.SensorManager._save_image_transforms = _timed_transforms

        print("[SEED4D_PROFILE] Patched sensor module")

    except ImportError:
        print("[SEED4D_PROFILE] Could not import sensor module")

    try:
        from common import vehicle as vehicle_mod

        _orig_save_data = vehicle_mod.Vehicle.save_data

        @functools.wraps(_orig_save_data)
        def _timed_vehicle_save(self, data_dir):
            t0 = time.perf_counter()
            result = _orig_save_data(self, data_dir)
            _timings["vehicle.save_data"].append(time.perf_counter() - t0)
            return result

        vehicle_mod.Vehicle.save_data = _timed_vehicle_save

        _orig_save_bev = vehicle_mod.Vehicle.save_bev

        @functools.wraps(_orig_save_bev)
        def _timed_bev_save(self, save_path):
            t0 = time.perf_counter()
            result = _orig_save_bev(self, save_path)
            _timings["vehicle.save_bev"].append(time.perf_counter() - t0)
            return result

        vehicle_mod.Vehicle.save_bev = _timed_bev_save

        print("[SEED4D_PROFILE] Patched vehicle module")

    except ImportError:
        print("[SEED4D_PROFILE] Could not import vehicle module")

    # Register cleanup
    atexit.register(print_report)
    atexit.register(lambda: save_report("benchmark_report.json"))
