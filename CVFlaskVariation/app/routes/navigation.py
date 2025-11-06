"""
Navigation and pathfinding routes.
"""

import logging
from flask import Blueprint, jsonify, request, session
from ..services.pathfinder import (
    create_occupancy_grid,
    astar_pathfinding,
    calculate_path_safety,
    convert_path_to_pixels,
    calculate_reactive_navigation
)
from ..constants import DEFAULT_GRID_SIZE

logger = logging.getLogger(__name__)

bp = Blueprint('navigation', __name__)

# Session-based user position tracking
# Key format: f"user_position_{session_id}"
# Value: [x, y, timestamp]


@bp.route('/reset_navigation', methods=['POST'])
def reset_navigation():
    """Reset navigation session data (user position, goal, previous detections, etc.)"""
    try:
        import time

        if 'session_id' not in session:
            return jsonify({'success': True, 'message': 'No active session'})

        session_id = session['session_id']
        position_key = f'nav_position_{session_id}'
        timestamp_key = f'nav_timestamp_{session_id}'
        goal_key = f'nav_goal_{session_id}'
        prev_detections_key = f'nav_prev_detections_{session_id}'

        session.pop(position_key, None)
        session.pop(timestamp_key, None)
        session.pop(goal_key, None)
        session.pop(prev_detections_key, None)

        logger.info(f"Navigation session reset for session {session_id}")

        return jsonify({
            'success': True,
            'message': 'Navigation session reset'
        })

    except Exception as e:
        logger.error(f"Error resetting navigation: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False})


@bp.route('/calculate_path', methods=['POST'])
def calculate_path():
    """Calculate navigation path avoiding obstacles."""
    try:
        data = request.get_json()

        if not data or 'detections' not in data or 'goal' not in data:
            return jsonify({'error': 'Missing detections or goal', 'success': False})

        detections = data['detections']
        goal = data['goal']  # (x, y) in pixel coordinates
        start = data.get('start')  # Optional start position, defaults to center bottom
        image_width = data.get('image_width', 640)
        image_height = data.get('image_height', 480)
        grid_size = data.get('grid_size', DEFAULT_GRID_SIZE)

        # Default start position (bottom center - user position)
        if not start:
            start = [image_width // 2, image_height - 20]

        # Create occupancy grid
        grid = create_occupancy_grid(detections, image_width, image_height, grid_size)

        # Convert pixel coordinates to grid coordinates
        start_grid = (int(start[0] / grid_size), int(start[1] / grid_size))
        goal_grid = (int(goal[0] / grid_size), int(goal[1] / grid_size))

        logger.info(f"Pathfinding from {start_grid} to {goal_grid}")

        # Run A* pathfinding
        path_grid = astar_pathfinding(grid, start_grid, goal_grid)

        if path_grid is None:
            logger.warning("No path found")
            return jsonify({
                'success': True,
                'path_found': False,
                'message': 'No clear path to destination',
                'grid_size': grid_size,
                'grid_shape': list(grid.shape)
            })

        # Convert grid coordinates back to pixel coordinates
        path_pixels = convert_path_to_pixels(path_grid, grid_size)

        logger.info(f"Path found with {len(path_pixels)} waypoints")

        # Calculate path safety score (based on distance from obstacles)
        safety_score = calculate_path_safety(grid, path_grid)

        return jsonify({
            'success': True,
            'path_found': True,
            'path': path_pixels,
            'waypoint_count': len(path_pixels),
            'grid_size': grid_size,
            'grid_shape': list(grid.shape),
            'safety_score': float(safety_score),
            'occupancy_grid': grid.tolist()  # For visualization
        })

    except Exception as e:
        logger.error(f"Pathfinding error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False})


def estimate_camera_movement(detections, previous_detections, previous_position, image_width, image_height):
    """
    Estimate camera movement using visual odometry from tracked object positions and distances.

    Args:
        detections: Current frame detections with track_id, bbox, distance
        previous_detections: Previous frame detections
        previous_position: Previous camera position [x, y] in pixel coordinates
        image_width: Image width
        image_height: Image height

    Returns:
        tuple: (new_position, confidence) - estimated new position and confidence score
    """
    import numpy as np

    if not previous_detections or not detections:
        return previous_position, 0.0

    # Match tracked objects between frames
    matched_objects = []
    for curr in detections:
        track_id = curr.get('track_id')
        if track_id is None:
            continue

        # Find same object in previous frame
        for prev in previous_detections:
            if prev.get('track_id') == track_id:
                # Use objects with good distance estimates
                curr_dist = curr.get('distance')
                prev_dist = prev.get('distance')
                curr_conf = curr.get('distance_confidence', 0)
                prev_conf = prev.get('distance_confidence', 0)

                if (curr_dist and prev_dist and
                    curr_dist > 0 and prev_dist > 0 and
                    curr_conf > 0.3 and prev_conf > 0.3):

                    # Calculate object center in image coordinates
                    curr_bbox = curr.get('bbox', [])
                    prev_bbox = prev.get('bbox', [])

                    if len(curr_bbox) >= 4 and len(prev_bbox) >= 4:
                        curr_center = [(curr_bbox[0] + curr_bbox[2]) / 2,
                                      (curr_bbox[1] + curr_bbox[3]) / 2]
                        prev_center = [(prev_bbox[0] + prev_bbox[2]) / 2,
                                      (prev_bbox[1] + prev_bbox[3]) / 2]

                        matched_objects.append({
                            'curr_center': curr_center,
                            'prev_center': prev_center,
                            'curr_distance': curr_dist,
                            'prev_distance': prev_dist,
                            'confidence': min(curr_conf, prev_conf)
                        })
                break

    if len(matched_objects) < 2:
        # Not enough matched objects for reliable estimate
        return previous_position, 0.0

    # Estimate camera movement from distance changes
    movement_estimates = []

    for obj in matched_objects:
        # Distance change (in meters)
        distance_change = obj['prev_distance'] - obj['curr_distance']

        # If distance decreased, camera moved toward object
        # If distance increased, camera moved away

        if abs(distance_change) < 0.1:  # Less than 10cm change - likely noise
            continue

        # Convert to pixel movement (rough: 100 pixels ~ 1 meter)
        pixel_movement = distance_change * 100

        # Direction: from previous position toward object
        obj_prev_pos = np.array(obj['prev_center'])
        cam_prev_pos = np.array(previous_position)

        direction_to_obj = obj_prev_pos - cam_prev_pos
        distance_to_obj_pixels = np.linalg.norm(direction_to_obj)

        if distance_to_obj_pixels > 1:
            direction_to_obj = direction_to_obj / distance_to_obj_pixels

            # Estimate movement vector
            movement_vector = direction_to_obj * pixel_movement

            movement_estimates.append({
                'vector': movement_vector,
                'confidence': obj['confidence']
            })

    if not movement_estimates:
        return previous_position, 0.0

    # Weighted average of movement estimates
    total_confidence = sum(est['confidence'] for est in movement_estimates)

    if total_confidence < 0.01:
        return previous_position, 0.0

    weighted_movement = np.zeros(2)
    for est in movement_estimates:
        weight = est['confidence'] / total_confidence
        weighted_movement += est['vector'] * weight

    # Calculate new position
    new_position = [
        previous_position[0] + weighted_movement[0],
        previous_position[1] + weighted_movement[1]
    ]

    # Clamp to screen bounds
    new_position[0] = max(0, min(new_position[0], image_width))
    new_position[1] = max(0, min(new_position[1], image_height))

    # Average confidence
    avg_confidence = total_confidence / len(movement_estimates)

    return new_position, avg_confidence


@bp.route('/navigate_reactive', methods=['POST'])
def navigate_reactive():
    """
    Reactive navigation endpoint - provides real-time obstacle avoidance guidance.
    Uses vision-based position tracking from object detections and distances.
    """
    try:
        import time
        import numpy as np

        data = request.get_json()

        if not data or 'detections' not in data or 'goal' not in data:
            return jsonify({'error': 'Missing detections or goal', 'success': False})

        detections = data['detections']
        goal = data['goal']  # [x, y] in pixel coordinates
        image_width = data.get('image_width', 640)
        image_height = data.get('image_height', 480)

        # Get or initialize session ID for position tracking
        if 'session_id' not in session:
            session['session_id'] = str(time.time())
        session_id = session['session_id']

        # Track user position per session
        position_key = f'nav_position_{session_id}'
        timestamp_key = f'nav_timestamp_{session_id}'
        goal_key = f'nav_goal_{session_id}'
        prev_detections_key = f'nav_prev_detections_{session_id}'

        current_time = time.time()

        # Check if this is a new goal (goal changed)
        stored_goal = session.get(goal_key)
        goal_changed = stored_goal != goal

        if goal_changed:
            # New goal - reset position to default (bottom center)
            start = [image_width // 2, image_height - 20]
            session[position_key] = start
            session[timestamp_key] = current_time
            session[goal_key] = goal
            session[prev_detections_key] = detections  # Store for next frame
            logger.info(f"New navigation goal set: {goal}")
            logger.info(f"Starting position reset to: {start}")
        else:
            # Continuing navigation - use vision-based position estimation
            start = session.get(position_key, [image_width // 2, image_height - 20])
            prev_detections = session.get(prev_detections_key, [])

            # Estimate camera movement from visual odometry
            new_position, confidence = estimate_camera_movement(
                detections,
                prev_detections,
                start,
                image_width,
                image_height
            )

            if confidence > 0.3:
                # High confidence - use vision-based estimate
                movement = np.linalg.norm(np.array(new_position) - np.array(start))
                logger.info(f"Vision-based position update: {start} -> {new_position} "
                          f"(moved {movement:.1f} pixels, confidence: {confidence:.2f})")
                start = new_position
            else:
                # Low confidence - fallback to time-based estimate
                last_time = session.get(timestamp_key, current_time)
                time_elapsed = current_time - last_time

                if 0 < time_elapsed < 2.0:
                    goal_vector = np.array([goal[0] - start[0], goal[1] - start[1]], dtype=float)
                    distance_to_goal = np.linalg.norm(goal_vector)

                    if distance_to_goal > 1:
                        direction = goal_vector / distance_to_goal
                        movement_distance = min(100 * time_elapsed, distance_to_goal)

                        new_position = [
                            start[0] + direction[0] * movement_distance,
                            start[1] + direction[1] * movement_distance
                        ]

                        new_position[0] = max(0, min(new_position[0], image_width))
                        new_position[1] = max(0, min(new_position[1], image_height))

                        start = new_position
                        logger.info(f"Time-based fallback: moved {movement_distance:.1f} pixels "
                                  f"in {time_elapsed:.2f}s (low vision confidence: {confidence:.2f})")

            # Store updated position, timestamp, and detections
            session[position_key] = start
            session[timestamp_key] = current_time
            session[prev_detections_key] = detections

        logger.info(f"Reactive navigation from {start} to {goal}")

        # Calculate reactive navigation guidance
        result = calculate_reactive_navigation(
            detections,
            goal,
            start,
            image_width,
            image_height
        )

        # Add success flag and user position
        result['success'] = True
        result['user_position'] = start  # Send back current position for debugging

        # Log guidance if available (won't be present when goal is reached)
        if 'guidance' in result:
            logger.info(f"Navigation guidance: {result['guidance']['primary']}")
            if result.get('guidance', {}).get('warnings'):
                logger.info(f"Warnings: {', '.join(result['guidance']['warnings'])}")

        # If goal reached, clear session data
        if result.get('reached_goal'):
            session.pop(position_key, None)
            session.pop(timestamp_key, None)
            session.pop(goal_key, None)
            session.pop(prev_detections_key, None)
            logger.info("Goal reached - clearing navigation session data")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Reactive navigation error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False})
