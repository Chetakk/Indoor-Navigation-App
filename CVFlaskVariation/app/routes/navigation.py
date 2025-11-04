"""
Navigation and pathfinding routes.
"""

import logging
from flask import Blueprint, jsonify, request
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


@bp.route('/navigate_reactive', methods=['POST'])
def navigate_reactive():
    """
    Reactive navigation endpoint - provides real-time obstacle avoidance guidance.
    Designed for dynamic environments where obstacles move and change.
    """
    try:
        data = request.get_json()

        if not data or 'detections' not in data or 'goal' not in data:
            return jsonify({'error': 'Missing detections or goal', 'success': False})

        detections = data['detections']
        goal = data['goal']  # [x, y] in pixel coordinates
        start = data.get('start')  # Optional start position
        image_width = data.get('image_width', 640)
        image_height = data.get('image_height', 480)

        # Default start position (bottom center - user position)
        if not start:
            start = [image_width // 2, image_height - 20]

        logger.info(f"Reactive navigation from {start} to {goal}")

        # Calculate reactive navigation guidance
        result = calculate_reactive_navigation(
            detections,
            goal,
            start,
            image_width,
            image_height
        )

        # Add success flag
        result['success'] = True

        logger.info(f"Navigation guidance: {result['guidance']['primary']}")
        if result.get('guidance', {}).get('warnings'):
            logger.info(f"Warnings: {', '.join(result['guidance']['warnings'])}")

        return jsonify(result)

    except Exception as e:
        logger.error(f"Reactive navigation error: {e}", exc_info=True)
        return jsonify({'error': str(e), 'success': False})
