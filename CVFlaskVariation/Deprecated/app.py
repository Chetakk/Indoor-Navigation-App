from flask import Flask, render_template, jsonify, request, session
from flask_cors import CORS
import cv2
import numpy as np
from ultralytics import YOLO
import base64
from io import BytesIO
from PIL import Image
import logging
from deep_sort_realtime.deepsort_tracker import DeepSort
from collections import defaultdict, deque
import time
from scipy.spatial.distance import euclidean
from scipy.ndimage import binary_dilation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-here-change-in-production'  # Required for session management

# Enable CORS for all routes to allow frontend communication
CORS(app, resources={
    r"/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Initialize DeepSORT tracker
# Store trackers per session to support multiple users
trackers = {}
track_histories = defaultdict(lambda: deque(maxlen=30))  # Store last 30 positions for each track

def get_tracker(session_id):
    """Get or create a tracker for a session"""
    if session_id not in trackers:
        import torch
        use_gpu = torch.cuda.is_available()

        trackers[session_id] = DeepSort(
            max_age=30,  # Max frames to keep alive a track without detections
            n_init=3,    # Number of consecutive detections before track is confirmed
            nms_max_overlap=0.7,  # Non-max suppression overlap threshold
            max_cosine_distance=0.4,  # Cosine distance threshold for matching
            nn_budget=100,  # Maximum size of appearance descriptor gallery
            embedder="mobilenet",  # Use MobileNet for feature extraction
            half=True,  # Use half precision for speed
            embedder_gpu=use_gpu  # Use GPU if available
        )
        logger.info(f"Created new tracker for session: {session_id} (GPU: {use_gpu})")
    return trackers[session_id]

# Class blacklist - add classes you want to filter out
BLACKLISTED_CLASSES = {
    'house',
    'office building',
    'building',
    'skyscraper',
    'tower',
    # Note: Clothing items removed from blacklist - they're valid detections
    # Face/person deduplication is handled by spatial overlap logic instead
}

# Class mapping - combine similar classes into one
CLASS_MAPPING = {
    # All human-related classes map to "person"
    'man': 'person',
    'woman': 'person',
    'boy': 'person',
    'girl': 'person',
    'human face': 'person',
    'face': 'person',
    'head': 'person',
    'human': 'person',
    # Add more mappings as needed
}

# Load your trained YOLO11 model with GPU acceleration
import torch

# Global device variable
# TEMPORARY: Force CPU if GPU is causing hangs
# device = 'cuda' if torch.cuda.is_available() else 'cpu'
device = 'cpu'  # TODO: Debug GPU hanging issue
logger.info(f"🚀 Using device: {device} (GPU temporarily disabled for debugging)")

if torch.cuda.is_available():
    logger.info(f"🎮 GPU Detected: {torch.cuda.get_device_name(0)}")
    logger.info(f"🎮 GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
else:
    logger.warning("⚠️ No GPU detected - using CPU (slower performance)")

try:
    # Load model
    model = YOLO('yolov8x-oiv7.pt')

    # FORCE the model to use CPU by setting it after loading
    # This prevents the GPU hang issue
    model.to('cpu')

    logger.info(f"✅ Model loaded successfully on CPU (GPU disabled due to hang issue)")

except Exception as e:
    logger.error(f"❌ Error loading model: {e}")
    # Fallback to a default model if your trained model isn't available
    model = YOLO('yolov8x-oiv7.pt')
    model.to('cpu')
    logger.info("Using fallback model on CPU")

def is_class_blacklisted(class_name):
    """Check if a class is in the blacklist"""
    return class_name.lower() in BLACKLISTED_CLASSES

def normalize_class_name(class_name):
    """Normalize class name using mapping (e.g., man/woman/face -> person)"""
    normalized = class_name.lower()
    return CLASS_MAPPING.get(normalized, class_name)

def calculate_iou(box1, box2):
    """
    Calculate Intersection over Union (IoU) between two bounding boxes
    Boxes are in [x1, y1, x2, y2] format
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

def deduplicate_same_class_detections(detections, iou_threshold=0.5):
    """
    Remove duplicate detections of the SAME class that overlap significantly.
    For example, if "person" and "face" both map to "person" and overlap,
    keep only the one with higher confidence.

    Args:
        detections: List of detection dicts with 'class_name', 'bbox_xyxy', 'confidence'
        iou_threshold: IoU threshold for considering boxes as duplicates

    Returns:
        Deduplicated list of detections
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

def calculate_movement(trajectory):
    """
    Calculate movement information from trajectory
    Returns direction, speed, and movement type
    """
    if len(trajectory) < 2:
        return {
            'direction': 'stationary',
            'speed': 0,
            'displacement': 0,
            'angle': 0,
            'velocity_x': 0,
            'velocity_y': 0
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

    # Determine direction
    if displacement < 5:  # Threshold for stationary
        direction = 'stationary'
    elif -45 <= angle < 45:
        direction = 'moving_right'
    elif 45 <= angle < 135:
        direction = 'moving_down'
    elif angle >= 135 or angle < -135:
        direction = 'moving_left'
    else:
        direction = 'moving_up'

    # Classify speed
    if speed < 2:
        speed_class = 'slow'
    elif speed < 10:
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

def predict_collision(track_center, track_movement, image_width, image_height, prediction_frames=10):
    """
    Predict if an object will collide with the user (camera center)

    Args:
        track_center: (x, y) current position
        track_movement: movement info with velocity
        image_width: width of image
        image_height: height of image
        prediction_frames: how many frames ahead to predict

    Returns:
        dict with collision prediction info
    """
    # Camera center (user position)
    camera_center_x = image_width / 2
    camera_center_y = image_height / 2

    # Define the "user zone" - center area of the frame
    user_zone_radius = min(image_width, image_height) * 0.15  # 15% of frame

    # Current distance to user
    current_distance = euclidean(track_center, (camera_center_x, camera_center_y))

    # If object is stationary, no collision
    if track_movement['direction'] == 'stationary':
        return {
            'collision_risk': False,
            'time_to_collision': None,
            'collision_severity': 'none',
            'predicted_position': track_center,
            'current_distance': float(current_distance)
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
    if is_approaching and velocity_x != 0 or velocity_y != 0:
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

def create_occupancy_grid(detections, image_width, image_height, grid_size=20):
    """
    Create an occupancy grid from detections for pathfinding

    Args:
        detections: list of detection objects with bboxes
        image_width: width of image
        image_height: height of image
        grid_size: size of each grid cell in pixels

    Returns:
        2D numpy array where 1 = obstacle, 0 = free
    """
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
    grid = binary_dilation(grid, iterations=1).astype(np.uint8)

    return grid

def astar_pathfinding(grid, start, goal):
    """
    A* pathfinding algorithm

    Args:
        grid: 2D occupancy grid (0 = free, 1 = obstacle)
        start: (x, y) start position in grid coordinates
        goal: (x, y) goal position in grid coordinates

    Returns:
        List of (x, y) waypoints from start to goal, or None if no path
    """
    from heapq import heappush, heappop

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

    # Heuristic function (Manhattan distance)
    def heuristic(a, b):
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

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

            # Calculate tentative g_score
            # Diagonal moves cost more (sqrt(2) ≈ 1.414)
            move_cost = 1.414 if dx != 0 and dy != 0 else 1.0
            tentative_g = g_score[current] + move_cost

            if neighbor not in g_score or tentative_g < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + heuristic(neighbor, goal)
                counter += 1
                heappush(open_set, (f_score[neighbor], counter, neighbor))

    return None  # No path found

def fix_image_orientation(image):
    """
    Fix image orientation based on EXIF data
    This handles phone rotation issues
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
    Determine rotation needed based on device orientation data
    
    orientation_data should contain:
    - alpha: rotation around z-axis (compass heading) 0-360°
    - beta: rotation around x-axis (front-to-back tilt) -180° to 180°
    - gamma: rotation around y-axis (left-to-right tilt) -90° to 90°
    - screen_orientation: screen.orientation.angle (0, 90, 180, 270)
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
    Apply rotation correction to image based on degrees
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

def detect_and_fix_rotation(image_np):
    """
    Detect if image needs rotation based on aspect ratio and content
    This is a fallback when gyroscope data isn't available
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
            orig_results = model(orig_small, verbose=False, conf=0.3)
            rot90_results = model(rot90_small, verbose=False, conf=0.3)
            rot270_results = model(rot270_small, verbose=False, conf=0.3)
            
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/test_connection', methods=['GET', 'POST'])
def test_connection():
    """Simple test endpoint to verify Flask → Frontend communication"""
    logger.info("🧪 Test connection endpoint called")
    response_data = {
        'success': True,
        'message': 'Flask backend is responding correctly',
        'timestamp': time.time(),
        'method': request.method
    }
    logger.info(f"📤 Sending test response: {response_data}")
    return jsonify(response_data)

@app.route('/detect_image', methods=['POST'])
def detect_image():
    """Process image from browser and return detection results with tracking"""
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
        # Lower confidence for blind navigation safety - detect potential obstacles early
        logger.info(f"🔍 Running YOLO detection on image shape: {image_bgr.shape}")
        logger.info(f"🔍 Image dtype: {image_bgr.dtype}, min: {image_bgr.min()}, max: {image_bgr.max()}")

        # Optimize: Resize image if too large to speed up inference
        max_dimension = 640
        height, width = image_bgr.shape[:2]
        if max(height, width) > max_dimension:
            scale = max_dimension / max(height, width)
            new_width = int(width * scale)
            new_height = int(height * scale)
            logger.info(f"🔍 Resizing image from {width}x{height} to {new_width}x{new_height} for faster inference")
            image_bgr = cv2.resize(image_bgr, (new_width, new_height))

        try:
            # Simplest possible inference call - force CPU device
            # Increased IOU threshold to reduce duplicate detections
            inference_start = time.time()
            logger.info("🔍 Calling model() with CPU device...")
            results = model(image_bgr, verbose=False, device='cpu', conf=0.30, iou=0.65, max_det=50)
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
                    class_name = model.names[int(box.cls[0])]

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
                        'class_id': int(box.cls[0])
                    })

        # Deduplicate detections of the SAME class that overlap
        # This removes cases where "person" + "face" → both become "person" and overlap
        raw_detections_before_dedup = len(raw_detections)
        raw_detections = deduplicate_same_class_detections(raw_detections, iou_threshold=0.5)
        dedup_removed = raw_detections_before_dedup - len(raw_detections)
        if dedup_removed > 0:
            logger.info(f"🔄 Deduplication removed {dedup_removed} overlapping same-class detections")

        # Apply object tracking if enabled
        tracked_objects = []
        if tracking_enabled and len(raw_detections) > 0:
            tracker = get_tracker(session_id)

            # Prepare detections for DeepSORT (bbox in ltwh format, confidence, class)
            deepsort_input = [
                (det['bbox'], det['confidence'], det['class_name'])
                for det in raw_detections
            ]

            # Update tracker with current frame
            tracks = tracker.update_tracks(deepsort_input, frame=image_bgr)

            # Process tracked objects
            for track in tracks:
                if not track.is_confirmed():
                    continue

                track_id = track.track_id
                ltrb = track.to_ltrb()  # Get bounding box in [left, top, right, bottom] format

                # Get detection info
                det_class = track.det_class if hasattr(track, 'det_class') else 'unknown'
                det_conf = track.det_conf if hasattr(track, 'det_conf') else 0.0

                # Calculate center point for trajectory
                center_x = (ltrb[0] + ltrb[2]) / 2
                center_y = (ltrb[1] + ltrb[3]) / 2

                # Store position history
                track_key = f"{session_id}_{track_id}"
                track_histories[track_key].append((center_x, center_y))

                # Get trajectory (last N positions)
                trajectory = list(track_histories[track_key])

                # Calculate movement direction and speed
                movement_info = calculate_movement(trajectory)

                # Predict collision
                collision_info = predict_collision(
                    (center_x, center_y),
                    movement_info,
                    image_np.shape[1],
                    image_np.shape[0],
                    prediction_frames=10
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

@app.route('/get_classes')
def get_classes():
    """Get available object classes (excluding blacklisted ones)"""
    try:
        all_classes = list(model.names.values())
        # Filter out blacklisted classes
        available_classes = [cls for cls in all_classes if not is_class_blacklisted(cls)]
        
        return jsonify({
            'classes': available_classes, 
            'success': True,
            'total_classes': len(all_classes),
            'available_classes': len(available_classes),
            'blacklisted_classes': list(BLACKLISTED_CLASSES)
        })
    except Exception as e:
        logger.error(f"Error getting classes: {e}")
        return jsonify({'error': str(e), 'success': False})

@app.route('/blacklist', methods=['GET', 'POST'])
def manage_blacklist():
    """Manage the class blacklist"""
    global BLACKLISTED_CLASSES
    
    if request.method == 'GET':
        return jsonify({
            'blacklisted_classes': list(BLACKLISTED_CLASSES),
            'success': True
        })
    
    elif request.method == 'POST':
        try:
            data = request.get_json()
            action = data.get('action')
            class_name = data.get('class_name', '').lower()
            
            if action == 'add' and class_name:
                BLACKLISTED_CLASSES.add(class_name)
                logger.info(f"Added '{class_name}' to blacklist")
                return jsonify({
                    'message': f"Added '{class_name}' to blacklist",
                    'blacklisted_classes': list(BLACKLISTED_CLASSES),
                    'success': True
                })
            
            elif action == 'remove' and class_name:
                BLACKLISTED_CLASSES.discard(class_name)
                logger.info(f"Removed '{class_name}' from blacklist")
                return jsonify({
                    'message': f"Removed '{class_name}' from blacklist",
                    'blacklisted_classes': list(BLACKLISTED_CLASSES),
                    'success': True
                })
            
            elif action == 'set' and 'classes' in data:
                BLACKLISTED_CLASSES = set(cls.lower() for cls in data['classes'])
                logger.info(f"Updated blacklist to: {list(BLACKLISTED_CLASSES)}")
                return jsonify({
                    'message': 'Blacklist updated',
                    'blacklisted_classes': list(BLACKLISTED_CLASSES),
                    'success': True
                })
            
            else:
                return jsonify({'error': 'Invalid action or missing class_name', 'success': False})
                
        except Exception as e:
            logger.error(f"Error managing blacklist: {e}")
            return jsonify({'error': str(e), 'success': False})

@app.route('/test_audio')
def test_audio():
    """Test endpoint to return sample detection data for audio testing"""
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

@app.route('/health')
def health_check():
    """Health check endpoint"""
    import torch

    gpu_info = {}
    if torch.cuda.is_available():
        gpu_info = {
            'gpu_available': True,
            'gpu_name': torch.cuda.get_device_name(0),
            'gpu_memory_total_gb': round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
            'gpu_memory_allocated_gb': round(torch.cuda.memory_allocated(0) / 1024**3, 2),
            'gpu_memory_cached_gb': round(torch.cuda.memory_reserved(0) / 1024**3, 2),
            'device_in_use': device
        }
    else:
        gpu_info = {
            'gpu_available': False,
            'device_in_use': 'cpu',
            'warning': 'No GPU detected - performance may be slower'
        }

    return jsonify({
        'status': 'healthy',
        'model_loaded': model is not None,
        'model_classes': len(model.names) if model else 0,
        'model_name': model.model_name if hasattr(model, 'model_name') else 'YOLO11',
        'available_classes': list(model.names.values())[:10],  # Show first 10 classes
        'blacklisted_classes': list(BLACKLISTED_CLASSES),
        'blacklist_count': len(BLACKLISTED_CLASSES),
        **gpu_info
    })

@app.route('/model_info')
def model_info():
    """Get model information"""
    try:
        all_classes = list(model.names.values())
        available_classes = [cls for cls in all_classes if not is_class_blacklisted(cls)]

        return jsonify({
            'model_loaded': model is not None,
            'all_classes': all_classes,
            'available_classes': available_classes,
            'total_class_count': len(all_classes),
            'available_class_count': len(available_classes),
            'blacklisted_classes': list(BLACKLISTED_CLASSES),
            'blacklisted_count': len(BLACKLISTED_CLASSES),
            'success': True
        })
    except Exception as e:
        logger.error(f"Error getting model info: {e}")
        return jsonify({'error': str(e), 'success': False})

@app.route('/reset_tracking', methods=['POST'])
def reset_tracking():
    """Reset tracking for current session"""
    try:
        if 'session_id' in session:
            session_id = session['session_id']

            # Remove tracker for this session
            if session_id in trackers:
                del trackers[session_id]
                logger.info(f"Deleted tracker for session: {session_id}")

            # Clear track histories for this session
            keys_to_delete = [key for key in track_histories.keys() if key.startswith(f"{session_id}_")]
            for key in keys_to_delete:
                del track_histories[key]

            # Create new session ID
            session['session_id'] = str(time.time())

            return jsonify({
                'message': 'Tracking reset successfully',
                'success': True,
                'new_session_id': session['session_id']
            })
        else:
            return jsonify({
                'message': 'No active tracking session',
                'success': True
            })
    except Exception as e:
        logger.error(f"Error resetting tracking: {e}")
        return jsonify({'error': str(e), 'success': False})

@app.route('/tracking_stats')
def tracking_stats():
    """Get tracking statistics for current session"""
    try:
        if 'session_id' not in session:
            return jsonify({
                'active_tracks': 0,
                'total_sessions': len(trackers),
                'success': True
            })

        session_id = session['session_id']

        # Count active tracks for this session
        active_tracks = sum(1 for key in track_histories.keys() if key.startswith(f"{session_id}_"))

        return jsonify({
            'session_id': session_id,
            'active_tracks': active_tracks,
            'total_sessions': len(trackers),
            'has_tracker': session_id in trackers,
            'success': True
        })
    except Exception as e:
        logger.error(f"Error getting tracking stats: {e}")
        return jsonify({'error': str(e), 'success': False})

@app.route('/calculate_path', methods=['POST'])
def calculate_path():
    """Calculate navigation path avoiding obstacles"""
    try:
        data = request.get_json()

        if not data or 'detections' not in data or 'goal' not in data:
            return jsonify({'error': 'Missing detections or goal', 'success': False})

        detections = data['detections']
        goal = data['goal']  # (x, y) in pixel coordinates
        start = data.get('start')  # Optional start position, defaults to center bottom
        image_width = data.get('image_width', 640)
        image_height = data.get('image_height', 480)
        grid_size = data.get('grid_size', 20)

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
                'grid_shape': grid.shape
            })

        # Convert grid coordinates back to pixel coordinates
        path_pixels = [[int(x * grid_size + grid_size/2), int(y * grid_size + grid_size/2)]
                       for x, y in path_grid]

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

def calculate_path_safety(grid, path):
    """Calculate how safe a path is based on proximity to obstacles"""
    if not path:
        return 0.0

    safety_scores = []
    height, width = grid.shape

    for x, y in path:
        # Check surrounding cells for obstacles
        min_distance = float('inf')

        for dx in range(-3, 4):
            for dy in range(-3, 4):
                nx, ny = x + dx, y + dy
                if 0 <= nx < width and 0 <= ny < height:
                    if grid[ny, nx] == 1:  # Obstacle
                        distance = np.sqrt(dx**2 + dy**2)
                        min_distance = min(min_distance, distance)

        # Normalize safety score (further from obstacles = safer)
        safety = min(min_distance / 3.0, 1.0) if min_distance != float('inf') else 1.0
        safety_scores.append(safety)

    return np.mean(safety_scores) if safety_scores else 0.0

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    import torch

    logger.info("=" * 70)
    logger.info("🚀 Starting YOLO11 Flask Application for Blind Navigation")
    logger.info("=" * 70)

    # GPU Status
    if torch.cuda.is_available():
        logger.info(f"🎮 GPU: {torch.cuda.get_device_name(0)}")
        logger.info(f"🎮 VRAM: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
        logger.info(f"✅ CUDA Version: {torch.version.cuda}")
    else:
        logger.warning("⚠️  NO GPU DETECTED - Using CPU (performance will be slower)")
        logger.warning("⚠️  For real-time blind navigation, GPU is highly recommended")

    # Model Info
    logger.info(f"📦 Model classes available: {len(model.names)}")
    logger.info(f"🚫 Blacklisted classes: {len(BLACKLISTED_CLASSES)}")
    logger.info(f"🔄 Class mappings: {len(CLASS_MAPPING)} (e.g., man/woman → person)")

    # Endpoints
    logger.info("\n📡 Available endpoints:")
    logger.info("  🏠 / - Main application")
    logger.info("  🔍 /detect_image - Real-time object detection (800ms)")
    logger.info("  💚 /health - Health check with GPU status")
    logger.info("  📊 /model_info - Model information")
    logger.info("  📋 /get_classes - Available object classes (filtered)")
    logger.info("  🚫 /blacklist - Manage class blacklist (GET/POST)")

    logger.info("\n" + "=" * 70)
    logger.info("🦯 Optimized for REAL-TIME blind indoor navigation")
    logger.info("=" * 70 + "\n")

    # Disable debug mode reloader which can cause model loading issues
    app.run(debug=False, threaded=True, host='192.168.1.14', port=5000, use_reloader=False, ssl_context=("cert.pem", "key.pem"))