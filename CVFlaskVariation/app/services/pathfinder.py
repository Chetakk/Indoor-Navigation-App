"""
Reactive navigation service for blind navigation with dynamic obstacles.
Replaces traditional A* pathfinding with real-time obstacle avoidance.
"""

import numpy as np
from heapq import heappush, heappop
from scipy.ndimage import binary_dilation
from ..constants import (
    DEFAULT_GRID_SIZE,
    OBSTACLE_DILATION_ITERATIONS,
    PATH_SAFETY_CHECK_RADIUS
)


def create_occupancy_grid(detections, image_width, image_height, grid_size=None):
    """
    Create an occupancy grid from detections for pathfinding.

    Args:
        detections: List of detection objects with bboxes
        image_width: Width of image
        image_height: Height of image
        grid_size: Size of each grid cell in pixels (uses default if None)

    Returns:
        numpy.ndarray: 2D array where 1 = obstacle, 0 = free
    """
    if grid_size is None:
        grid_size = DEFAULT_GRID_SIZE

    # Calculate grid dimensions
    grid_width = int(np.ceil(image_width / grid_size))
    grid_height = int(np.ceil(image_height / grid_size))

    # Initialize empty grid
    grid = np.zeros((grid_height, grid_width), dtype=np.uint8)

    # Mark obstacles
    for detection in detections:
        bbox = detection['bbox']
        x1, y1, x2, y2 = bbox

        # Convert bbox to grid coordinates
        grid_x1 = int(x1 / grid_size)
        grid_y1 = int(y1 / grid_size)
        grid_x2 = int(np.ceil(x2 / grid_size))
        grid_y2 = int(np.ceil(y2 / grid_size))

        # Clamp to grid bounds
        grid_x1 = max(0, min(grid_x1, grid_width - 1))
        grid_y1 = max(0, min(grid_y1, grid_height - 1))
        grid_x2 = max(0, min(grid_x2, grid_width))
        grid_y2 = max(0, min(grid_y2, grid_height))

        # Mark cells as occupied
        grid[grid_y1:grid_y2, grid_x1:grid_x2] = 1

    # Dilate obstacles to add safety margin
    grid = binary_dilation(grid, iterations=OBSTACLE_DILATION_ITERATIONS).astype(np.uint8)

    return grid


def astar_pathfinding(grid, start, goal):
    """
    Enhanced A* pathfinding algorithm with Euclidean heuristic.

    Args:
        grid: 2D occupancy grid (0 = free, 1 = obstacle)
        start: (x, y) start position in grid coordinates
        goal: (x, y) goal position in grid coordinates

    Returns:
        list: List of (x, y) waypoints from start to goal, or None if no path
    """
    height, width = grid.shape

    # Validate start and goal
    start = (int(start[0]), int(start[1]))
    goal = (int(goal[0]), int(goal[1]))

    if not (0 <= start[0] < width and 0 <= start[1] < height):
        return None
    if not (0 <= goal[0] < width and 0 <= goal[1] < height):
        return None
    if grid[start[1], start[0]] == 1:
        return None  # Start is in obstacle
    if grid[goal[1], goal[0]] == 1:
        return None  # Goal is in obstacle

    # Enhanced heuristic function (Euclidean distance with slight overestimate for faster pathfinding)
    def heuristic(a, b):
        dx = abs(a[0] - b[0])
        dy = abs(a[1] - b[1])
        # Euclidean distance with 1.05x multiplier for faster pathfinding
        return 1.05 * np.sqrt(dx*dx + dy*dy)

    # Priority queue: (f_score, counter, current_pos)
    counter = 0
    open_set = []
    heappush(open_set, (0, counter, start))

    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, goal)}

    # Possible movements (8-directional)
    neighbors = [
        (0, 1), (1, 0), (0, -1), (-1, 0),  # Cardinal
        (1, 1), (1, -1), (-1, 1), (-1, -1)  # Diagonal
    ]

    while open_set:
        _, _, current = heappop(open_set)

        if current == goal:
            # Reconstruct path
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            return path

        for dx, dy in neighbors:
            neighbor = (current[0] + dx, current[1] + dy)

            # Check bounds
            if not (0 <= neighbor[0] < width and 0 <= neighbor[1] < height):
                continue

            # Check if obstacle
            if grid[neighbor[1], neighbor[0]] == 1:
                continue

            # Enhanced cost calculation
            # Diagonal moves cost sqrt(2), but we add penalties for:
            # 1. Direction changes (favors straighter paths)
            # 2. Proximity to obstacles (favors safer paths)
            base_cost = 1.414 if dx != 0 and dy != 0 else 1.0

            # Direction change penalty (smoother paths)
            direction_penalty = 0.0
            if current in came_from:
                prev = came_from[current]
                prev_dx = current[0] - prev[0]
                prev_dy = current[1] - prev[1]
                # If direction changed, add small penalty
                if (prev_dx, prev_dy) != (dx, dy):
                    direction_penalty = 0.2

            # Obstacle proximity penalty (safer paths)
            obstacle_penalty = 0.0
            for check_dx in [-1, 0, 1]:
                for check_dy in [-1, 0, 1]:
                    if check_dx == 0 and check_dy == 0:
                        continue
                    check_x = neighbor[0] + check_dx
                    check_y = neighbor[1] + check_dy
                    if (0 <= check_x < width and 0 <= check_y < height):
                        if grid[check_y, check_x] == 1:
                            obstacle_penalty += 0.3

            move_cost = base_cost + direction_penalty + min(obstacle_penalty, 1.0)
            tentative_g = g_score[current] + move_cost

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                counter += 1
                heappush(open_set, (f_score[neighbor], counter, neighbor))

    return None  # No path found


def calculate_path_safety(grid, path):
    """
    Calculate how safe a path is based on proximity to obstacles.

    Args:
        grid: 2D occupancy grid
        path: List of (x, y) waypoints in grid coordinates

    Returns:
        float: Safety score between 0 and 1 (higher is safer)
    """
    if not path:
        return 0.0

    safety_scores = []
    height, width = grid.shape

    for x, y in path:
        # Check surrounding cells for obstacles
        min_distance = float('inf')

        for dx in range(-PATH_SAFETY_CHECK_RADIUS, PATH_SAFETY_CHECK_RADIUS + 1):
            for dy in range(-PATH_SAFETY_CHECK_RADIUS, PATH_SAFETY_CHECK_RADIUS + 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if grid[ny, nx] == 1:  # Obstacle
                        distance = np.sqrt(dx**2 + dy**2)
                        min_distance = min(min_distance, distance)

        # Normalize safety score (further from obstacles = safer)
        safety = min(min_distance / PATH_SAFETY_CHECK_RADIUS, 1.0) if min_distance != float('inf') else 1.0
        safety_scores.append(safety)

    return np.mean(safety_scores) if safety_scores else 0.0


def convert_path_to_pixels(path_grid, grid_size):
    """
    Convert a path from grid coordinates to pixel coordinates.

    Args:
        path_grid: List of (x, y) in grid coordinates
        grid_size: Size of each grid cell in pixels

    Returns:
        list: List of [x, y] in pixel coordinates (centered in each cell)
    """
    return [[int(x * grid_size + grid_size/2), int(y * grid_size + grid_size/2)]
            for x, y in path_grid]


def calculate_reactive_navigation(detections, goal, start, image_width, image_height):
    """
    Reactive local navigation - calculates immediate safe direction toward goal.
    Designed for dynamic environments with moving obstacles.

    Args:
        detections: List of detection objects with bboxes and optional velocity
        goal: [x, y] goal position in pixel coordinates
        start: [x, y] current position in pixel coordinates
        image_width: Width of image
        image_height: Height of image

    Returns:
        dict: Navigation guidance including safe direction, obstacles, and voice commands
    """
    # Calculate direct vector to goal
    goal_vector = np.array([goal[0] - start[0], goal[1] - start[1]], dtype=float)
    distance_to_goal_pixels = np.linalg.norm(goal_vector)

    if distance_to_goal_pixels < 1:
        return {
            'reached_goal': bool(True),
            'message': 'Goal reached',
            'direction': None,
            'distance': 0,
            'obstacles': []
        }

    # Normalize goal direction
    goal_direction = goal_vector / distance_to_goal_pixels

    # Convert pixel distance to rough meters estimate
    # Note: This is still approximate as we don't have depth to goal point
    distance_to_goal_meters = distance_to_goal_pixels / 100  # rough estimate

    # Analyze obstacles in the scene
    obstacles = []
    for det in detections:
        bbox = det['bbox']
        x1, y1, x2, y2 = bbox

        # Calculate obstacle center and size
        obs_center = np.array([(x1 + x2) / 2, (y1 + y2) / 2])
        obs_width = x2 - x1
        obs_height = y2 - y1
        obs_size = max(obs_width, obs_height)

        # Vector from user to obstacle
        to_obstacle = obs_center - np.array(start)
        distance_to_obs_pixels = np.linalg.norm(to_obstacle)

        if distance_to_obs_pixels < 1:
            continue  # Skip if too close (likely invalid)

        # Normalize
        direction_to_obs = to_obstacle / distance_to_obs_pixels

        # Use real distance from depth estimation if available
        real_distance = det.get('distance')  # meters from depth estimation

        # Validate distance and use bbox heuristic fallback if needed
        if real_distance is None or real_distance <= 0:
            # Bbox heuristic: estimate distance from bbox size and position
            bbox_area = obs_width * obs_height
            image_area = image_width * image_height
            area_ratio = bbox_area / image_area

            if area_ratio > 0.01:
                # Larger objects = closer, smaller objects = farther
                real_distance = 5.0 / np.sqrt(area_ratio)

                # Adjust by vertical position (lower in frame = closer)
                bbox_center_y = (y1 + y2) / 2
                vertical_position = bbox_center_y / image_height
                position_factor = 0.7 + (vertical_position * 0.6)
                real_distance *= position_factor

                # Clamp to reasonable range
                real_distance = np.clip(real_distance, 0.5, 20.0)
            else:
                # Last resort: pixel-based estimate
                real_distance = distance_to_obs_pixels / 100  # rough pixel-to-meter

        # Calculate if obstacle is in our path (using dot product)
        alignment_with_goal = np.dot(direction_to_obs, goal_direction)

        # Check if moving (if velocity data available)
        is_moving = det.get('is_moving', False)
        velocity = det.get('velocity', [0, 0])

        obstacles.append({
            'label': det.get('class_name', det.get('label', 'object')),
            'center': obs_center.tolist(),
            'size': float(obs_size),
            'distance': float(real_distance),  # NOW IN METERS!
            'distance_pixels': float(distance_to_obs_pixels),  # Keep for legacy
            'distance_confidence': det.get('distance_confidence', 0.0),  # Confidence score
            'distance_method': det.get('distance_method', 'bbox_heuristic'),  # Estimation method
            'direction': direction_to_obs.tolist(),
            'alignment_with_goal': float(alignment_with_goal),
            'is_moving': bool(is_moving),
            'velocity': [float(v) for v in velocity],
            'bbox': [float(b) for b in bbox],
            'in_path': bool(alignment_with_goal > 0.5)  # In our forward direction
        })

    # Sort obstacles by threat level (close + in path = high threat)
    def threat_score(obs):
        threat = 0
        if obs['in_path']:
            threat += 100 / max(obs['distance'], 1)  # Closer = higher threat
        if obs['is_moving']:
            threat += 20  # Moving objects are more dangerous
        return threat

    obstacles.sort(key=threat_score, reverse=True)

    # Find safe direction using obstacle avoidance
    safe_direction = find_safe_direction(
        goal_direction,
        obstacles,
        start,
        image_width,
        image_height
    )

    # Check depth confidence - warn if using low-quality depth data
    low_confidence_obstacles = [
        obs for obs in obstacles[:5]
        if obs.get('distance_confidence', 0) < 0.3 and obs['in_path']
    ]

    # Generate voice guidance (use meters for distance)
    guidance = generate_voice_guidance(
        safe_direction,
        goal_direction,
        distance_to_goal_meters,
        obstacles,
        low_confidence_count=len(low_confidence_obstacles)
    )

    return {
        'reached_goal': bool(False),
        'safe_direction': safe_direction.tolist(),
        'goal_direction': goal_direction.tolist(),
        'distance_to_goal': float(distance_to_goal_meters),  # NOW IN METERS!
        'distance_to_goal_pixels': float(distance_to_goal_pixels),  # Keep for legacy
        'obstacles': obstacles[:5],  # Top 5 most threatening
        'guidance': guidance,
        'deviation_angle': float(np.degrees(np.arccos(np.clip(np.dot(safe_direction, goal_direction), -1, 1))))
    }


def find_safe_direction(goal_direction, obstacles, start, image_width, image_height):
    """
    Find a safe walking direction that avoids obstacles while moving toward goal.

    Args:
        goal_direction: Normalized vector toward goal
        obstacles: List of obstacle info dicts
        start: Current position [x, y]
        image_width: Image width
        image_height: Image height

    Returns:
        numpy.ndarray: Safe direction vector (normalized)
    """
    # Sample multiple candidate directions around the goal direction
    num_samples = 16
    angles = np.linspace(-np.pi/2, np.pi/2, num_samples)  # -90 to +90 degrees

    # Current goal angle
    goal_angle = np.arctan2(goal_direction[1], goal_direction[0])

    best_direction = goal_direction.copy()
    best_score = -float('inf')

    for angle_offset in angles:
        test_angle = goal_angle + angle_offset
        test_direction = np.array([np.cos(test_angle), np.sin(test_angle)])

        # Calculate score for this direction
        score = 0

        # Prefer directions close to goal (cosine similarity)
        goal_alignment = np.dot(test_direction, goal_direction)
        score += goal_alignment * 10  # High weight on goal alignment

        # Penalize based on obstacle proximity in this direction
        for obs in obstacles:
            if not obs['in_path']:
                continue  # Only care about obstacles ahead

            obs_direction = np.array(obs['direction'])
            alignment = np.dot(test_direction, obs_direction)

            if alignment > 0.3:  # Obstacle is in this direction
                # Penalize proportional to alignment and inverse of distance
                penalty = alignment * (50 / max(obs['distance'], 10))
                if obs['is_moving']:
                    penalty *= 1.5  # Extra penalty for moving obstacles
                score -= penalty

        # Check if direction leads out of bounds
        test_pos = np.array(start) + test_direction * 100  # Project 100 pixels ahead
        if test_pos[0] < 50 or test_pos[0] > image_width - 50:
            score -= 20  # Penalty for going near edges
        if test_pos[1] < 50 or test_pos[1] > image_height - 50:
            score -= 20

        if score > best_score:
            best_score = score
            best_direction = test_direction

    return best_direction


def generate_voice_guidance(safe_direction, goal_direction, distance_to_goal, obstacles, low_confidence_count=0):
    """
    Generate human-readable voice guidance for navigation.

    Args:
        safe_direction: Safe walking direction
        goal_direction: Direct direction to goal
        distance_to_goal: Distance to goal in meters
        obstacles: List of obstacles
        low_confidence_count: Number of obstacles with low depth confidence

    Returns:
        dict: Voice guidance with primary message and warnings
    """
    # Calculate deviation from goal
    deviation_angle = np.degrees(np.arccos(np.clip(np.dot(safe_direction, goal_direction), -1, 1)))

    # Determine if we need to deviate from straight path
    if deviation_angle < 10:
        direction_text = "Walk straight ahead"
    elif deviation_angle < 30:
        # Determine left or right
        cross = np.cross(goal_direction, safe_direction)
        side = "slightly left" if cross > 0 else "slightly right"
        direction_text = f"Bear {side}"
    else:
        cross = np.cross(goal_direction, safe_direction)
        side = "left" if cross > 0 else "right"
        direction_text = f"Turn {side}"

    # Distance is now in REAL METERS from depth estimation!
    # No more pixel conversions needed
    if distance_to_goal < 2:
        distance_text = "almost there"
    elif distance_to_goal < 5:
        distance_text = f"{int(distance_to_goal)} meters"
    else:
        distance_text = f"{int(distance_to_goal)} meters ahead"

    # Check for immediate obstacles (distance now in METERS!)
    warnings = []
    for obs in obstacles[:3]:  # Check top 3 threats
        if obs['in_path'] and obs['distance'] < 3:  # Close obstacle in path (3 meters)
            # Determine position relative to user
            obs_dir = np.array(obs['direction'])
            cross = np.cross(safe_direction, obs_dir)
            side = "left" if cross > 0 else "right"

            label = obs['label']
            moving_text = "moving " if obs['is_moving'] else ""
            warnings.append(f"{moving_text}{label} on {side}")

    # Add depth confidence warning if depth data is uncertain
    if low_confidence_count > 0:
        warnings.append("distance approximate, low sensor confidence")

    # Build complete guidance
    primary_message = f"{direction_text}, {distance_text}"

    return {
        'primary': primary_message,
        'warnings': warnings,
        'full_message': primary_message + (", " + ", ".join(warnings) if warnings else "")
    }
