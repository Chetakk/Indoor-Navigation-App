"""
Object detection routes.
"""

import logging
import time
import base64
import cv2
import numpy as np
from io import BytesIO
from PIL import Image
from flask import Blueprint, jsonify, request, session
from ..services.yolo_detector import get_detector
from ..services.object_tracker import get_tracking_manager
from ..services.collision_detector import calculate_movement, predict_collision
from ..utils.filtering import (
    is_class_blacklisted,
    normalize_class_name,
    deduplicate_same_class_detections,
    filter_detections_by_confidence
)
from ..utils.image_processing import (
    get_rotation_from_gyroscope,
    apply_rotation_correction,
    resize_image_for_inference
)
from ..constants import MAX_IMAGE_DIMENSION

logger = logging.getLogger(__name__)

bp = Blueprint('detection', __name__)


@bp.route('/detect_image', methods=['POST'])
def detect_image():
    """Process image from browser and return detection results with tracking."""
    start_time = time.time()
    try:
        logger.info("📥 Received detection request")
        logger.info(f"Request headers: {dict(request.headers)}")

        data = request.get_json()
        logger.info(f"Request data keys: {data.keys() if data else 'None'}")

        if not data or 'image' not in data:
            logger.error("❌ No image data in request")
            response = jsonify({'error': 'No image data provided', 'success': False})
            logger.info("📤 Sending error response for missing image")
            return response

        # Get or create session ID for tracking continuity
        if 'session_id' not in session:
            session['session_id'] = str(time.time())
        session_id = session['session_id']

        # Check if tracking is enabled (default: True)
        tracking_enabled = data.get('tracking_enabled', True)

        # Decode base64 image from browser
        image_data = data['image'].split(',')[1]  # Remove data:image/jpeg;base64,
        image_bytes = base64.b64decode(image_data)
        image = Image.open(BytesIO(image_bytes))

        # Convert to numpy array
        image_np = np.array(image)

        # Convert RGB to BGR for OpenCV/YOLO
        image_bgr = cv2.cvtColor(image_np, cv2.COLOR_RGB2BGR)

        # Apply gyroscope-based rotation if available
        rotation_applied = 0
        orientation_source = "none"

        if 'orientation' in data and data['orientation']:
            rotation_applied = get_rotation_from_gyroscope(data['orientation'])
            orientation_source = "gyroscope"
            logger.info(f"Using gyroscope data, applying {rotation_applied}° rotation")

            # Apply the rotation correction
            if rotation_applied != 0:
                image_bgr = apply_rotation_correction(image_bgr, rotation_applied)
        else:
            logger.info("No orientation data provided - image will be processed as-is")

        # Update image dimensions after rotation
        if rotation_applied != 0:
            # Convert back to RGB for size reporting
            image_rgb_corrected = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
            image_np = image_rgb_corrected

        # Run YOLO detection with optimized settings for real-time performance
        logger.info(f"🔍 Running YOLO detection on image shape: {image_bgr.shape}")
        logger.info(f"🔍 Image dtype: {image_bgr.dtype}, min: {image_bgr.min()}, max: {image_bgr.max()}")

        # Optimize: Resize image if too large to speed up inference
        image_bgr, scale = resize_image_for_inference(image_bgr, MAX_IMAGE_DIMENSION)

        try:
            # Run inference
            inference_start = time.time()

            detector = get_detector()
            device_info = detector.get_model_info().get('device', 'unknown')
            logger.info(f"🔍 Calling model() with device: {device_info}")

            results = detector.detect(image_bgr)

            inference_time = (time.time() - inference_start) * 1000
            logger.info(f"🔍 model() returned in {inference_time:.1f}ms")

        except Exception as e:
            logger.error(f"❌ Error during model inference: {e}", exc_info=True)
            raise

        logger.info(f"✅ Detection complete, processing {len(results)} result objects...")

        # Extract detection data and filter blacklisted classes
        raw_detections = []
        filtered_count = 0

        for r in results:
            boxes = r.boxes
            if boxes is not None:
                for box in boxes:
                    class_id = int(box.cls[0])
                    class_name = detector.model.names[class_id]

                    # Skip blacklisted classes
                    if is_class_blacklisted(class_name):
                        filtered_count += 1
                        logger.debug(f"Filtered out blacklisted class: {class_name}")
                        continue

                    # Normalize class name (e.g., man/woman/face -> person)
                    normalized_class_name = normalize_class_name(class_name)

                    # Ensure we have valid bounding box coordinates
                    bbox_coords = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                    confidence = float(box.conf[0])

                    # Format for DeepSORT: ([left, top, width, height], confidence, class_name)
                    x1, y1, x2, y2 = bbox_coords
                    width = x2 - x1
                    height = y2 - y1

                    raw_detections.append({
                        'bbox': [x1, y1, width, height],  # LTWH format for tracker
                        'bbox_xyxy': bbox_coords,  # Keep original format too
                        'confidence': confidence,
                        'class_name': normalized_class_name,  # Use normalized name
                        'class_id': class_id
                    })

        # Filter by confidence threshold FIRST (before dedup)
        raw_detections_before_filtering = len(raw_detections)
        raw_detections = filter_detections_by_confidence(raw_detections, min_confidence=0.3)
        confidence_filtered = raw_detections_before_filtering - len(raw_detections)
        if confidence_filtered > 0:
            logger.info(f"🎯 Confidence filtering removed {confidence_filtered} low-confidence detections (< 30%)")

        # Deduplicate detections of the SAME class that overlap
        raw_detections_before_dedup = len(raw_detections)
        raw_detections = deduplicate_same_class_detections(raw_detections, iou_threshold=0.5)
        dedup_removed = raw_detections_before_dedup - len(raw_detections)
        if dedup_removed > 0:
            logger.info(f"🔄 Deduplication removed {dedup_removed} overlapping same-class detections")

        # Apply object tracking if enabled
        tracked_objects = []
        if tracking_enabled and len(raw_detections) > 0:
            tracking_manager = get_tracking_manager()

            # Prepare detections for DeepSORT (bbox in ltwh format, confidence, class)
            deepsort_input = [
                (det['bbox'], det['confidence'], det['class_name'])
                for det in raw_detections
            ]

            # Update tracker with current frame
            tracks = tracking_manager.update_tracks(session_id, deepsort_input, image_bgr)

            # Process tracked objects
            for track in tracks:
                track_id = track.track_id
                ltrb = track.to_ltrb()  # Get bounding box in [left, top, right, bottom] format

                # Get detection info
                det_class = track.det_class if hasattr(track, 'det_class') else 'unknown'
                det_conf = track.det_conf if hasattr(track, 'det_conf') else 0.0

                # Calculate center point for trajectory
                center_x = (ltrb[0] + ltrb[2]) / 2
                center_y = (ltrb[1] + ltrb[3]) / 2

                # Get trajectory (last N positions)
                trajectory = tracking_manager.get_track_history(session_id, track_id)

                # Calculate movement direction and speed
                movement_info = calculate_movement(trajectory)

                # Predict collision
                collision_info = predict_collision(
                    (center_x, center_y),
                    movement_info,
                    image_np.shape[1],
                    image_np.shape[0]
                )

                tracked_objects.append({
                    'track_id': track_id,
                    'class_name': det_class,
                    'confidence': det_conf,
                    'bbox': [ltrb[0], ltrb[1], ltrb[2], ltrb[3]],
                    'center': [center_x, center_y],
                    'trajectory': trajectory,
                    'movement': movement_info,
                    'collision': collision_info,
                    'is_confirmed': True
                })

            logger.info(f"Tracking: {len(tracked_objects)} confirmed tracks from {len(raw_detections)} detections")
        else:
            # Return raw detections without tracking
            tracked_objects = [{
                'track_id': None,
                'class_name': det['class_name'],
                'confidence': det['confidence'],
                'bbox': det['bbox_xyxy'],
                'center': [(det['bbox_xyxy'][0] + det['bbox_xyxy'][2])/2,
                          (det['bbox_xyxy'][1] + det['bbox_xyxy'][3])/2],
                'trajectory': [],
                'movement': None,
                'is_confirmed': False
            } for det in raw_detections]

        logger.info(f"✅ Detected {len(raw_detections)} objects, tracking {len(tracked_objects)} objects")
        if filtered_count > 0:
            logger.info(f"🚫 Filtered out {filtered_count} blacklisted detections")
        if rotation_applied != 0:
            logger.info(f"🔄 Applied {rotation_applied}° rotation correction via {orientation_source}")

        # Check for collision warnings
        collision_warnings = [obj for obj in tracked_objects if obj.get('collision', {}).get('collision_risk', False)]
        if collision_warnings:
            logger.warning(f"⚠️ Collision warnings: {len(collision_warnings)} objects approaching user")

        # Prepare response with explicit type conversion for JSON serialization
        response_data = {
            'detections': tracked_objects,  # Now includes tracking and collision info
            'success': True,
            'image_size': [int(image_np.shape[1]), int(image_np.shape[0])],
            'filtered_count': int(filtered_count),
            'rotation_applied': int(rotation_applied),
            'orientation_source': str(orientation_source),
            'orientation_corrected': bool(rotation_applied != 0),
            'gyroscope_available': bool('orientation' in data and data['orientation'] is not None),
            'tracking_enabled': bool(tracking_enabled),
            'tracked_count': int(len(tracked_objects)),
            'raw_detection_count': int(len(raw_detections)),
            'collision_warnings': int(len(collision_warnings)),
            'processing_time_ms': float((time.time() - start_time) * 1000)
        }

        logger.info(f"📤 Sending response with {len(tracked_objects)} tracked objects")
        logger.info(f"⏱️ Total processing time: {response_data['processing_time_ms']:.1f}ms")

        response = jsonify(response_data)
        logger.info(f"✅ Response object created successfully")
        return response

    except Exception as e:
        logger.error(f"❌ Detection error: {e}", exc_info=True)
        logger.error(f"❌ Error type: {type(e).__name__}")
        logger.error(f"❌ Error occurred at line: {e.__traceback__.tb_lineno if hasattr(e, '__traceback__') else 'unknown'}")

        error_response = jsonify({
            'error': str(e),
            'error_type': type(e).__name__,
            'success': False,
            'processing_time_ms': float((time.time() - start_time) * 1000)
        })
        logger.info("📤 Sending error response")
        return error_response


@bp.route('/test_audio')
def test_audio():
    """Test endpoint to return sample detection data for audio testing."""
    # Only include non-blacklisted classes in test data
    sample_detections = [
        {
            'class_name': 'person',
            'confidence': 0.85,
            'bbox': [100, 50, 300, 400],  # Large bounding box = close
            'class_id': 0
        },
        {
            'class_name': 'car',
            'confidence': 0.92,
            'bbox': [400, 200, 500, 250],  # Small bounding box = far
            'class_id': 2
        }
    ]

    # Filter out any blacklisted classes from test data
    filtered_detections = [
        det for det in sample_detections
        if not is_class_blacklisted(det['class_name'])
    ]

    return jsonify({
        'detections': filtered_detections,
        'success': True,
        'image_size': [640, 480]
    })
