"""
Constants used throughout the blind navigation application.
"""

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

# Detection thresholds
DEFAULT_CONFIDENCE_THRESHOLD = 0.30
DEFAULT_IOU_THRESHOLD = 0.65
MAX_DETECTIONS = 50

# Tracking parameters
TRACK_HISTORY_LENGTH = 30  # Number of positions to keep in trajectory
MAX_TRACKER_AGE = 10  # Max frames to keep alive a track without detections (reduced from 30 to prevent false matches)
MIN_TRACK_INIT = 2  # Number of consecutive detections before track is confirmed (reduced from 3 for faster initialization)
NMS_MAX_OVERLAP = 0.7  # Non-max suppression overlap threshold
MAX_COSINE_DISTANCE = 0.25  # Cosine distance threshold for matching (reduced from 0.4 to be more strict on appearance)
NN_BUDGET = 100  # Maximum size of appearance descriptor gallery

# Collision detection
USER_ZONE_RADIUS_FACTOR = 0.15  # 15% of frame size
COLLISION_PREDICTION_FRAMES = 10  # How many frames ahead to predict
STATIONARY_THRESHOLD = 5  # Pixels displacement threshold

# Speed classification
SPEED_SLOW_THRESHOLD = 2.0  # pixels per frame
SPEED_MEDIUM_THRESHOLD = 10.0  # pixels per frame

# Pathfinding
DEFAULT_GRID_SIZE = 20  # pixels per grid cell
OBSTACLE_DILATION_ITERATIONS = 1  # Safety margin around obstacles
PATH_SAFETY_CHECK_RADIUS = 3  # Grid cells to check around path

# Image processing
MAX_IMAGE_DIMENSION = 640  # Resize larger images for faster inference
ROTATION_DETECTION_THRESHOLD = 0.75  # Aspect ratio threshold for rotation detection
ROTATION_TEST_SIZE = (320, 240)  # Size for quick rotation detection test
