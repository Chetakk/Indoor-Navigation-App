"""
YOLO model management and object detection service.
"""

import logging
import torch
from ultralytics import YOLO
from ..constants import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_IOU_THRESHOLD,
    MAX_DETECTIONS
)

logger = logging.getLogger(__name__)


class YOLODetector:
    """Manages YOLO model loading and inference."""

    def __init__(self, model_path='yolov8n-oiv7.pt', force_cpu=True):
        """
        Initialize the YOLO detector.

        Args:
            model_path: Path to the YOLO model file
            force_cpu: If True, force CPU usage (GPU temporarily disabled due to hang issue)
        """
        self.model_path = model_path
        self.device = 'cpu' if force_cpu else ('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self._load_model()

    def _load_model(self):
        """Load the YOLO model and configure device."""
        try:
            logger.info(f"Loading YOLO model from {self.model_path}...")

            # Check GPU availability
            if torch.cuda.is_available():
                logger.info(f"🎮 GPU Detected: {torch.cuda.get_device_name(0)}")
                logger.info(f"🎮 GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
            else:
                logger.warning("⚠️ No GPU detected - using CPU (slower performance)")

            # Load model
            self.model = YOLO(self.model_path)

            # Force CPU usage (temporary workaround for GPU hanging issue)
            if self.device == 'cpu':
                self.model.to('cpu')
                logger.info("✅ Model loaded successfully on CPU (GPU disabled due to hang issue)")
            else:
                self.model.to(self.device)
                logger.info(f"✅ Model loaded successfully on {self.device}")

            logger.info(f"📦 Model has {len(self.model.names)} classes")

        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")
            # Fallback to default model
            logger.info("Attempting to load fallback model...")
            self.model = YOLO('yolov8x-oiv7.pt')
            self.model.to('cpu')
            logger.info("Using fallback model on CPU")

    def detect(self, image, conf=None, iou=None, max_det=None, verbose=False):
        """
        Run object detection on an image.

        Args:
            image: Image as numpy array (BGR format)
            conf: Confidence threshold (uses default if None)
            iou: IOU threshold for NMS (uses default if None)
            max_det: Maximum detections (uses default if None)
            verbose: Whether to print verbose output

        Returns:
            YOLO results object
        """
        if self.model is None:
            raise RuntimeError("Model not loaded")

        conf = conf or DEFAULT_CONFIDENCE_THRESHOLD
        iou = iou or DEFAULT_IOU_THRESHOLD
        max_det = max_det or MAX_DETECTIONS

        logger.debug(f"Running detection with conf={conf}, iou={iou}, max_det={max_det}")

        results = self.model(
            image,
            verbose=verbose,
            device=self.device,
            conf=conf,
            iou=iou,
            max_det=max_det
        )

        return results

    def get_class_names(self):
        """
        Get all available class names.

        Returns:
            dict: Dictionary mapping class IDs to class names
        """
        if self.model is None:
            return {}
        return self.model.names

    def get_model_info(self):
        """
        Get model information.

        Returns:
            dict: Model metadata
        """
        if self.model is None:
            return {'loaded': False}

        return {
            'loaded': True,
            'model_path': self.model_path,
            'device': self.device,
            'num_classes': len(self.model.names),
            'class_names': list(self.model.names.values()),
            'gpu_available': torch.cuda.is_available(),
            'gpu_name': torch.cuda.get_device_name(0) if torch.cuda.is_available() else None
        }


# Global detector instance (singleton pattern)
_detector = None


def get_detector(model_path='yolov8x-oiv7.pt', force_cpu=True):
    """
    Get the global YOLO detector instance (singleton).

    Args:
        model_path: Path to the YOLO model file
        force_cpu: If True, force CPU usage

    Returns:
        YOLODetector: The detector instance
    """
    global _detector
    if _detector is None:
        _detector = YOLODetector(model_path=model_path, force_cpu=force_cpu)
    return _detector
