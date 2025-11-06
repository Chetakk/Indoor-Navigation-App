"""
Camera calibration utilities using pinhole camera model.
Provides fallback distance estimation when depth models are unavailable.
"""

import numpy as np
import logging
from ..constants import DEFAULT_FOCAL_LENGTH, KNOWN_OBJECT_HEIGHTS

logger = logging.getLogger(__name__)


class PinholeCameraModel:
    """
    Pinhole camera model for distance estimation.

    Uses the formula: distance = (known_height * focal_length) / bbox_pixel_height
    """

    def __init__(self, focal_length=None, image_width=640, image_height=480):
        """
        Initialize camera calibration.

        Args:
            focal_length: Camera focal length in pixels (auto-estimated if None)
            image_width: Image width in pixels
            image_height: Image height in pixels
        """
        self.image_width = image_width
        self.image_height = image_height

        if focal_length is None:
            # Estimate focal length assuming 60-degree horizontal FOV (typical mobile camera)
            self.focal_length = self._estimate_focal_length(image_width)
            logger.info(f"Auto-estimated focal length: {self.focal_length:.1f} pixels")
        else:
            self.focal_length = focal_length

    def _estimate_focal_length(self, image_width, horizontal_fov_degrees=60):
        """
        Estimate focal length from horizontal field of view.

        Args:
            image_width: Image width in pixels
            horizontal_fov_degrees: Horizontal field of view in degrees

        Returns:
            float: Estimated focal length in pixels
        """
        horizontal_fov_radians = np.radians(horizontal_fov_degrees)
        focal_length = image_width / (2 * np.tan(horizontal_fov_radians / 2))
        return focal_length

    def estimate_distance(self, bbox, class_name):
        """
        Estimate distance to object using pinhole camera model.

        Args:
            bbox: Bounding box in [x1, y1, x2, y2] format
            class_name: Object class name

        Returns:
            float: Estimated distance in meters, or None if cannot estimate
        """
        # Normalize class name to lowercase for case-insensitive lookup
        class_name_normalized = class_name.lower() if class_name else ''

        # Check if we have known height for this class
        if class_name_normalized not in KNOWN_OBJECT_HEIGHTS:
            logger.debug(f"No known height for class '{class_name}' - cannot estimate distance")
            return None

        known_height = KNOWN_OBJECT_HEIGHTS[class_name_normalized]

        # Calculate bbox dimensions
        x1, y1, x2, y2 = bbox
        bbox_width = x2 - x1
        bbox_height = y2 - y1

        # Sanity check
        if bbox_height <= 0:
            logger.warning(f"Invalid bbox height: {bbox_height}")
            return None

        # Apply pinhole camera formula
        # distance = (real_height * focal_length) / image_height
        distance = (known_height * self.focal_length) / bbox_height

        # Sanity check: distances should be reasonable (0.1m to 100m)
        if distance < 0.1 or distance > 100:
            logger.warning(f"Unrealistic distance estimate: {distance:.2f}m for {class_name}")
            return None

        logger.debug(f"Pinhole distance for {class_name}: {distance:.2f}m (bbox_h={bbox_height:.1f}px)")
        return distance

    def estimate_distance_with_confidence(self, bbox, class_name):
        """
        Estimate distance with confidence score.

        Args:
            bbox: Bounding box in [x1, y1, x2, y2] format
            class_name: Object class name

        Returns:
            tuple: (distance in meters, confidence score 0-1), or (None, 0.0)
        """
        distance = self.estimate_distance(bbox, class_name)

        if distance is None:
            return None, 0.0

        # Calculate confidence based on bbox quality
        x1, y1, x2, y2 = bbox
        bbox_width = x2 - x1
        bbox_height = y2 - y1
        bbox_area = bbox_width * bbox_height
        image_area = self.image_width * self.image_height

        # Confidence factors:
        # 1. Bbox should not be too small (< 1% of image) or too large (> 80%)
        area_ratio = bbox_area / image_area
        if area_ratio < 0.01:
            confidence = 0.3  # Low confidence for very small objects
        elif area_ratio > 0.8:
            confidence = 0.4  # Low confidence for very large objects (likely cropped)
        elif 0.05 <= area_ratio <= 0.5:
            confidence = 0.8  # High confidence for well-sized objects
        else:
            confidence = 0.6  # Medium confidence

        # 2. Aspect ratio should be reasonable for the object class
        aspect_ratio = bbox_width / bbox_height

        # Expected aspect ratios for common classes
        expected_aspect_ratios = {
            'person': (0.3, 0.8),  # People are taller than wide
            'car': (1.2, 2.0),  # Cars are wider than tall
            'bicycle': (0.8, 1.5),
            'motorcycle': (0.9, 1.8),
            'bus': (1.5, 3.0),
            'truck': (1.3, 2.5),
        }

        # Check aspect ratio using normalized class name
        class_name_normalized = class_name.lower() if class_name else ''
        if class_name_normalized in expected_aspect_ratios:
            min_ar, max_ar = expected_aspect_ratios[class_name_normalized]
            if min_ar <= aspect_ratio <= max_ar:
                # Good aspect ratio - no penalty
                pass
            else:
                # Bad aspect ratio - reduce confidence
                confidence *= 0.7
                logger.debug(f"Unusual aspect ratio {aspect_ratio:.2f} for {class_name}")

        return distance, confidence

    def update_image_dimensions(self, width, height):
        """
        Update image dimensions (e.g., when camera resolution changes).

        Args:
            width: New image width
            height: New image height
        """
        self.image_width = width
        self.image_height = height
        # Re-estimate focal length if it was auto-estimated
        self.focal_length = self._estimate_focal_length(width)
        logger.info(f"Updated camera dimensions to {width}x{height}, focal_length={self.focal_length:.1f}px")


# Global pinhole camera model instance
_pinhole_model = None


def get_pinhole_model(focal_length=None, image_width=640, image_height=480):
    """
    Get the global pinhole camera model instance (singleton).

    Args:
        focal_length: Camera focal length in pixels
        image_width: Image width in pixels
        image_height: Image height in pixels

    Returns:
        PinholeCameraModel: The model instance
    """
    global _pinhole_model
    if _pinhole_model is None:
        _pinhole_model = PinholeCameraModel(focal_length, image_width, image_height)
    return _pinhole_model
