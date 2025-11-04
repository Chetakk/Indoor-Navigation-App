"""
Image processing utilities for rotation correction and EXIF handling.
"""

import logging
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# EXIF orientation tag
ORIENTATION = 274


def fix_image_orientation(image):
    """
    Fix image orientation based on EXIF data.
    This handles phone rotation issues.

    Args:
        image: PIL Image object

    Returns:
        PIL Image: Image with corrected orientation
    """
    try:
        # Get EXIF data
        exif = image._getexif()
        if exif is not None:
            orientation = exif.get(ORIENTATION)
            if orientation:
                if orientation == 2:
                    # Horizontal flip
                    image = image.transpose(Image.FLIP_LEFT_RIGHT)
                elif orientation == 3:
                    # 180 degree rotation
                    image = image.rotate(180, expand=True)
                elif orientation == 4:
                    # Vertical flip
                    image = image.transpose(Image.FLIP_TOP_BOTTOM)
                elif orientation == 5:
                    # Horizontal flip + 90 degree rotation
                    image = image.transpose(Image.FLIP_LEFT_RIGHT).rotate(90, expand=True)
                elif orientation == 6:
                    # 90 degree rotation
                    image = image.rotate(270, expand=True)
                elif orientation == 7:
                    # Horizontal flip + 270 degree rotation
                    image = image.transpose(Image.FLIP_LEFT_RIGHT).rotate(270, expand=True)
                elif orientation == 8:
                    # 270 degree rotation
                    image = image.rotate(90, expand=True)

                logger.info(f"Applied EXIF orientation correction: {orientation}")

        return image
    except (AttributeError, KeyError, TypeError) as e:
        logger.debug(f"No EXIF orientation data found or error processing: {e}")
        return image


def get_rotation_from_gyroscope(orientation_data):
    """
    Determine rotation needed based on device orientation data.

    Args:
        orientation_data: Dictionary containing:
            - alpha: rotation around z-axis (compass heading) 0-360°
            - beta: rotation around x-axis (front-to-back tilt) -180° to 180°
            - gamma: rotation around y-axis (left-to-right tilt) -90° to 90°
            - screen_orientation: screen.orientation.angle (0, 90, 180, 270)

    Returns:
        int: Rotation angle in degrees (0, 90, 180, or 270)
    """
    try:
        # Use screen orientation as primary indicator (most reliable)
        if 'screen_orientation' in orientation_data:
            screen_angle = orientation_data['screen_orientation']
            logger.info(f"Screen orientation angle: {screen_angle}°")

            # Map screen orientation to image rotation needed
            if screen_angle == 0:
                return 0  # Portrait, no rotation needed
            elif screen_angle == 90:
                return 270  # Landscape left, rotate 270° to correct
            elif screen_angle == 180:
                return 180  # Portrait upside down
            elif screen_angle == 270:
                return 90   # Landscape right, rotate 90° to correct

        # Fallback to gyroscope gamma (left-right tilt) if no screen orientation
        if 'gamma' in orientation_data:
            gamma = orientation_data['gamma']
            logger.info(f"Gyroscope gamma (tilt): {gamma}°")

            # Determine orientation based on tilt
            if abs(gamma) < 45:
                return 0    # Portrait
            elif gamma > 45:
                return 270  # Landscape left
            elif gamma < -45:
                return 90   # Landscape right

        # Additional fallback using beta (front-back tilt)
        if 'beta' in orientation_data:
            beta = orientation_data['beta']
            if abs(beta) > 135:  # Phone held upside down
                return 180

        logger.warning("No reliable orientation data found")
        return 0

    except Exception as e:
        logger.error(f"Error processing gyroscope data: {e}")
        return 0


def apply_rotation_correction(image_bgr, rotation_degrees):
    """
    Apply rotation correction to image based on degrees.

    Args:
        image_bgr: OpenCV image in BGR format
        rotation_degrees: Degrees to rotate (0, 90, 180, or 270)

    Returns:
        numpy.ndarray: Rotated image
    """
    if rotation_degrees == 0:
        return image_bgr
    elif rotation_degrees == 90:
        return cv2.rotate(image_bgr, cv2.ROTATE_90_CLOCKWISE)
    elif rotation_degrees == 180:
        return cv2.rotate(image_bgr, cv2.ROTATE_180)
    elif rotation_degrees == 270:
        return cv2.rotate(image_bgr, cv2.ROTATE_90_COUNTERCLOCKWISE)
    else:
        logger.warning(f"Unsupported rotation: {rotation_degrees}°")
        return image_bgr


def detect_and_fix_rotation(image_np, model, confidence_threshold=0.3):
    """
    Detect if image needs rotation based on aspect ratio and content.
    This is a fallback when gyroscope data isn't available.

    Args:
        image_np: Image as numpy array
        model: YOLO model for detection testing
        confidence_threshold: Confidence threshold for test detection

    Returns:
        tuple: (rotated_image, rotation_applied_degrees)
    """
    height, width = image_np.shape[:2]

    # If width is much smaller than height, likely rotated
    if width < height * 0.75:  # Threshold for detecting portrait mode
        logger.info("Detected likely rotated image, checking orientation...")

        # Try different rotations and see which gives better detection
        original = image_np.copy()
        rotated_90 = cv2.rotate(original, cv2.ROTATE_90_CLOCKWISE)
        rotated_270 = cv2.rotate(original, cv2.ROTATE_90_COUNTERCLOCKWISE)

        # Quick detection test on smaller images for speed
        test_size = (320, 240)
        orig_small = cv2.resize(original, test_size)
        rot90_small = cv2.resize(rotated_90, test_size)
        rot270_small = cv2.resize(rotated_270, test_size)

        # Run quick detection on each
        try:
            orig_results = model(orig_small, verbose=False, conf=confidence_threshold)
            rot90_results = model(rot90_small, verbose=False, conf=confidence_threshold)
            rot270_results = model(rot270_small, verbose=False, conf=confidence_threshold)

            # Count detections for each orientation
            orig_count = len(orig_results[0].boxes) if orig_results[0].boxes is not None else 0
            rot90_count = len(rot90_results[0].boxes) if rot90_results[0].boxes is not None else 0
            rot270_count = len(rot270_results[0].boxes) if rot270_results[0].boxes is not None else 0

            logger.info(f"Detection counts - Original: {orig_count}, 90°: {rot90_count}, 270°: {rot270_count}")

            # Choose orientation with most detections
            if rot90_count > orig_count and rot90_count >= rot270_count:
                logger.info("Auto-correcting with 90° clockwise rotation")
                return rotated_90, 90
            elif rot270_count > orig_count and rot270_count > rot90_count:
                logger.info("Auto-correcting with 270° clockwise rotation")
                return rotated_270, 270

        except Exception as e:
            logger.error(f"Error in rotation detection: {e}")

    return image_np, 0


def resize_image_for_inference(image, max_dimension=640):
    """
    Resize image if too large to speed up inference.

    Args:
        image: OpenCV image
        max_dimension: Maximum width or height

    Returns:
        tuple: (resized_image, scale_factor) or (original_image, 1.0) if no resize needed
    """
    height, width = image.shape[:2]

    if max(height, width) > max_dimension:
        scale = max_dimension / max(height, width)
        new_width = int(width * scale)
        new_height = int(height * scale)
        logger.info(f"Resizing image from {width}x{height} to {new_width}x{new_height} for faster inference")
        resized = cv2.resize(image, (new_width, new_height))
        return resized, scale

    return image, 1.0
