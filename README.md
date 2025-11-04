# Indoor Navigation App for Visually Impaired Users

A Flask-based real-time object detection and navigation system designed for blind and visually impaired users. This application uses YOLO11 for object detection, DeepSORT for tracking, and provides audio announcements with collision detection and reactive navigation guidance.

## 🎯 Features

### Core Capabilities
- **Real-time Object Detection**: YOLO11-based detection with high accuracy
- **Object Tracking**: DeepSORT tracking with MobileNet embeddings for persistent object identification
- **Collision Detection**: Predictive collision warnings with movement analysis
- **Reactive Navigation**: Real-time obstacle avoidance with natural language guidance
- **Audio Announcements**: Priority-based text-to-speech with Web Speech API
- **Voice Commands**: Hands-free control with speech recognition
- **Gyroscope Integration**: Automatic image rotation correction based on device orientation
- **SSL/HTTPS Support**: Secure communication for production use

### Accessibility Features
- **Blind Mode**: Optimized settings for visually impaired users
- **Auto-start Detection**: Camera and detection start automatically on mobile devices
- **Priority Audio Queue**: Critical warnings interrupt normal announcements
- **Perspective-aware Directions**: Uses "approaching/receding" instead of confusing "up/down"
- **Distance-based Announcements**: Closer objects announced more frequently

## 🛠️ Tech Stack

### Backend
- **Python 3.x**
- **Flask**: Web framework
- **PyTorch**: Deep learning framework (with CUDA support)
- **Ultralytics YOLO**: YOLO11 model (yolov8x-oiv7.pt)
- **OpenCV**: Image processing
- **DeepSORT**: Object tracking with MobileNet embeddings
- **NumPy, SciPy**: Scientific computing
- **Flask-CORS**: Cross-origin resource sharing

### Frontend
- **JavaScript ES6 Modules**: Modular architecture
- **HTML5 Canvas**: Video rendering and visualization
- **Web Speech API**: Text-to-speech and speech recognition
- **MediaDevices API**: Camera access
- **DeviceOrientation API**: Gyroscope data

### ML Model
- **YOLO11**: Object detection model (Open Images V7 dataset)
- **DeepSORT**: Multi-object tracking algorithm
- **MobileNet**: Feature embeddings for tracking

## 📋 Prerequisites

- Python 3.8 or higher
- pip package manager
- Webcam or camera-enabled device
- Modern web browser with camera and microphone permissions
- (Optional) NVIDIA GPU with CUDA 11.8+ for faster inference

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Indoor-Navigation-App.git
cd Indoor-Navigation-App/CVFlaskVariation
```

### 2. Create Virtual Environment

```bash
python -m venv venv

# On Windows
venv\Scripts\activate

# On macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. (Optional) GPU Setup

For NVIDIA GPU acceleration:

1. Install CUDA Toolkit 11.8 or 12.1 from [NVIDIA](https://developer.nvidia.com/cuda-downloads)
2. Install cuDNN library
3. Install PyTorch with CUDA support:
   ```bash
   pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
   ```
4. Verify GPU:
   ```bash
   python -c "import torch; print(torch.cuda.is_available())"
   ```

**Expected speedup**: 5-10x faster inference with GPU

### 5. (Optional) SSL Certificate Setup

For HTTPS support, generate self-signed certificates:

```bash
openssl req -x509 -newkey rsa:4096 -nodes -out cert.pem -keyout key.pem -days 365
```

Place `cert.pem` and `key.pem` in the `CVFlaskVariation` directory.

## ⚙️ Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Flask Settings
FLASK_ENV=development  # development, production, or testing
FLASK_HOST=192.168.1.14  # Your server IP address
FLASK_PORT=5000
FLASK_DEBUG=false

# SSL Settings
USE_SSL=true
SSL_CERT=cert.pem
SSL_KEY=key.pem

# Model Settings
MODEL_PATH=yolov8x-oiv7.pt
FORCE_CPU=false  # Set to true to force CPU even if GPU available

# Accessibility Settings
BLIND_MODE_ENABLED=true
AUTO_START_DETECTION=true
VOICE_COMMANDS_ENABLED=true
AUDIO_FEEDBACK_ENABLED=true

# Audio Settings
SPEECH_RATE=1.0
SPEECH_PITCH=1.0
SPEECH_VOLUME=1.0

# Detection Settings
ANNOUNCE_DELAY_MS=3000
ANNOUNCE_PRIORITY_THRESHOLD=0.7
ANNOUNCE_COLLISION_WARNINGS=true
```

### Model Configuration

The default model is `yolov8x-oiv7.pt` (Open Images V7). You can:
- Use a different YOLO model by setting `MODEL_PATH`
- Place custom models in the `CVFlaskVariation` directory
- Modify blacklisted classes in `app/constants.py`

## 🎮 Usage

### Starting the Server

```bash
python run.py
```

The server will start on `http://FLASK_HOST:FLASK_PORT` (default: `http://192.168.1.14:5000`)

### Accessing the Application

1. Open a web browser on your device (mobile or desktop)
2. Navigate to `https://YOUR_SERVER_IP:5000` (or `http://` if SSL disabled)
3. Allow camera and microphone permissions when prompted
4. The detection will start automatically on mobile devices

### Voice Commands

- **"start"** or **"begin"**: Start object detection
- **"stop"** or **"pause"**: Stop detection
- **"where"** or **"what"**: Announce currently detected objects
- **"find [object]"**: Navigate to a specific object (e.g., "find door")
- **"audio on/off"**: Toggle audio announcements
- **"help"**: Show available commands

### Keyboard Shortcuts

- **Spacebar**: Toggle camera detection on/off

### Navigation Mode

1. Click on the video canvas to set a navigation goal
2. The system will provide real-time guidance:
   - "Walk straight ahead, 3 meters"
   - "Bear slightly left, person on right"
   - "Turn right, 5 meters ahead, moving car on left"
3. Navigation updates every 500ms for dynamic obstacle avoidance

## 📡 API Endpoints

### Detection
- `POST /detect_image` - Process image and return detections with tracking
- `GET /test_audio` - Return sample detection data for audio testing

### Health & Info
- `GET /` - Render main application page
- `GET /health` - Health check with GPU and model information
- `GET/POST /test_connection` - Test Flask-frontend communication

### Model Management
- `GET /get_classes` - Get available object classes (excluding blacklisted)
- `GET /model_info` - Get detailed model information
- `GET/POST /blacklist` - Manage class blacklist (add/remove/set)

### Tracking
- `POST /reset_tracking` - Reset object tracking for current session
- `GET /tracking_stats` - Get tracking statistics for current session

### Navigation
- `POST /navigate_reactive` - Calculate safe immediate direction with real-time obstacle avoidance
- `POST /calculate_path` - [DEPRECATED] Static A* pathfinding

### Example API Request

```bash
curl -X POST http://localhost:5000/detect_image \
  -H "Content-Type: application/json" \
  -d '{"image": "base64_encoded_image_data"}'
```

## 📁 Project Structure

```
CVFlaskVariation/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Configuration classes
│   ├── constants.py             # Global constants
│   ├── models/                  # Data models
│   ├── routes/                  # API endpoints
│   │   ├── detection.py         # Object detection endpoint
│   │   ├── health.py            # Health check & main page
│   │   ├── model.py             # Model info & blacklist
│   │   ├── navigation.py        # Pathfinding endpoint
│   │   └── tracking.py          # Tracking management
│   ├── services/                # Business logic
│   │   ├── collision_detector.py  # Collision prediction
│   │   ├── object_tracker.py      # DeepSORT tracking
│   │   ├── pathfinder.py          # Reactive navigation
│   │   └── yolo_detector.py       # YOLO inference
│   ├── static/
│   │   └── js/
│   │       ├── main.js          # Application entry point
│   │       └── modules/
│   │           ├── audio.js     # Text-to-speech & audio
│   │           ├── camera.js    # Camera & detection loop
│   │           ├── detection.js # Detection processing
│   │           ├── gyroscope.js # Gyroscope tracking
│   │           ├── pathfinding.js # Navigation paths
│   │           ├── tracking.js  # Tracking state
│   │           └── ui.js        # UI rendering & stats
│   ├── templates/
│   │   └── index.html           # Main HTML page
│   └── utils/                   # Helper functions
│       ├── filtering.py         # Detection filtering
│       ├── geometry.py          # Geometric calculations
│       └── image_processing.py  # Image transformations
├── docs/                        # Documentation files
├── run.py                       # Application entry point
├── test_model.py                # Model testing script
├── requirements.txt             # Python dependencies
├── Changelog.org                # Project changelog
├── Documentation.org            # Project documentation
└── DEVELOPER_HANDBOOK.org       # Developer reference
```

## 🔧 Development

### Testing the Model

```bash
python test_model.py
```

This script tests YOLO model inference and GPU availability.

### Running in Development Mode

```bash
export FLASK_ENV=development
export FLASK_DEBUG=true
python run.py
```

### Code Structure

- **Backend**: Follows Flask application factory pattern
- **Frontend**: Modular ES6 JavaScript architecture
- **Services**: Singleton pattern for YOLO detector and tracking manager
- **Routes**: RESTful API endpoints with error handling

### Key Algorithms

1. **Object Detection**: YOLO11 inference with confidence filtering
2. **Tracking**: DeepSORT with Kalman filtering and Hungarian algorithm
3. **Collision Prediction**: Trajectory analysis with user zone detection
4. **Reactive Navigation**: Direction sampling with obstacle avoidance

## 📚 Documentation

- **Developer Handbook**: `CVFlaskVariation/DEVELOPER_HANDBOOK.org` - Complete function reference
- **Project Documentation**: `CVFlaskVariation/Documentation.org` - System architecture
- **Changelog**: `CVFlaskVariation/Changelog.org` - Development history
- **Zettelkasten**: `CVFlaskVariation/zettelkasten/` - Deep knowledge base

## 🐛 Troubleshooting

### Camera Not Working
- Ensure browser permissions are granted
- Try accessing via HTTPS (required for camera on some browsers)
- Check browser compatibility (Chrome, Firefox, Safari recommended)

### GPU Not Detected
- Verify CUDA installation: `nvidia-smi`
- Check PyTorch CUDA: `python -c "import torch; print(torch.cuda.is_available())"`
- Set `FORCE_CPU=false` in environment variables

### SSL Certificate Errors
- Generate new certificates if expired
- Ensure `cert.pem` and `key.pem` are in the project root
- Set `USE_SSL=false` to disable SSL

### Slow Performance
- Enable GPU acceleration (see GPU Setup section)
- Reduce detection confidence threshold in `app/constants.py`
- Increase detection interval in `app/static/js/modules/camera.js`

## 🤝 Contributing

Contributions are welcome! Please follow these guidelines:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines

- Follow PEP 8 for Python code
- Use ES6 modules for JavaScript
- Update `Changelog.org` with changes
- Update `Documentation.org` for new features
- Test on both mobile and desktop browsers

## 📝 License

[Add your license here]

## 🙏 Acknowledgments

- **Ultralytics**: YOLO implementation
- **DeepSORT**: Object tracking algorithm
- **Open Images V7**: Dataset for object detection model
- **Flask**: Web framework

## 📞 Support

For issues, questions, or contributions, please open an issue on GitHub.

---

**Version**: 1.2  
**Last Updated**: 2025-10-15  
**Status**: Active Development
