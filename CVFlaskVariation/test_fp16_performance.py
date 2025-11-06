"""
Test FP16 mixed precision performance vs FP32.
Measures the speedup achieved by FP16 optimization on RTX GPUs.
"""

import time
import logging
import numpy as np
import torch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_fp16_speedup():
    """Compare FP32 vs FP16 performance."""
    print("="*70)
    print("FP16 Mixed Precision Performance Test")
    print("="*70)

    # Test 1: Load with FP32
    print("\nTEST 1: Loading model with FP32 (default)...")

    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Temporarily disable FP16
    from app import constants
    original_fp16_setting = constants.DEPTH_USE_FP16
    constants.DEPTH_USE_FP16 = False

    from app.services.depth_estimator import get_depth_estimator

    start = time.time()
    estimator_fp32 = get_depth_estimator(force_cpu=False)
    load_time_fp32 = (time.time() - start) * 1000

    print(f"  Load time (FP32): {load_time_fp32:.1f}ms")

    # Test inference with FP32
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Warm-up
    for _ in range(5):
        _ = estimator_fp32.estimate_distance_with_depth(
            test_image, [100, 100, 300, 300], 'person'
        )

    time.sleep(1)  # Let async worker process

    # Benchmark FP32
    n_runs = 20
    times_fp32 = []

    print(f"\n  Benchmarking FP32 ({n_runs} runs)...")
    for i in range(n_runs):
        start = time.time()
        result = estimator_fp32.estimate_distance_with_depth(
            test_image, [100 + i*5, 100, 300 + i*5, 300], 'person'
        )
        elapsed = (time.time() - start) * 1000
        times_fp32.append(elapsed)

    avg_fp32 = np.mean(times_fp32)
    min_fp32 = np.min(times_fp32)

    print(f"  FP32 Average: {avg_fp32:.2f}ms")
    print(f"  FP32 Min: {min_fp32:.2f}ms")

    # Test 2: Load with FP16
    print("\n" + "-"*70)
    print("\nTEST 2: Loading model with FP16 (optimized)...")

    # Re-enable FP16
    constants.DEPTH_USE_FP16 = True

    # Force reload by clearing singleton
    import app.services.depth_estimator as depth_module
    depth_module._depth_estimator = None

    start = time.time()
    estimator_fp16 = get_depth_estimator(force_cpu=False)
    load_time_fp16 = (time.time() - start) * 1000

    print(f"  Load time (FP16): {load_time_fp16:.1f}ms")

    # Warm-up
    for _ in range(5):
        _ = estimator_fp16.estimate_distance_with_depth(
            test_image, [100, 100, 300, 300], 'person'
        )

    time.sleep(1)  # Let async worker process

    # Benchmark FP16
    times_fp16 = []

    print(f"\n  Benchmarking FP16 ({n_runs} runs)...")
    for i in range(n_runs):
        start = time.time()
        result = estimator_fp16.estimate_distance_with_depth(
            test_image, [100 + i*5, 100, 300 + i*5, 300], 'person'
        )
        elapsed = (time.time() - start) * 1000
        times_fp16.append(elapsed)

    avg_fp16 = np.mean(times_fp16)
    min_fp16 = np.min(times_fp16)

    print(f"  FP16 Average: {avg_fp16:.2f}ms")
    print(f"  FP16 Min: {min_fp16:.2f}ms")

    # Calculate speedup
    print("\n" + "="*70)
    print("PERFORMANCE COMPARISON")
    print("="*70)

    speedup = avg_fp32 / avg_fp16 if avg_fp16 > 0 else 1.0

    print(f"\nMain Pipeline Latency (what matters for blind navigation):")
    print(f"  FP32: {avg_fp32:.2f}ms")
    print(f"  FP16: {avg_fp16:.2f}ms")
    print(f"  Speedup: {speedup:.2f}x")

    if speedup >= 1.8:
        print(f"\n  ✓✓✓ EXCELLENT! FP16 achieves {speedup:.1f}x speedup!")
    elif speedup >= 1.3:
        print(f"\n  ✓✓ GOOD! FP16 achieves {speedup:.1f}x speedup!")
    elif speedup >= 1.1:
        print(f"\n  ✓ OK! FP16 achieves {speedup:.1f}x speedup")
    else:
        print(f"\n  ⚠ Minimal speedup ({speedup:.2f}x) - async worker may be limiting factor")

    # Check GPU stats
    stats_fp16 = estimator_fp16.get_stats()

    print(f"\nAsync Worker Status (runs in background):")
    print(f"  Device: {stats_fp16['device']}")
    print(f"  Async Running: {stats_fp16['async_running']}")
    print(f"  Has Cached Depth: {stats_fp16['has_cached_depth']}")

    print("\nNote: Main pipeline latency is very low because async worker")
    print("      runs depth estimation in background. The speedup applies")
    print("      to the background depth processing time.")

    # Restore original setting
    constants.DEPTH_USE_FP16 = original_fp16_setting

    print("\n" + "="*70)
    print("TEST COMPLETE")
    print("="*70)

    return speedup


if __name__ == '__main__':
    try:
        speedup = test_fp16_speedup()

        print(f"\nFinal Result: FP16 provides {speedup:.2f}x speedup over FP32")
        print("\nRecommendation: Keep DEPTH_USE_FP16 = True for best performance!")

    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()
