# SEED4D Simulation Performance Optimizations

## Overview

This document describes the performance optimizations applied to the SEED4D data generation pipeline. All changes are backward-compatible. Benchmarks were run on the offline components (no CARLA required) to measure the improvements.

## Benchmark Configuration

- Resolution: 928x1600 (nuscenes) and 600x800 (sphere)
- Cameras per rig: 6 (nuscenes_old.json)
- Sensor types per camera: rgb + depth + semantic_segmentation + instance_segmentation

---

## 1. PNG Encoding: pypng `.tolist()` replaced with `cv2.imwrite`

**File:** `common/sensor.py`

The original code converted numpy arrays to Python lists (`.tolist()`) before passing them to `pypng`. This is extremely slow for large arrays because it creates millions of Python objects.

| Image Type | Resolution | Before | After (cv2) | Speedup |
|---|---|---|---|---|
| Depth (16-bit) | 928x1600 | 70ms | 22ms | **3.2x** |
| Depth (16-bit) | 600x800 | 19ms | 4ms | **4.8x** |
| Semantic Seg (8-bit) | 928x1600 | 43ms | 6ms | **6.7x** |
| Semantic Seg (8-bit) | 600x800 | 12ms | 2ms | **5.1x** |

**Per-step savings (6 cameras):** ~300ms for depth + semseg combined

---

## 2. Threaded Sensor Data Saving

**File:** `common/sensor.py` (`SensorManager._save_sensor_data`)

All sensor outputs (rgb, depth, semseg, instance_seg, lidar) were saved sequentially. Now uses `ThreadPoolExecutor` with up to 8 workers for parallel disk I/O.

| Scenario | Before (sequential) | After (threaded) | Speedup |
|---|---|---|---|
| 6 RGB images (928x1600) | 681ms | 125ms (6 workers) | **5.4x** |
| 18 mixed images (6 cam x 3 types) | 1,340ms | 559ms (6 workers) | **2.4x** |

**Per-step savings:** ~500-800ms depending on sensor count

---

## 3. Adaptive Sensor Polling

**File:** `common/sensor.py` (`SensorManager._save_sensor_data`)

The original code polled sensor readiness with a fixed `sleep(0.1)` (100ms). If a sensor became ready after 5ms, 95ms was wasted. Now uses exponential backoff starting at 1ms, doubling up to 50ms.

| Metric | Fixed 100ms | Adaptive (1ms-50ms) | Improvement |
|---|---|---|---|
| Avg wasted time per wait | 58.8ms | 22.2ms | **2.8x** less waste |

**Per-step savings:** ~35ms average

---

## 4. Cached Camera Intrinsics

**File:** `common/sensor.py` (`SensorManager._precompute_intrinsics`)

When cameras have heterogeneous FOVs, intrinsics were recalculated per-frame per-camera. Now pre-computed once at initialization and looked up from cache.

**Per-step savings:** ~0.075ms (negligible but removes redundant computation)

---

## 5. Cached `get_actors()` Calls

**File:** `generator.py`

The simulation loop called `world.get_actors()` 3 times per step for logging (total actors, sensors, vehicles). Now calls once and filters locally.

**Per-step savings:** ~5-10ms (CARLA IPC overhead)

---

## 6. CARLA Startup Exponential Backoff

**File:** `generator.py` (`Generator._launch_carla`)

The original code had a hardcoded `sleep(15)` before attempting to connect. Now uses exponential backoff: 2s, 4s, 8s, 16s, with a 120s total timeout.

| Scenario | Before | After | Savings |
|---|---|---|---|
| Fast hardware (CARLA ready in ~4s) | 15s + 1s retry | ~6s (2+4) | **~10s** |
| Normal hardware (CARLA ready in ~12s) | 15s + 1s retry | ~14s (2+4+8) | **~2s** |
| Slow hardware (CARLA ready in ~20s) | 15s + 5x1s retry | ~30s (2+4+8+16) | slightly slower but more robust |

**Per-config savings:** 2-13s depending on hardware

---

## 7. Parallel Config Processing

**File:** `main.py`

New `--parallel N` flag runs N generator subprocesses concurrently. Each worker gets a unique CARLA port (base 2000, spaced by 10) via `CARLA_PORT` environment variable.

```bash
# Sequential (default, same as before)
python3 main.py --config_dir config/dynamic/ --data_dir data

# Parallel with 4 workers
python3 main.py --config_dir config/dynamic/ --data_dir data --parallel 4
```

| Configs | Sequential | Parallel (4 workers) | Speedup |
|---|---|---|---|
| 10 configs x 15min each | 150 min | ~40 min | **~3.8x** |
| 50 configs x 15min each | 750 min | ~200 min | **~3.8x** |

**Note:** Each parallel worker launches its own CARLA instance, requiring proportionally more GPU/CPU memory.

---

## 8. BEV GIF Streaming to Disk

**File:** `common/vehicle.py`

BEV camera frames were accumulated as numpy arrays in a Python list, then converted to PIL images and saved as a GIF at the end. For 100 frames at 512x512, this consumed ~75MB of RAM.

Now frames are written as PNGs to a temporary directory immediately and assembled into a GIF at the end.

| Frames | Before (RAM) | After (disk) | Memory Savings |
|---|---|---|---|
| 10 frames | 7.5 MB | ~0 MB | 7.5 MB |
| 50 frames | 37.5 MB | ~0 MB | 37.5 MB |
| 100 frames | 75.0 MB | ~0 MB | 75.0 MB |

---

## Total Estimated Savings

### Per Simulation Step (nuscenes config, 6 cameras)

| Component | Savings |
|---|---|
| cv2 encoding | ~300ms |
| Threaded I/O | ~500ms |
| Adaptive polling | ~35ms |
| Cached intrinsics | <1ms |
| Cached get_actors | ~5ms |
| **Total per step** | **~840ms** |

### Per Config (single scenario)

| Component | Savings |
|---|---|
| Per-step savings x N steps | ~840ms x N |
| CARLA startup | 2-13s |

### Multi-Config Batch

| Component | Savings |
|---|---|
| `--parallel N` | Up to Nx speedup (bounded by hardware) |

---

## Profiling in Docker

For measuring CARLA-dependent code paths, set the environment variable:

```bash
SEED4D_PROFILE=1 python3 generator.py --config config/nuscenes.yaml --data_dir data --carla_executable /workspace/CarlaUE4.sh
```

This activates the instrumentation module (`benchmarks/instrument.py`) which monkey-patches key methods with timing wrappers and produces a JSON report at `benchmark_report.json`.

---

## Running Offline Benchmarks

```bash
uv run python3 -m pytest benchmarks/bench_offline.py -v -s
```

This measures all optimizable components without requiring CARLA.
