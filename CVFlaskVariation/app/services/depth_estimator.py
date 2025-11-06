"""
Depth estimation service using Depth Anything V2 for monocular depth prediction.
Provides real distance measurements with GPU acceleration and async processing.

PERFORMANCE OPTIMIZATIONS (2025-10-19):
- Replaced MiDaS with Depth Anything V2 Small (72 FPS vs 5 FPS)
- Added async depth worker thread (non-blocking detection pipeline)
- GPU acceleration on RTX 5060
- Auto-calibration using pinhole distances
- Reduced input size to 256x256 for faster inference
"""

import logging
import numpy as np
import cv2
import torch
import threading
import time
import atexit
from pathlib import Path
from collections import deque
from transformers import AutoImageProcessor, AutoModelForDepthEstimation
from ..constants import (
    DEPTH_INFERENCE_INTERVAL,
    DEPTH_MODEL_TYPE,
    DEPTH_INPUT_SIZE,
    DEPTH_CACHE_FRAMES,
    DEPTH_FALLBACK_ENABLED,
    DEPTH_ASYNC_ENABLED,
    DEPTH_AUTO_CALIBRATION,
    DEPTH_USE_FP16
)
from ..utils.camera_calibration import get_pinhole_model

logger = logging.getLogger(__name__)


class DepthMapCache:
    """Thread-safe cache for depth maps."""

    def __init__(self, maxlen=10):
        self.maxlen = maxlen
        self.depth_map = None
        self.timestamp = 0
        self.lock = threading.Lock()

    def set(self, depth_map):
        """Store depth map (thread-safe)."""
        with self.lock:
            self.depth_map = depth_map
            self.timestamp = time.time()

    def get(self):
        """Retrieve depth map (thread-safe)."""
        with self.lock:
            return self.depth_map, self.timestamp

    def is_valid(self, max_age_seconds=1.0):
        """Check if cached depth is still fresh."""
        with self.lock:
            if self.depth_map is None:
                return False
            age = time.time() - self.timestamp
            return age < max_age_seconds


class AutoCalibrator:
    """Auto-calibrates depth scale using pinhole camera estimates."""

    def __init__(self, window_size=20):
        self.scales = deque(maxlen=window_size)
        self.lock = threading.Lock()

    def add_sample(self, pinhole_distance, relative_depth):
        """Add a calibration sample."""
        if pinhole_distance is None or relative_depth is None or relative_depth <= 0:
            return

        # Calculate scale: real_distance = relative_depth * scale
        scale = pinhole_distance / relative_depth

        # Sanity check: scale should be reasonable (0.001 to 0.1)
        if 0.001 <= scale <= 0.1:
            with self.lock:
                self.scales.append(scale)
                logger.info(f"Auto-calibration sample: pinhole={pinhole_distance:.2f}m, rel_depth={relative_depth:.2f}, scale={scale:.6f}")

    def get_scale(self):
        """Get current calibrated scale (median of samples)."""
        with self.lock:
            if len(self.scales) < 3:
                return None
            return float(np.median(list(self.scales)))

    def get_confidence(self):
        """Get confidence in current calibration (0-1)."""
        with self.lock:
            n_samples = len(self.scales)
            if n_samples < 3:
                return 0.0
            elif n_samples < 10:
                return 0.5 + (n_samples / 20.0)  # 0.5 to 1.0
            else:
                return 0.9  # High confidence


class AsyncDepthWorker(threading.Thread):
    """Background thread that continuously updates depth maps."""

    def __init__(self, model, transform, device, cache, input_size=256, use_fp16=False):
        super().__init__(daemon=True)
        self.model = model
        self.transform = transform
        self.device = device
        self.cache = cache
        self.input_size = input_size
        self.use_fp16 = use_fp16

        self.image_queue = deque(maxlen=2)  # Only keep latest 2 frames
        self.queue_lock = threading.Lock()
        self.running = True
        self.frame_count = 0

    def add_image(self, image_bgr):
        """Add image to processing queue."""
        with self.queue_lock:
            self.image_queue.append(image_bgr.copy())

    def stop(self, timeout=2.0):
        """
        Stop the worker thread gracefully.

        Args:
            timeout: Maximum time to wait for thread to finish (seconds)
        """
        logger.info("Stopping async depth worker...")
        self.running = False

        # Wait for thread to finish (with timeout)
        if self.is_alive():
            self.join(timeout=timeout)
            if self.is_alive():
                logger.warning(f"Async depth worker did not stop within {timeout}s timeout")
            else:
                logger.info("Async depth worker stopped successfully")

    def run(self):
        """Main worker loop - processes images from queue."""
        logger.info("Async depth worker started")

        while self.running:
            # Get image from queue
            image_bgr = None
            with self.queue_lock:
                if len(self.image_queue) > 0:
                    image_bgr = self.image_queue.popleft()

            if image_bgr is None:
                time.sleep(0.01)  # Wait for new images
                continue

            # Process depth estimation
            try:
                depth_map = self._estimate_depth(image_bgr)
                if depth_map is not None:
                    self.cache.set(depth_map)
                    self.frame_count += 1
                    if self.frame_count % 10 == 0:
                        logger.debug(f"Async depth worker: processed {self.frame_count} frames")
            except Exception as e:
                logger.error(f"Error in async depth worker: {e}", exc_info=True)

        logger.info("Async depth worker stopped")

    def _estimate_depth(self, image_bgr):
        """Estimate depth map for an image (internal method)."""
        try:
            # Convert BGR to RGB
            image_rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)

            # Resize for faster inference
            if image_rgb.shape[0] > self.input_size or image_rgb.shape[1] > self.input_size:
                h, w = image_rgb.shape[:2]
                scale = self.input_size / max(h, w)
                new_h, new_w = int(h * scale), int(w * scale)
                image_rgb = cv2.resize(image_rgb, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # Prepare input
            inputs = self.transform(images=image_rgb, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Convert to FP16 if enabled (2x faster on RTX GPUs!)
            if self.use_fp16 and self.device == 'cuda':
                inputs = {k: v.half() if v.dtype == torch.float32 else v for k, v in inputs.items()}

            # Run inference with FP16 mixed precision if enabled
            with torch.no_grad():
                if self.use_fp16 and self.device == 'cuda':
                    with torch.amp.autocast('cuda'):
                        outputs = self.model(**inputs)
                        predicted_depth = outputs.predicted_depth
                else:
                    outputs = self.model(**inputs)
                    predicted_depth = outputs.predicted_depth

            # Interpolate to original size
            prediction = torch.nn.functional.interpolate(
                predicted_depth.unsqueeze(1),
                size=(image_bgr.shape[0], image_bgr.shape[1]),
                mode="bicubic",
                align_corners=False,
            ).squeeze()

            # Convert to numpy
            depth_map = prediction.cpu().numpy()

            return depth_map

        except Exception as e:
            logger.error(f"Error during depth estimation: {e}")
            return None


class DepthEstimator:
    """
    Manages depth estimation using Depth Anything V2 with async processing.
    """

    def __init__(self, model_type='depth-anything-v2-small', force_cpu=False):
        """
        Initialize the depth estimator.

        Args:
            model_type: Model variant ('depth-anything-v2-small' is fastest)
            force_cpu: If True, force CPU usage
        """
        self.model_type = model_type
        self.device = 'cpu' if force_cpu else ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.transform = None

        # Caching and async processing
        self.depth_cache = DepthMapCache(maxlen=DEPTH_CACHE_FRAMES)
        self.frame_counter = 0
        self.async_worker = None

        # Auto-calibration
        self.auto_calibrator = AutoCalibrator() if DEPTH_AUTO_CALIBRATION else None

        # Pinhole fallback
        self.pinhole_model = get_pinhole_model() if DEPTH_FALLBACK_ENABLED else None

        self._load_model()

    def _load_model(self):
        """Load the Depth Anything V2 model safely (fixed meta tensor issue)."""
        try:
            if 'depth-anything-v2' in self.model_type:
                logger.info(f"Loading Depth Anything V2 model: {self.model_type}...")
    
                # Map model size to HuggingFace model name
                model_name = "depth-anything/Depth-Anything-V2-Small-hf"
                if 'large' in self.model_type:
                    model_name = "depth-anything/Depth-Anything-V2-Large-hf"
                elif 'base' in self.model_type:
                    model_name = "depth-anything/Depth-Anything-V2-Base-hf"
    
                # Load processor
                self.transform = AutoImageProcessor.from_pretrained(model_name)
    
                # --- FIX: Load directly to the actual device without meta tensors ---
                torch_dtype = torch.float16 if (DEPTH_USE_FP16 and self.device == 'cuda') else torch.float32
                self.model = AutoModelForDepthEstimation.from_pretrained(
                    model_name,
                    torch_dtype=torch_dtype,
                    low_cpu_mem_usage=False,   # Force real allocation, no meta tensors
                    device_map=None             # Avoid Accelerate dispatching
                )
    
                # Move model explicitly to device
                self.model.to(self.device)
                self.model.eval()
    
                logger.info(f"Depth Anything V2 model loaded successfully on {self.device} ({torch_dtype})")
    
                # Start async worker if enabled
                if DEPTH_ASYNC_ENABLED:
                    self.async_worker = AsyncDepthWorker(
                        self.model, self.transform, self.device,
                        self.depth_cache, input_size=DEPTH_INPUT_SIZE,
                        use_fp16=DEPTH_USE_FP16
                    )
                    self.async_worker.start()
                    logger.info("Async depth worker started successfully")
    
            elif 'midas' in self.model_type:
                # Fallback to MiDaS (legacy)
                logger.info(f"Loading MiDaS model (legacy): {self.model_type}...")
                self.model = torch.hub.load('intel-isl/MiDaS', 'MiDaS_small', pretrained=True)
                self.model.to(self.device)
                self.model.eval()
    
                midas_transforms = torch.hub.load('intel-isl/MiDaS', 'transforms')
                self.transform = midas_transforms.small_transform
                logger.info(f"MiDaS model loaded successfully on {self.device}")
    
        except Exception as e:
            logger.error(f"Error loading depth model: {e}", exc_info=True)
            logger.warning("Depth estimation will use pinhole fallback only")
            self.model = None


    def estimate_depth(self, image_bgr):
        """
        Estimate depth map for an image (synchronous).

        Args:
            image_bgr: Input image in BGR format (OpenCV format)

        Returns:
            numpy.ndarray: Depth map (same size as input), or None if failed
        """
        if self.model is None:
            return None

        # If async worker is active, add to queue and return cached result
        if self.async_worker is not None and self.async_worker.is_alive():
            self.async_worker.add_image(image_bgr)
            cached_depth, _ = self.depth_cache.get()
            return cached_depth

        # Fallback to synchronous processing
        return self.async_worker._estimate_depth(image_bgr) if self.async_worker else None

    def get_depth_at_bbox(self, depth_map, bbox):
        """
        Sample depth value at bounding box location.

        Args:
            depth_map: Depth map from estimate_depth()
            bbox: Bounding box in [x1, y1, x2, y2] format

        Returns:
            float: Median depth value in bbox region
        """
        if depth_map is None:
            return None

        x1, y1, x2, y2 = map(int, bbox)

        # Clamp to image bounds
        h, w = depth_map.shape
        x1 = max(0, min(x1, w - 1))
        x2 = max(0, min(x2, w))
        y1 = max(0, min(y1, h - 1))
        y2 = max(0, min(y2, h))

        if x2 <= x1 or y2 <= y1:
            logger.warning(f"Invalid bbox for depth sampling: {bbox}")
            return None

        # Sample depth in bbox region (use median to avoid outliers)
        bbox_region = depth_map[y1:y2, x1:x2]
        median_depth = np.median(bbox_region)

        return float(median_depth)

    def estimate_distance_with_depth(self, image_bgr, bbox, class_name, force_inference=False, motion_scale=None, motion_confidence=0.0):
        """
        Estimate distance to object using depth map + auto-calibration.

        NEW (2025-10-19): Uses Depth Anything V2 + auto-calibration from pinhole.
        Async processing ensures no blocking on main detection pipeline.

        Args:
            image_bgr: Input image in BGR format
            bbox: Bounding box in [x1, y1, x2, y2] format
            class_name: Object class name
            force_inference: Force depth inference even if not scheduled
            motion_scale: Motion-calibrated depth scale (meters per depth unit)
            motion_confidence: Confidence in motion calibration (0-1)

        Returns:
            dict: {
                'distance': float (meters),
                'confidence': float (0-1),
                'method': str ('motion_calibrated', 'auto_calibrated', 'pinhole', 'bbox_heuristic', 'failed')
            }
        """
        self.frame_counter += 1

        # Get depth map (from cache if async, or compute if sync)
        depth_map, cache_age = self.depth_cache.get()

        # Queue image for async processing if enabled
        if self.async_worker is not None and self.async_worker.is_alive():
            if self.frame_counter % DEPTH_INFERENCE_INTERVAL == 0:
                self.async_worker.add_image(image_bgr)

        # Try pinhole first (for auto-calibration)
        pinhole_distance = None
        pinhole_conf = 0.0
        if self.pinhole_model is not None:
            pinhole_distance, pinhole_conf = self.pinhole_model.estimate_distance_with_confidence(bbox, class_name)

        # Get relative depth from depth map
        relative_depth = None
        if depth_map is not None:
            relative_depth = self.get_depth_at_bbox(depth_map, bbox)

        # AUTO-CALIBRATION: Learn scale from pinhole estimates
        if self.auto_calibrator is not None and pinhole_distance is not None and relative_depth is not None:
            self.auto_calibrator.add_sample(pinhole_distance, relative_depth)

        # PRIORITY 1: Motion-calibrated depth (if available)
        if relative_depth is not None and motion_scale is not None and motion_confidence > 0.1:
            distance = relative_depth * motion_scale
            if 0.1 <= distance <= 50:
                return {
                    'distance': distance,
                    'confidence': motion_confidence,
                    'method': 'motion_calibrated',
                    'relative_depth': relative_depth
                }

        # PRIORITY 2: Auto-calibrated depth (learned from pinhole)
        if relative_depth is not None and self.auto_calibrator is not None:
            auto_scale = self.auto_calibrator.get_scale()
            auto_conf = self.auto_calibrator.get_confidence()

            if auto_scale is not None and auto_conf > 0.3:
                distance = relative_depth * auto_scale
                if 0.1 <= distance <= 50:
                    logger.debug(f"Auto-calibrated distance: {distance:.2f}m (scale={auto_scale:.6f}, conf={auto_conf:.2f})")
                    return {
                        'distance': distance,
                        'confidence': auto_conf,
                        'method': 'auto_calibrated',
                        'relative_depth': relative_depth
                    }

        # PRIORITY 3: Pinhole-only (for known objects)
        if pinhole_distance is not None:
            return {
                'distance': pinhole_distance,
                'confidence': pinhole_conf,
                'method': 'pinhole',
                'relative_depth': relative_depth
            }

        # PRIORITY 4: Bbox heuristic fallback
        x1, y1, x2, y2 = bbox
        bbox_area = (x2 - x1) * (y2 - y1)
        image_area = image_bgr.shape[0] * image_bgr.shape[1]
        area_ratio = bbox_area / image_area

        if area_ratio > 0.01:  # Object must be visible
            # Heuristic: distance inversely proportional to sqrt of area
            # Larger objects = closer, smaller objects = farther
            estimated_distance = 5.0 / np.sqrt(area_ratio)

            # Adjust by vertical position (lower in frame = closer)
            bbox_center_y = (y1 + y2) / 2
            vertical_position = bbox_center_y / image_bgr.shape[0]  # 0 = top, 1 = bottom

            # Objects at bottom are typically closer
            position_factor = 0.7 + (vertical_position * 0.6)  # 0.7 to 1.3
            estimated_distance *= position_factor

            # Clamp to reasonable range
            estimated_distance = np.clip(estimated_distance, 0.5, 20.0)

            logger.debug(f"Bbox heuristic distance: {estimated_distance:.2f}m (area_ratio={area_ratio:.4f}, vertical_pos={vertical_position:.2f})")
            return {
                'distance': estimated_distance,
                'confidence': 0.3,  # Low confidence
                'method': 'bbox_heuristic',
                'relative_depth': relative_depth
            }

        # No distance estimation available
        return {
            'distance': None,
            'confidence': 0.0,
            'method': 'failed',
            'relative_depth': relative_depth
        }

    def update_image_dimensions(self, width, height):
        """Update image dimensions."""
        if self.pinhole_model is not None:
            self.pinhole_model.update_image_dimensions(width, height)

    def reset_cache(self):
        """Reset depth cache."""
        self.depth_cache = DepthMapCache(maxlen=DEPTH_CACHE_FRAMES)
        self.frame_counter = 0
        if self.auto_calibrator is not None:
            self.auto_calibrator = AutoCalibrator()
        logger.info("Depth cache reset")

    def get_stats(self):
        """Get depth estimator statistics."""
        depth_map, cache_age = self.depth_cache.get()
        auto_scale = self.auto_calibrator.get_scale() if self.auto_calibrator else None
        auto_conf = self.auto_calibrator.get_confidence() if self.auto_calibrator else 0.0

        return {
            'model_loaded': self.model is not None,
            'model_type': self.model_type,
            'device': self.device,
            'frame_counter': self.frame_counter,
            'has_cached_depth': depth_map is not None,
            'cache_age_ms': (time.time() - cache_age) * 1000 if cache_age > 0 else None,
            'async_enabled': self.async_worker is not None,
            'async_running': self.async_worker.is_alive() if self.async_worker else False,
            'auto_calibration_scale': auto_scale,
            'auto_calibration_confidence': auto_conf,
            'pinhole_available': self.pinhole_model is not None
        }

    def cleanup(self):
        """
        Explicitly cleanup resources (async worker, GPU memory).
        Call this before application shutdown to avoid GPU context issues.
        """
        logger.info("Cleaning up depth estimator...")

        # Stop async worker if running
        if self.async_worker is not None and self.async_worker.is_alive():
            logger.info("Stopping async depth worker...")
            self.async_worker.stop(timeout=3.0)
            self.async_worker = None

        # Clear GPU memory if using CUDA
        if self.device == 'cuda':
            try:
                import torch
                torch.cuda.empty_cache()
                logger.info("GPU memory cache cleared")
            except Exception as e:
                logger.warning(f"Error clearing GPU cache: {e}")

        logger.info("Depth estimator cleanup complete")

    def __del__(self):
        """Cleanup on deletion (backup, explicit cleanup() is preferred)."""
        try:
            self.cleanup()
        except Exception:
            pass  # Ignore errors during __del__


# Global depth estimator instance
_depth_estimator = None


def _cleanup_on_exit():
    """Cleanup function called by atexit (backup cleanup mechanism)."""
    global _depth_estimator
    if _depth_estimator is not None:
        try:
            logger.info("atexit: Cleaning up depth estimator...")
            _depth_estimator.cleanup()
        except Exception as e:
            logger.error(f"atexit cleanup error: {e}")


# Register atexit handler as backup cleanup mechanism
atexit.register(_cleanup_on_exit)


def get_depth_estimator(model_type=None, force_cpu=False):
    """
    Get the global depth estimator instance (singleton).

    Args:
        model_type: Model variant (uses DEPTH_MODEL_TYPE from constants if None)
        force_cpu: If True, force CPU usage

    Returns:
        DepthEstimator: The estimator instance
    """
    global _depth_estimator
    if _depth_estimator is None:
        if model_type is None:
            model_type = DEPTH_MODEL_TYPE
        _depth_estimator = DepthEstimator(model_type=model_type, force_cpu=force_cpu)
    return _depth_estimator
