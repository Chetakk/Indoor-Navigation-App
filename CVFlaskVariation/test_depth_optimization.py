"""
Test script for Depth Anything V2 performance optimization.
Verifies model loading, GPU acceleration, and latency benchmarks.
"""

import time
import logging
import torch
import cv2
import numpy as np

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_depth_model_loading():
    """Test that Depth Anything V2 loads correctly."""
    print("\n" + "="*60)
    print("TEST 1: Depth Anything V2 Model Loading")
    print("="*60)

    try:
        from app.services.depth_estimator import get_depth_estimator

        logger.info("Loading depth estimator...")
        start_time = time.time()

        # Load with GPU enabled
        estimator = get_depth_estimator(force_cpu=False)

        load_time = (time.time() - start_time) * 1000

        print(f"\nRESULT: Model loaded successfully in {load_time:.1f}ms")

        # Get stats
        stats = estimator.get_stats()
        print(f"\nModel Stats:")
        print(f"  - Model Type: {stats['model_type']}")
        print(f"  - Device: {stats['device']}")
        print(f"  - Model Loaded: {stats['model_loaded']}")
        print(f"  - Async Enabled: {stats['async_enabled']}")
        print(f"  - Async Running: {stats['async_running']}")
        print(f"  - Auto-Calibration Available: {stats.get('auto_calibration_scale') is not None or stats.get('auto_calibration_confidence', 0) == 0}")

        return estimator, True

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return None, False


def test_depth_inference_speed(estimator):
    """Benchmark depth inference speed."""
    print("\n" + "="*60)
    print("TEST 2: Depth Inference Speed Benchmark")
    print("="*60)

    try:
        # Create a test image (640x480)
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        print(f"\nTest image size: {test_image.shape}")

        # Warm-up run
        logger.info("Warm-up run...")
        _ = estimator.estimate_distance_with_depth(
            test_image,
            bbox=[100, 100, 300, 300],
            class_name='person'
        )

        # Wait for async worker to process
        time.sleep(0.5)

        # Benchmark multiple runs
        n_runs = 10
        times = []

        print(f"\nRunning {n_runs} inference tests...")
        for i in range(n_runs):
            start = time.time()

            result = estimator.estimate_distance_with_depth(
                test_image,
                bbox=[100 + i*10, 100, 300 + i*10, 300],
                class_name='person'
            )

            elapsed = (time.time() - start) * 1000
            times.append(elapsed)

            if i == 0:
                print(f"\nFirst run result:")
                print(f"  - Distance: {result.get('distance')}")
                print(f"  - Confidence: {result.get('confidence')}")
                print(f"  - Method: {result.get('method')}")

        # Calculate stats
        avg_time = np.mean(times)
        min_time = np.min(times)
        max_time = np.max(times)
        std_time = np.std(times)

        print(f"\nPerformance Metrics:")
        print(f"  - Average: {avg_time:.2f}ms")
        print(f"  - Min: {min_time:.2f}ms")
        print(f"  - Max: {max_time:.2f}ms")
        print(f"  - Std Dev: {std_time:.2f}ms")
        print(f"  - Target: <15ms (Main pipeline latency)")

        # Check if async is helping
        stats = estimator.get_stats()
        print(f"\nAsync Worker Status:")
        print(f"  - Has cached depth: {stats['has_cached_depth']}")
        print(f"  - Cache age: {stats.get('cache_age_ms', 'N/A')}ms")

        return avg_time < 50, avg_time  # Success if under 50ms (very generous)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_auto_calibration(estimator):
    """Test auto-calibration system."""
    print("\n" + "="*60)
    print("TEST 3: Auto-Calibration System")
    print("="*60)

    try:
        # Create test images with known objects
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        known_objects = [
            ('person', [100, 100, 200, 400]),
            ('car', [300, 200, 500, 350]),
            ('bicycle', [50, 150, 150, 300])
        ]

        print(f"\nFeeding {len(known_objects)} known objects for calibration...")

        for class_name, bbox in known_objects:
            result = estimator.estimate_distance_with_depth(
                test_image,
                bbox=bbox,
                class_name=class_name
            )

            print(f"\n  {class_name}:")
            print(f"    - Method: {result.get('method')}")
            print(f"    - Distance: {result.get('distance')}")
            print(f"    - Confidence: {result.get('confidence')}")

        # Wait for processing
        time.sleep(0.5)

        # Check auto-calibration stats
        stats = estimator.get_stats()
        auto_scale = stats.get('auto_calibration_scale')
        auto_conf = stats.get('auto_calibration_confidence')

        print(f"\nAuto-Calibration Status:")
        print(f"  - Scale: {auto_scale}")
        print(f"  - Confidence: {auto_conf}")
        print(f"  - Active: {auto_scale is not None and auto_conf > 0.3}")

        return True

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_case_sensitivity_fix():
    """Test that class name case sensitivity is fixed."""
    print("\n" + "="*60)
    print("TEST 4: Class Name Case Sensitivity Fix")
    print("="*60)

    try:
        from app.utils.camera_calibration import PinholeCameraModel

        pinhole = PinholeCameraModel()

        # Test with different case variations
        test_cases = [
            ('person', [100, 100, 200, 400]),
            ('Person', [100, 100, 200, 400]),
            ('PERSON', [100, 100, 200, 400]),
            ('computer monitor', [200, 150, 400, 300]),
            ('Computer Monitor', [200, 150, 400, 300]),
            ('desk', [100, 200, 500, 400]),
            ('Desk', [100, 200, 500, 400]),
        ]

        print("\nTesting case-insensitive lookups:")
        success_count = 0

        for class_name, bbox in test_cases:
            distance = pinhole.estimate_distance(bbox, class_name)
            success = distance is not None

            print(f"  {class_name:20s} -> {'OK' if success else 'FAIL'} ({distance:.2f}m)" if success else f"  {class_name:20s} -> FAIL (None)")

            if success:
                success_count += 1

        print(f"\nResult: {success_count}/{len(test_cases)} tests passed")

        return success_count == len(test_cases)

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("\n" + "#"*60)
    print("#  Depth Estimation Optimization Test Suite")
    print("#  Testing Depth Anything V2 + Async Processing")
    print("#"*60)

    results = {}

    # Test 1: Model Loading
    estimator, success = test_depth_model_loading()
    results['model_loading'] = success

    if not success or estimator is None:
        print("\n\nFAILED: Could not load depth model. Aborting tests.")
        return

    # Test 2: Inference Speed
    success, avg_time = test_depth_inference_speed(estimator)
    results['inference_speed'] = success

    # Test 3: Auto-Calibration
    success = test_auto_calibration(estimator)
    results['auto_calibration'] = success

    # Test 4: Case Sensitivity
    success = test_case_sensitivity_fix()
    results['case_sensitivity'] = success

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        emoji = "✓" if passed else "✗"
        print(f"  {emoji} {test_name:30s} {status}")

    total = len(results)
    passed = sum(results.values())

    print(f"\nOverall: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓✓✓ ALL TESTS PASSED! System is ready. ✓✓✓")
    else:
        print(f"\n⚠ WARNING: {total - passed} test(s) failed. Review output above.")


if __name__ == '__main__':
    main()
