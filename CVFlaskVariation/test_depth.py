"""
Test script for depth estimation system.
Tests both pinhole model and MiDaS depth estimation.
"""

import cv2
import numpy as np
import logging
from app.utils.camera_calibration import PinholeCameraModel
from app.services.depth_estimator import DepthEstimator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_pinhole_model():
    """Test pinhole camera model distance estimation."""
    print("\n" + "="*60)
    print("TESTING PINHOLE CAMERA MODEL")
    print("="*60)

    # Create camera model (typical mobile camera settings)
    camera = PinholeCameraModel(focal_length=None, image_width=640, image_height=480)
    print(f"\nCamera focal length: {camera.focal_length:.1f} pixels")

    # Test cases: (bbox, class_name, expected_distance_range)
    test_cases = [
        # Large person bbox = close person
        ([100, 50, 300, 450], 'person', (1.5, 3.5), "Close person"),
        # Small person bbox = far person
        ([400, 200, 480, 280], 'person', (8.0, 15.0), "Far person"),
        # Car bbox
        ([50, 150, 350, 350], 'car', (3.0, 8.0), "Car"),
    ]

    for bbox, class_name, expected_range, description in test_cases:
        distance, confidence = camera.estimate_distance_with_confidence(bbox, class_name)

        print(f"\n{description}:")
        print(f"  Bbox: {bbox}")
        print(f"  Class: {class_name}")
        print(f"  Estimated distance: {distance:.2f}m" if distance else "  Could not estimate")
        print(f"  Confidence: {confidence:.2f}")
        print(f"  Expected range: {expected_range[0]:.1f}m - {expected_range[1]:.1f}m")

        if distance:
            in_range = expected_range[0] <= distance <= expected_range[1]
            print(f"  Status: {'✓ PASS' if in_range else '✗ FAIL - outside expected range'}")


def test_depth_estimator():
    """Test MiDaS depth estimator."""
    print("\n" + "="*60)
    print("TESTING MIDAS DEPTH ESTIMATOR")
    print("="*60)

    # Create depth estimator
    print("\nInitializing MiDaS model...")
    estimator = DepthEstimator(model_type='MiDaS_small', force_cpu=True)

    stats = estimator.get_stats()
    print(f"\nDepth Estimator Stats:")
    print(f"  Model loaded: {stats['model_loaded']}")
    print(f"  Model type: {stats['model_type']}")
    print(f"  Device: {stats['device']}")
    print(f"  Pinhole fallback available: {stats['pinhole_available']}")

    if not stats['model_loaded']:
        print("\n⚠ MiDaS model failed to load - will use pinhole fallback only")
        return

    # Create a test image (gradient to simulate depth)
    print("\nCreating synthetic test image...")
    test_image = np.zeros((480, 640, 3), dtype=np.uint8)
    # Create a gradient (darker = closer in depth maps)
    for i in range(480):
        test_image[i, :, :] = int(i / 480 * 255)

    # Test depth estimation
    print("\nRunning depth estimation...")
    depth_map = estimator.estimate_depth(test_image)

    if depth_map is not None:
        print(f"✓ Depth map generated: shape={depth_map.shape}")
        print(f"  Depth range: {depth_map.min():.2f} to {depth_map.max():.2f}")

        # Test sampling at specific bbox
        test_bbox = [200, 200, 400, 400]  # Center region
        depth_value = estimator.get_depth_at_bbox(depth_map, test_bbox)
        print(f"\n  Depth at bbox {test_bbox}: {depth_value:.2f}")
    else:
        print("✗ Failed to generate depth map")


def test_hybrid_estimation():
    """Test hybrid depth + pinhole estimation."""
    print("\n" + "="*60)
    print("TESTING HYBRID DEPTH ESTIMATION")
    print("="*60)

    # Create depth estimator with pinhole fallback
    print("\nInitializing hybrid estimator...")
    estimator = DepthEstimator(model_type='MiDaS_small', force_cpu=True)

    # Create test image
    test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

    # Test cases
    test_cases = [
        ([100, 50, 300, 450], 'person', "Large person bbox"),
        ([400, 200, 480, 280], 'person', "Small person bbox"),
        ([50, 150, 350, 350], 'car', "Car bbox"),
        ([200, 100, 250, 150], 'bicycle', "Bicycle bbox"),
    ]

    print("\nTesting distance estimation on different objects:\n")

    for bbox, class_name, description in test_cases:
        result = estimator.estimate_distance_with_depth(test_image, bbox, class_name)

        print(f"{description}:")
        print(f"  Bbox: {bbox}")
        print(f"  Class: {class_name}")
        print(f"  Distance: {result['distance']:.2f}m" if result['distance'] else "  Distance: Not available")
        print(f"  Confidence: {result['confidence']:.2f}")
        print(f"  Method: {result['method']}")
        print()


if __name__ == "__main__":
    print("="*60)
    print("DEPTH ESTIMATION SYSTEM TEST")
    print("="*60)

    try:
        # Test 1: Pinhole model
        test_pinhole_model()

        # Test 2: MiDaS depth estimator
        test_depth_estimator()

        # Test 3: Hybrid estimation
        test_hybrid_estimation()

        print("\n" + "="*60)
        print("ALL TESTS COMPLETED")
        print("="*60)

    except Exception as e:
        print(f"\n❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()
