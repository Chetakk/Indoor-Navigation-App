"""
Geometric calculations for object detection and tracking.
"""

import numpy as np
from scipy.spatial.distance import euclidean


def calculate_iou(box1, box2):
    """
    Calculate Intersection over Union (IoU) between two bounding boxes.

    Args:
        box1: Bounding box in [x1, y1, x2, y2] format
        box2: Bounding box in [x1, y1, x2, y2] format

    Returns:
        float: IoU score between 0 and 1
    """
    x1_min, y1_min, x1_max, y1_max = box1
    x2_min, y2_min, x2_max, y2_max = box2

    # Calculate intersection area
    intersect_x_min = max(x1_min, x2_min)
    intersect_y_min = max(y1_min, y2_min)
    intersect_x_max = min(x1_max, x2_max)
    intersect_y_max = min(y1_max, y2_max)

    if intersect_x_max < intersect_x_min or intersect_y_max < intersect_y_min:
        return 0.0  # No intersection

    intersection = (intersect_x_max - intersect_x_min) * (intersect_y_max - intersect_y_min)

    # Calculate union area
    box1_area = (x1_max - x1_min) * (y1_max - y1_min)
    box2_area = (x2_max - x2_min) * (y2_max - y2_min)
    union = box1_area + box2_area - intersection

    return intersection / union if union > 0 else 0.0


def calculate_distance(point1, point2):
    """
    Calculate Euclidean distance between two points.

    Args:
        point1: Tuple of (x, y) coordinates
        point2: Tuple of (x, y) coordinates

    Returns:
        float: Distance between the points
    """
    return euclidean(point1, point2)


def calculate_box_center(bbox):
    """
    Calculate the center point of a bounding box.

    Args:
        bbox: Bounding box in [x1, y1, x2, y2] format

    Returns:
        tuple: (center_x, center_y)
    """
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def calculate_box_area(bbox):
    """
    Calculate the area of a bounding box.

    Args:
        bbox: Bounding box in [x1, y1, x2, y2] format

    Returns:
        float: Area of the bounding box
    """
    x1, y1, x2, y2 = bbox
    return (x2 - x1) * (y2 - y1)


def convert_bbox_format(bbox, from_format='xyxy', to_format='ltwh'):
    """
    Convert bounding box between different formats.

    Args:
        bbox: Bounding box coordinates
        from_format: Source format ('xyxy' or 'ltwh')
        to_format: Target format ('xyxy' or 'ltwh')

    Returns:
        list: Converted bounding box coordinates

    Formats:
        - 'xyxy': [x1, y1, x2, y2] (top-left and bottom-right corners)
        - 'ltwh': [left, top, width, height]
    """
    if from_format == to_format:
        return bbox

    if from_format == 'xyxy' and to_format == 'ltwh':
        x1, y1, x2, y2 = bbox
        return [x1, y1, x2 - x1, y2 - y1]

    elif from_format == 'ltwh' and to_format == 'xyxy':
        x, y, w, h = bbox
        return [x, y, x + w, y + h]

    else:
        raise ValueError(f"Unsupported conversion: {from_format} -> {to_format}")
