"""
Collision detection and movement prediction service.

IMPROVEMENTS (2025-10-19):
- Added graceful handling of None/invalid distances
- Uses bbox-based fallback when depth unavailable
- Only triggers high-confidence warnings for validated distances
"""

import numpy as np
from scipy.spatial.distance import euclidean
from ..constants import (
    USER_ZONE_RADIUS_FACTOR,
    COLLISION_PREDICTION_FRAMES,
    STATIONARY_THRESHOLD,
    SPEED_SLOW_THRESHOLD,
    SPEED_MEDIUM_THRESHOLD
)


def calculate_movement(trajectory):
    """
    Calculate movement information from trajectory.

    Args:
        trajectory: List of (x, y) positions

    Returns:
        dict: Movement information including direction, speed, displacement, etc.
    """
    if len(trajectory) < 2:
        return {
            'direction': 'stationary',
            'speed': 0,
            'displacement': 0,
            'angle': 0,
            'velocity_x': 0,
            'velocity_y': 0,
            'speed_class': 'slow',
            'trajectory_length': len(trajectory)
        }

    # Get first and last points
    start = trajectory[0]
    end = trajectory[-1]

    # Calculate displacement
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    displacement = np.sqrt(dx**2 + dy**2)

    # Calculate speed (pixels per frame)
    speed = displacement / len(trajectory)

    # Calculate velocity components
    velocity_x = dx / len(trajectory)
    velocity_y = dy / len(trajectory)

    # Calculate angle (in degrees, 0 = right, 90 = down, 180 = left, 270 = up)
    angle = np.degrees(np.arctan2(dy, dx))

    # Determine direction using perspective-aware naming
    # In camera perspective: up in frame = away from user, down in frame = toward user
    if displacement < STATIONARY_THRESHOLD:
        direction = 'stationary'
    elif -45 <= angle < 45:
        direction = 'moving_right'
    elif 45 <= angle < 135:
        direction = 'moving_closer'  # Moving down in frame = coming toward user
    elif angle >= 135 or angle < -135:
        direction = 'moving_left'
    else:
        direction = 'moving_away'  # Moving up in frame = going away from user

    # Classify speed
    if speed < SPEED_SLOW_THRESHOLD:
        speed_class = 'slow'
    elif speed < SPEED_MEDIUM_THRESHOLD:
        speed_class = 'medium'
    else:
        speed_class = 'fast'

    return {
        'direction': direction,
        'speed': float(speed),
        'speed_class': speed_class,
        'displacement': float(displacement),
        'angle': float(angle),
        'trajectory_length': len(trajectory),
        'velocity_x': float(velocity_x),
        'velocity_y': float(velocity_y)
    }


def predict_collision(track_center, track_movement, image_width, image_height, prediction_frames=None):
    """
    Predict if an object will collide with the user (camera center).

    Args:
        track_center: (x, y) current position
        track_movement: Movement info dict with velocity
        image_width: Width of image
        image_height: Height of image
        prediction_frames: How many frames ahead to predict (uses default if None)

    Returns:
        dict: Collision prediction information
    """
    if prediction_frames is None:
        prediction_frames = COLLISION_PREDICTION_FRAMES

    # Camera center (user position)
    camera_center_x = image_width / 2
    camera_center_y = image_height / 2

    # Define the "user zone" - center area of the frame
    user_zone_radius = min(image_width, image_height) * USER_ZONE_RADIUS_FACTOR

    # Current distance to user
    current_distance = euclidean(track_center, (camera_center_x, camera_center_y))

    # If object is stationary, no collision
    if track_movement['direction'] == 'stationary':
        return {
            'collision_risk': False,
            'is_approaching': False,
            'time_to_collision': None,
            'collision_severity': 'none',
            'predicted_position': list(track_center),
            'current_distance': float(current_distance),
            'predicted_distance': float(current_distance),
            'user_zone_radius': float(user_zone_radius)
        }

    # Predict future position
    velocity_x = track_movement.get('velocity_x', 0)
    velocity_y = track_movement.get('velocity_y', 0)

    # Project position forward
    predicted_x = track_center[0] + (velocity_x * prediction_frames)
    predicted_y = track_center[1] + (velocity_y * prediction_frames)
    predicted_position = (predicted_x, predicted_y)

    # Calculate distance at predicted position
    predicted_distance = euclidean(predicted_position, (camera_center_x, camera_center_y))

    # Check if moving toward user
    is_approaching = predicted_distance < current_distance

    # Calculate time to collision (if approaching)
    time_to_collision = None
    if is_approaching and (velocity_x != 0 or velocity_y != 0):
        # Calculate how many frames until it reaches user zone
        speed = track_movement['speed']
        if speed > 0:
            distance_to_close = current_distance - user_zone_radius
            if distance_to_close > 0:
                time_to_collision = distance_to_close / speed

    # Determine collision risk and severity
    collision_risk = False
    collision_severity = 'none'

    if is_approaching:
        if predicted_distance < user_zone_radius:
            collision_risk = True
            collision_severity = 'high'  # Will enter user zone
        elif predicted_distance < user_zone_radius * 2:
            collision_risk = True
            collision_severity = 'medium'  # Getting close
        elif current_distance < user_zone_radius * 3:
            collision_risk = True
            collision_severity = 'low'  # Approaching from distance

    return {
        'collision_risk': collision_risk,
        'is_approaching': is_approaching,
        'time_to_collision': float(time_to_collision) if time_to_collision else None,
        'collision_severity': collision_severity,
        'predicted_position': [float(predicted_x), float(predicted_y)],
        'current_distance': float(current_distance),
        'predicted_distance': float(predicted_distance),
        'user_zone_radius': float(user_zone_radius)
    }
