"""
Filtering utilities for object detection - blacklisting, normalization, and deduplication.
"""

import logging
from ..constants import BLACKLISTED_CLASSES, CLASS_MAPPING
from .geometry import calculate_iou

logger = logging.getLogger(__name__)


def is_class_blacklisted(class_name):
    """
    Check if a class is in the blacklist.

    Args:
        class_name: Name of the class to check

    Returns:
        bool: True if the class is blacklisted
    """
    return class_name.lower() in BLACKLISTED_CLASSES


def normalize_class_name(class_name):
    """
    Normalize class name using mapping (e.g., man/woman/face -> person).

    Args:
        class_name: Original class name

    Returns:
        str: Normalized class name
    """
    normalized = class_name.lower()
    return CLASS_MAPPING.get(normalized, class_name)


def deduplicate_same_class_detections(detections, iou_threshold=0.5):
    """
    Remove duplicate detections of the SAME class that overlap significantly.
    For example, if "person" and "face" both map to "person" and overlap,
    keep only the one with higher confidence.

    Args:
        detections: List of detection dicts with 'class_name', 'bbox_xyxy', 'confidence'
        iou_threshold: IoU threshold for considering boxes as duplicates

    Returns:
        list: Deduplicated list of detections
    """
    if len(detections) <= 1:
        return detections

    # Group by normalized class name
    class_groups = {}
    for det in detections:
        cls = det['class_name']
        if cls not in class_groups:
            class_groups[cls] = []
        class_groups[cls].append(det)

    # Deduplicate within each class group
    deduplicated = []
    for cls, group in class_groups.items():
        # Sort by confidence (highest first)
        group_sorted = sorted(group, key=lambda x: x['confidence'], reverse=True)

        kept = []
        for det in group_sorted:
            # Check if this detection overlaps significantly with any already kept detection
            should_keep = True
            for kept_det in kept:
                iou = calculate_iou(det['bbox_xyxy'], kept_det['bbox_xyxy'])
                if iou > iou_threshold:
                    # This is a duplicate of a higher-confidence detection
                    should_keep = False
                    logger.debug(f"Removing duplicate {cls} detection (IoU={iou:.2f})")
                    break

            if should_keep:
                kept.append(det)

        deduplicated.extend(kept)

    return deduplicated


def filter_detections_by_confidence(detections, min_confidence=0.3):
    """
    Filter detections by minimum confidence threshold.

    Args:
        detections: List of detection dictionaries
        min_confidence: Minimum confidence threshold (0.0 to 1.0)

    Returns:
        list: Filtered detections
    """
    return [det for det in detections if det.get('confidence', 0) >= min_confidence]


def filter_detections_by_classes(detections, allowed_classes):
    """
    Keep only detections of specific classes.

    Args:
        detections: List of detection dictionaries
        allowed_classes: Set or list of class names to keep

    Returns:
        list: Filtered detections
    """
    allowed_set = set(cls.lower() for cls in allowed_classes)
    return [det for det in detections if det.get('class_name', '').lower() in allowed_set]
