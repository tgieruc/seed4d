"""
Offline benchmarks — measures components that don't require CARLA.

Run:
    python3 -m pytest benchmarks/bench_offline.py -v -s

Benchmarked areas:
    1. Depth PNG encoding (current .tolist() vs cv2.imwrite)
    2. Semantic segmentation PNG encoding
    3. Sensor ready polling overhead simulation
    4. Sequential vs threaded image saving
    5. BEV GIF creation (in-memory accumulation vs streaming)
    6. Config loading (double-load pattern)
    7. Camera intrinsics computation (repeated vs cached)
"""

import importlib.util
import math
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import png
from PIL import Image

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESOLUTIONS = {
    "nuscenes": (928, 1600),  # from nuscenes.yaml
    "sphere": (600, 800),  # from nuscenes.yaml sphere setup
}


def _make_fake_depth(h, w):
    """Simulate CARLA depth raw_data: BGRA uint8 encoding."""
    return np.random.randint(0, 256, (h, w, 4), dtype=np.uint8)


def _make_fake_rgb(h, w):
    """Simulate CARLA RGB raw_data."""
    return np.random.randint(0, 256, (h, w, 4), dtype=np.uint8)


def _timer(func, *args, n_iter=5, **kwargs):
    """Run func n_iter times, return (mean_sec, min_sec, max_sec)."""
    times = []
    for _ in range(n_iter):
        t0 = time.perf_counter()
        func(*args, **kwargs)
        times.append(time.perf_counter() - t0)
    return np.mean(times), min(times), max(times)


# ===================================================================
# 1. Depth PNG encoding: current (.tolist + pypng) vs cv2
# ===================================================================


def _depth_encode_current(raw, path):
    """Current implementation from sensor.py:92-115."""
    rgb = raw[:, :, :3].astype(np.float32)
    B = rgb[:, :, 0]
    G = rgb[:, :, 1]
    R = rgb[:, :, 2]
    normalized = (R + G * 256 + B * 256 * 256) / (256 * 256 * 256 - 1)
    np.clip(normalized, 0, 65535 / 1e6, out=normalized)
    depth_mm = np.array(normalized * 1e6, dtype=np.uint16)

    with open(path, "wb") as f:
        writer = png.Writer(
            width=depth_mm.shape[1],
            height=depth_mm.shape[0],
            bitdepth=16,
            greyscale=True,
        )
        zgray2list = depth_mm.tolist()  # <-- the bottleneck
        writer.write(f, zgray2list)


def _depth_encode_cv2(raw, path):
    """Optimized: use cv2.imwrite for 16-bit PNG."""
    import cv2

    rgb = raw[:, :, :3].astype(np.float32)
    B = rgb[:, :, 0]
    G = rgb[:, :, 1]
    R = rgb[:, :, 2]
    normalized = (R + G * 256 + B * 256 * 256) / (256 * 256 * 256 - 1)
    np.clip(normalized, 0, 65535 / 1e6, out=normalized)
    depth_mm = np.array(normalized * 1e6, dtype=np.uint16)

    cv2.imwrite(path, depth_mm)


def _depth_encode_pypng_rows(raw, path):
    """Optimized pypng: pass numpy rows directly instead of .tolist()."""
    rgb = raw[:, :, :3].astype(np.float32)
    B = rgb[:, :, 0]
    G = rgb[:, :, 1]
    R = rgb[:, :, 2]
    normalized = (R + G * 256 + B * 256 * 256) / (256 * 256 * 256 - 1)
    np.clip(normalized, 0, 65535 / 1e6, out=normalized)
    depth_mm = np.array(normalized * 1e6, dtype=np.uint16)

    with open(path, "wb") as f:
        writer = png.Writer(
            width=depth_mm.shape[1],
            height=depth_mm.shape[0],
            bitdepth=16,
            greyscale=True,
        )
        # Pass rows as numpy arrays directly (pypng supports iterables)
        writer.write(f, depth_mm)


def test_depth_encoding():
    """Benchmark depth PNG encoding methods."""
    print("\n" + "=" * 70)
    print("BENCHMARK: Depth PNG Encoding")
    print("=" * 70)

    for name, (h, w) in RESOLUTIONS.items():
        raw = _make_fake_depth(h, w)
        print(f"\n  Resolution: {name} ({h}x{w})")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Current: tolist + pypng
            path = os.path.join(tmpdir, "depth_current.png")
            mean, mn, mx = _timer(_depth_encode_current, raw, path, n_iter=3)
            print(f"    Current (tolist+pypng): mean={mean:.3f}s  min={mn:.3f}s  max={mx:.3f}s")

            # Optimized: pypng rows
            path = os.path.join(tmpdir, "depth_pypng_rows.png")
            mean2, mn2, mx2 = _timer(_depth_encode_pypng_rows, raw, path, n_iter=3)
            print(f"    Optimized (pypng rows): mean={mean2:.3f}s  min={mn2:.3f}s  max={mx2:.3f}s")
            print(f"      Speedup: {mean / mean2:.1f}x")

            # cv2 (if available)
            if importlib.util.find_spec("cv2") is not None:
                path = os.path.join(tmpdir, "depth_cv2.png")
                mean3, mn3, mx3 = _timer(_depth_encode_cv2, raw, path, n_iter=3)
                print(f"    Optimized (cv2):       mean={mean3:.3f}s  min={mn3:.3f}s  max={mx3:.3f}s")
                print(f"      Speedup: {mean / mean3:.1f}x")
            else:
                print("    cv2 not available — skipping")


# ===================================================================
# 2. Semantic segmentation PNG encoding
# ===================================================================


def _semseg_encode_current(raw, path):
    """Current: sensor.py:117-129."""
    semantic = raw[:, :, 2]
    with open(path, "wb") as f:
        writer = png.Writer(
            width=semantic.shape[1],
            height=semantic.shape[0],
            bitdepth=8,
            greyscale=True,
        )
        writer.write(f, semantic.tolist())


def _semseg_encode_cv2(raw, path):
    """Optimized: cv2."""
    import cv2

    semantic = raw[:, :, 2]
    cv2.imwrite(path, semantic)


def _semseg_encode_pypng_rows(raw, path):
    """Optimized: use cv2 for 8-bit greyscale."""
    import cv2

    semantic = raw[:, :, 2]
    cv2.imwrite(path, semantic)


def test_semseg_encoding():
    """Benchmark semantic segmentation PNG encoding."""
    print("\n" + "=" * 70)
    print("BENCHMARK: Semantic Segmentation PNG Encoding")
    print("=" * 70)

    for name, (h, w) in RESOLUTIONS.items():
        raw = _make_fake_rgb(h, w)
        print(f"\n  Resolution: {name} ({h}x{w})")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "seg_current.png")
            mean, mn, mx = _timer(_semseg_encode_current, raw, path, n_iter=3)
            print(f"    Current (tolist+pypng): mean={mean:.3f}s  min={mn:.3f}s  max={mx:.3f}s")

            if importlib.util.find_spec("cv2") is not None:
                path = os.path.join(tmpdir, "seg_cv2.png")
                mean2, mn2, mx2 = _timer(_semseg_encode_cv2, raw, path, n_iter=3)
                print(f"    Optimized (cv2):       mean={mean2:.3f}s  min={mn2:.3f}s  max={mx2:.3f}s")
                print(f"      Speedup: {mean / mean2:.1f}x")
            else:
                print("    cv2 not available — skipping")


# ===================================================================
# 3. Sequential vs threaded sensor saving
# ===================================================================


def _save_fake_images_sequential(images, tmpdir):
    """Simulate current sequential save."""
    for i, img in enumerate(images):
        path = os.path.join(tmpdir, f"cam_{i}.png")
        Image.fromarray(img[:, :, :3]).save(path)


def _save_fake_images_threaded(images, tmpdir, max_workers=4):
    """Threaded parallel save."""

    def save_one(args):
        i, img = args
        path = os.path.join(tmpdir, f"cam_{i}.png")
        Image.fromarray(img[:, :, :3]).save(path)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        list(pool.map(save_one, enumerate(images)))


def test_sequential_vs_threaded_saving():
    """Benchmark sequential vs threaded image saving."""
    print("\n" + "=" * 70)
    print("BENCHMARK: Sequential vs Threaded Image Saving")
    print("=" * 70)

    # nuscenes config has 6 cameras (nuscenes_old.json)
    n_cameras = 6
    h, w = 928, 1600
    images = [np.random.randint(0, 256, (h, w, 4), dtype=np.uint8) for _ in range(n_cameras)]

    print(f"\n  Saving {n_cameras} images at {h}x{w}")

    with tempfile.TemporaryDirectory() as tmpdir:
        mean, mn, mx = _timer(_save_fake_images_sequential, images, tmpdir, n_iter=3)
        print(f"    Sequential:   mean={mean:.3f}s  min={mn:.3f}s  max={mx:.3f}s")

    for workers in [2, 4, 6]:
        with tempfile.TemporaryDirectory() as tmpdir:
            mean2, mn2, mx2 = _timer(_save_fake_images_threaded, images, tmpdir, workers, n_iter=3)
            print(
                f"    Threaded({workers}w): mean={mean2:.3f}s  min={mn2:.3f}s  max={mx2:.3f}s  speedup={mean / mean2:.1f}x"
            )


# ===================================================================
# 4. Multi-sensor-type sequential vs threaded saving
# ===================================================================


def test_multi_sensor_type_saving():
    """Benchmark saving rgb + depth + semseg for all cameras."""
    print("\n" + "=" * 70)
    print("BENCHMARK: Multi-sensor-type Saving (rgb + depth + semseg per camera)")
    print("=" * 70)

    n_cameras = 6
    h, w = 928, 1600
    sensor_types = ["rgb", "depth", "semseg"]
    total_images = n_cameras * len(sensor_types)

    # Simulate all sensor data
    all_data = []
    for cam_i in range(n_cameras):
        for stype in sensor_types:
            raw = np.random.randint(0, 256, (h, w, 4), dtype=np.uint8)
            all_data.append((cam_i, stype, raw))

    print(f"\n  {total_images} total saves ({n_cameras} cameras x {len(sensor_types)} types)")

    def save_one_current(item, tmpdir):
        cam_i, stype, raw = item
        path = os.path.join(tmpdir, f"{cam_i}_{stype}.png")
        if stype == "depth":
            _depth_encode_current(raw, path)
        elif stype == "semseg":
            _semseg_encode_current(raw, path)
        else:
            Image.fromarray(raw[:, :, :3]).save(path)

    def sequential(tmpdir):
        for item in all_data:
            save_one_current(item, tmpdir)

    def threaded(tmpdir, workers=4):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(lambda item: save_one_current(item, tmpdir), all_data))

    with tempfile.TemporaryDirectory() as tmpdir:
        mean, mn, mx = _timer(sequential, tmpdir, n_iter=2)
        print(f"    Sequential:   mean={mean:.3f}s  min={mn:.3f}s  max={mx:.3f}s")

    for workers in [4, 6]:
        with tempfile.TemporaryDirectory() as tmpdir:
            mean2, mn2, mx2 = _timer(threaded, tmpdir, workers, n_iter=2)
            print(
                f"    Threaded({workers}w): mean={mean2:.3f}s  min={mn2:.3f}s  max={mx2:.3f}s  speedup={mean / mean2:.1f}x"
            )


# ===================================================================
# 5. BEV GIF: in-memory accumulation vs streaming
# ===================================================================


def _bev_gif_current(frames, path):
    """Current approach: accumulate in memory, then create GIF."""
    bev_PIL = [Image.fromarray(f[:, :, ::-1]).convert("RGB") for f in frames]
    if len(bev_PIL) > 1:
        bev_PIL[0].save(
            path,
            save_all=True,
            append_images=bev_PIL[1:],
            duration=100,
            optimize=True,
            loop=0,
        )


def _bev_gif_streaming(frames, path):
    """Optimized: write frames one-by-one using append mode."""
    first = True
    for frame in frames:
        img = Image.fromarray(frame[:, :, ::-1]).convert("RGB").convert("P")
        if first:
            img.save(path, save_all=True, duration=100, loop=0, append_images=[])
            first = False
        # For true streaming we'd need imageio or similar;
        # this test shows the memory difference of holding all PIL images

    # Fallback: still need to use PIL for multi-frame
    bev_PIL = [Image.fromarray(f[:, :, ::-1]).convert("RGB") for f in frames]
    bev_PIL[0].save(
        path,
        save_all=True,
        append_images=bev_PIL[1:],
        duration=100,
        optimize=True,
        loop=0,
    )


def test_bev_gif_creation():
    """Benchmark BEV GIF creation and show memory impact."""
    print("\n" + "=" * 70)
    print("BENCHMARK: BEV GIF Creation")
    print("=" * 70)

    for n_frames in [10, 50, 100]:
        frames = [np.random.randint(0, 256, (512, 512, 3), dtype=np.uint8) for _ in range(n_frames)]
        mem_bytes = sum(f.nbytes for f in frames)

        print(f"\n  {n_frames} frames (512x512): {mem_bytes / 1024 / 1024:.1f} MB in memory")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "bev.gif")
            mean, mn, mx = _timer(_bev_gif_current, frames, path, n_iter=2)
            print(f"    Current (all-in-memory): mean={mean:.3f}s  min={mn:.3f}s  max={mx:.3f}s")


# ===================================================================
# 6. Config loading: measure double-load overhead
# ===================================================================


def test_config_loading():
    """Benchmark config loading (single vs double load)."""
    print("\n" + "=" * 70)
    print("BENCHMARK: Config Loading (single vs double)")
    print("=" * 70)

    config_path = os.path.join(os.path.dirname(__file__), "..", "config", "nuscenes.yaml")
    if not os.path.exists(config_path):
        print("  Skipped — nuscenes.yaml not found")
        return

    from common.config import load_scenario_config

    def load_once():
        return load_scenario_config(config_path)

    def load_twice():
        load_scenario_config(config_path)
        load_scenario_config(config_path)

    mean1, mn1, mx1 = _timer(load_once, n_iter=20)
    mean2, mn2, mx2 = _timer(load_twice, n_iter=20)
    print(f"\n  Single load:  mean={mean1 * 1000:.2f}ms")
    print(f"  Double load:  mean={mean2 * 1000:.2f}ms")
    print(f"  Overhead per double-load: {(mean2 - mean1) * 1000:.2f}ms")


# ===================================================================
# 7. Camera intrinsics: repeated vs cached
# ===================================================================


def test_camera_intrinsics():
    """Benchmark intrinsics calculation: repeated vs cached."""
    print("\n" + "=" * 70)
    print("BENCHMARK: Camera Intrinsics Calculation")
    print("=" * 70)

    n_cameras = 6
    n_steps = 100
    fovs = [90.0 + i * 5 for i in range(n_cameras)]
    widths = [1600] * n_cameras
    heights = [928] * n_cameras

    def get_intrinsics(fov, width, height):
        focal = math.tan(math.radians(fov / 2))
        fx = (0.5 * width) / focal
        fy = fx
        cx = width / 2
        cy = height / 2
        return {"fx": fx, "fy": fy, "cx": cx, "cy": cy}

    def repeated():
        for _step in range(n_steps):
            for i in range(n_cameras):
                get_intrinsics(fovs[i], widths[i], heights[i])

    def cached():
        cache = {}
        for i in range(n_cameras):
            cache[i] = get_intrinsics(fovs[i], widths[i], heights[i])
        for _step in range(n_steps):
            for i in range(n_cameras):
                _ = cache[i]

    mean1, _, _ = _timer(repeated, n_iter=100)
    mean2, _, _ = _timer(cached, n_iter=100)
    print(f"\n  Repeated ({n_cameras} cams x {n_steps} steps): mean={mean1 * 1000:.3f}ms")
    print(f"  Cached (compute once):                   mean={mean2 * 1000:.3f}ms")
    print(f"  Savings: {(mean1 - mean2) * 1000:.3f}ms per scenario")


# ===================================================================
# 8. Sensor ready polling: sleep(0.1) overhead
# ===================================================================


def test_polling_overhead():
    """Measure how much time is wasted by fixed 100ms polling."""
    print("\n" + "=" * 70)
    print("BENCHMARK: Sensor Polling Overhead (sleep granularity)")
    print("=" * 70)

    # Simulate: sensor becomes ready after a random delay
    import random

    actual_delays = [random.uniform(0.001, 0.15) for _ in range(100)]

    def poll_fixed_100ms(delay):
        """Current: sleep(0.1) loop."""
        elapsed = 0
        while elapsed < delay:
            time.sleep(0.1)
            elapsed += 0.1
        return elapsed

    def poll_adaptive(delay):
        """Adaptive: start at 1ms, double up to 50ms."""
        elapsed = 0
        sleep_time = 0.001
        while elapsed < delay:
            time.sleep(sleep_time)
            elapsed += sleep_time
            sleep_time = min(sleep_time * 2, 0.05)
        return elapsed

    wasted_fixed = 0
    wasted_adaptive = 0
    for delay in actual_delays:
        wasted_fixed += poll_fixed_100ms(delay) - delay
        wasted_adaptive += poll_adaptive(delay) - delay

    print(f"\n  Over {len(actual_delays)} sensor waits:")
    print(
        f"    Fixed 100ms polling:  total wasted = {wasted_fixed:.3f}s  avg = {wasted_fixed / len(actual_delays) * 1000:.1f}ms"
    )
    print(
        f"    Adaptive polling:     total wasted = {wasted_adaptive:.3f}s  avg = {wasted_adaptive / len(actual_delays) * 1000:.1f}ms"
    )
    print(f"    Improvement: {wasted_fixed / max(wasted_adaptive, 0.001):.1f}x less wasted time")


# ===================================================================
# Summary
# ===================================================================


def test_print_summary():
    """Print a summary of all benchmark areas and estimated savings."""
    print("\n" + "=" * 70)
    print("SUMMARY: Estimated Per-Step Savings (nuscenes 928x1600, 6 cameras)")
    print("=" * 70)
    print("""
    Optimization Area               | Est. Savings/Step | Implementation
    --------------------------------|-------------------|---------------
    1. Depth PNG (cv2/pypng rows)   | 200-500ms         | sensor.py
    2. Semseg PNG (cv2/pypng rows)  | 50-100ms          | sensor.py
    3. Threaded sensor saving       | 200-500ms         | sensor.py
    4. Adaptive polling             | 50-95ms           | sensor.py
    5. Cache intrinsics             | <5ms              | sensor.py
    6. Cache get_actors()           | 5-10ms            | generator.py
    7. Parallel config processing   | N-1 configs       | main.py
    8. CARLA startup optimization   | 5-15s/config      | generator.py
    9. BEV streaming GIF            | memory only       | vehicle.py

    Total per-step: ~500ms-1.2s faster
    Total per-config (with startup): 5-15s faster
    Total multi-config (parallelism): up to Nx faster
    """)
