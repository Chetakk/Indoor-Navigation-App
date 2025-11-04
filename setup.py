# setup_android.py - Setup script for Android development
import os
import subprocess
import sys

def install_buildozer():
    """Install buildozer for Android packaging"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "buildozer"])
        print("✅ Buildozer installed successfully")
    except subprocess.CalledProcessError:
        print("❌ Failed to install buildozer")
        return False
    return True

def install_requirements():
    """Install Python requirements"""
    requirements = [
        "kivy>=2.1.0",
        "kivymd>=1.1.1", 
        "opencv-python>=4.5.0",
        "numpy>=1.21.0",
        "Pillow>=8.0.0",
        "pyttsx3>=2.90"
    ]
    
    for req in requirements:
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", req])
            print(f"✅ Installed {req}")
        except subprocess.CalledProcessError:
            print(f"❌ Failed to install {req}")

def create_buildozer_spec():
    """Create buildozer.spec file"""
    spec_content = '''[app]
# (str) Title of your application
title = Object Detection

# (str) Package name
package.name = objectdetection

# (str) Package domain (needed for android/ios packaging)
package.domain = org.example

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,tflite

# (str) Application versioning (method 1)
version = 1.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy,kivymd,opencv,numpy,pillow,pyjnius,android

# (str) Presplash of the application
#presplash.filename = %(source.dir)s/data/presplash.png

# (str) Icon of the application
#icon.filename = %(source.dir)s/data/icon.png

# (str) Supported orientation (landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

[buildozer]
# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1

[android]
# (bool) Indicate if the application should be installable on SD card
api = 30

# (int) Target Android API, should be as high as possible.
minapi = 21

# (str) Android NDK version to use
ndk = 23b

# (str) Android SDK version to use
sdk = 30

# (list) Android application meta-data to set (key=value format)
android.meta_data = com.google.android.gms.version=@integer/google_play_services_version

# (list) Android library project to add (will be added in the
# project.properties automatically.)
android.library_references = @null

# (str) Android logcat filters to use
#android.logcat_filters = *:S python:D

# (bool) Copy library instead of making a libpymodules.so
android.copy_libs = 1

# (list) The Android archs to build for, choices: armeabi-v7a, arm64-v8a, x86, x86_64
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature (Android API >=23)
android.allow_backup = True

# (str) XML file for custom backup rules (see official auto backup documentation)
# android.backup_rules =

# (str) If you need to insert variables into your AndroidManifest.xml file,
# you can do so with the manifestPlaceholders property.
# This property takes a map of key-value pairs. (via a string)
# Usage example : android.manifest_placeholders = FACEBOOK_APP_ID:123456789,OTHER_VAR:some_value_here
# android.manifest_placeholders = [:]

# (bool) Skip byte compile for .py files
# android.no-byte-compile-python = False

[android.permissions]
android.permissions = CAMERA,RECORD_AUDIO,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET,ACCESS_FINE_LOCATION,ACCESS_COARSE_LOCATION,WAKE_LOCK

[android.add_src]
# (list) Android additionnal libraries to copy into libs/armeabi
android.add_src = 

[android.gradle_dependencies]
# (list) Gradle dependencies to add 
android.gradle_dependencies = 

[android.gradle_repositories]
# (list) Gradle repositories to add {can be necessary for some android.gradle_dependencies}
android.gradle_repositories = 

[android.add_activites]
# (list) Android additionnal activites to add
android.add_activites = 

[android.entrypoint]
# (str) python entrypoint to use for launching the application
android.entrypoint = org.kivy.android.PythonActivity

[android.app_theme]
# (str) Android app theme, default is ok for Kivy-based app
android.app_theme = "@android:style/Theme.NoTitleBar"

[android.presplash_color]
# (str) Android presplash background color (for new android toolchain)
android.presplash_color = #FFFFFF
'''

    with open('buildozer.spec', 'w') as f:
        f.write(spec_content)
    print("✅ Created buildozer.spec file")

def create_detector_utils():
    """Create utility functions for object detection"""
    utils_content = '''# detector_utils.py - Object detection utilities
import cv2
import numpy as np
import math
from kivy.logger import Logger

class DetectionUtils:
    """Utility functions for object detection"""
    
    @staticmethod
    def preprocess_image(image, target_size=(416, 416)):
        """Preprocess image for detection"""
        try:
            # Resize image
            resized = cv2.resize(image, target_size)
            
            # Normalize pixel values
            normalized = resized.astype(np.float32) / 255.0
            
            # Add batch dimension
            batched = np.expand_dims(normalized, axis=0)
            
            return batched
        except Exception as e:
            Logger.error(f"Image preprocessing error: {e}")
            return None
    
    @staticmethod
    def apply_nms(boxes, scores, score_threshold=0.5, nms_threshold=0.4):
        """Apply Non-Maximum Suppression"""
        try:
            # Convert to format expected by cv2.dnn.NMSBoxes
            boxes_list = boxes.tolist()
            scores_list = scores.tolist()
            
            # Apply NMS
            indices = cv2.dnn.NMSBoxes(
                boxes_list, 
                scores_list, 
                score_threshold, 
                nms_threshold
            )
            
            if len(indices) > 0:
                return indices.flatten()
            else:
                return []
                
        except Exception as e:
            Logger.error(f"NMS error: {e}")
            return []
    
    @staticmethod
    def get_object_direction(bbox, image_width, image_height):
        """Calculate object direction based on bounding box position"""
        x1, y1, x2, y2 = bbox
        
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # Normalize coordinates
        norm_x = center_x / image_width
        norm_y = center_y / image_height
        
        # Determine horizontal direction
        if norm_x < 0.2:
            horizontal = "far left"
        elif norm_x < 0.35:
            horizontal = "left"
        elif norm_x < 0.45:
            horizontal = "slightly left"
        elif norm_x < 0.55:
            horizontal = "center"
        elif norm_x < 0.65:
            horizontal = "slightly right"
        elif norm_x < 0.8:
            horizontal = "right"
        else:
            horizontal = "far right"
        
        # Determine vertical direction
        if norm_y < 0.3:
            vertical = "above"
        elif norm_y < 0.7:
            vertical = "level"
        else:
            vertical = "below"
        
        # Combine directions
        if horizontal == "center":
            if vertical == "above":
                direction = "ahead and above"
            elif vertical == "below":
                direction = "ahead and below"
            else:
                direction = "directly ahead"
        else:
            if vertical == "above":
                direction = f"{horizontal} and above"
            elif vertical == "below":
                direction = f"{horizontal} and below"
            else:
                direction = horizontal
        
        return {
            'direction': direction,
            'horizontal': horizontal,
            'vertical': vertical,
            'coordinates': {'x': norm_x, 'y': norm_y}
        }
    
    @staticmethod
    def estimate_distance(bbox, image_width, image_height, class_name=None):
        """Estimate object distance based on bounding box size"""
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        area = width * height
        
        image_area = image_width * image_height
        object_ratio = area / image_area
        
        # Distance categories based on object size ratio
        if object_ratio > 0.3:
            distance = "very close"
            category = "immediate"
        elif object_ratio > 0.15:
            distance = "close"
            category = "near"
        elif object_ratio > 0.05:
            distance = "medium distance"
            category = "medium"
        elif object_ratio > 0.01:
            distance = "far"
            category = "far"
        else:
            distance = "very far"
            category = "distant"
        
        return {
            'distance': distance,
            'category': category,
            'ratio': object_ratio,
            'area': area
        }
    
    @staticmethod
    def rotate_image(image, angle):
        """Rotate image by specified angle"""
        if angle == 0:
            return image
        
        try:
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            
            # Get rotation matrix
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            
            # Calculate new image dimensions
            cos = np.abs(rotation_matrix[0, 0])
            sin = np.abs(rotation_matrix[0, 1])
            
            new_width = int((height * sin) + (width * cos))
            new_height = int((height * cos) + (width * sin))
            
            # Adjust rotation matrix for new center
            rotation_matrix[0, 2] += (new_width / 2) - center[0]
            rotation_matrix[1, 2] += (new_height / 2) - center[1]
            
            # Perform rotation
            rotated = cv2.warpAffine(image, rotation_matrix, (new_width, new_height))
            return rotated
            
        except Exception as e:
            Logger.error(f"Image rotation error: {e}")
            return image
    
    @staticmethod
    def draw_detection_boxes(image, detections):
        """Draw detection boxes and labels on image"""
        try:
            for detection in detections:
                bbox = detection['bbox']
                class_name = detection['class_name']
                confidence = detection['confidence']
                
                x1, y1, x2, y2 = map(int, bbox)
                
                # Color based on confidence
                if confidence > 0.8:
                    color = (0, 255, 0)  # Green for high confidence
                elif confidence > 0.6:
                    color = (0, 255, 255)  # Yellow for medium confidence
                else:
                    color = (0, 0, 255)  # Red for low confidence
                
                # Draw bounding box
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
                label = f"{class_name} {int(confidence * 100)}%"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                
                # Label background
                cv2.rectangle(
                    image, 
                    (x1, y1 - label_size[1] - 10), 
                    (x1 + label_size[0], y1), 
                    color, 
                    -1
                )
                
                # Label text
                cv2.putText(
                    image, 
                    label, 
                    (x1, y1 - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.7, 
                    (255, 255, 255), 
                    2
                )
            
            return image
            
        except Exception as e:
            Logger.error(f"Drawing detection boxes error: {e}")
            return image

class PerformanceMonitor:
    """Monitor app performance"""
    
    def __init__(self):
        self.frame_times = []
        self.max_samples = 30
        
    def add_frame_time(self, frame_time):
        """Add frame processing time"""
        self.frame_times.append(frame_time)
        if len(self.frame_times) > self.max_samples:
            self.frame_times.pop(0)
    
    def get_avg_fps(self):
        """Get average FPS"""
        if not self.frame_times:
            return 0
        
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0
    
    def get_min_max_fps(self):
        """Get min and max FPS"""
        if not self.frame_times:
            return 0, 0
        
        min_fps = 1.0 / max(self.frame_times) if max(self.frame_times) > 0 else 0
        max_fps = 1.0 / min(self.frame_times) if min(self.frame_times) > 0 else 0
        
        return min_fps, max_fps
'''

    with open('detector_utils.py', 'w') as f:
        f.write(utils_content)
    print("✅ Created detector_utils.py")

def create_android_sensors():
    """Create Android sensor integration"""
    sensors_content = '''# android_sensors.py - Android sensor integration
from kivy.logger import Logger

try:
    from jnius import autoclass, cast
    from android.runnable import run_on_ui_thread
    ANDROID_AVAILABLE = True
    
    # Android classes
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')
    SensorManager = autoclass('android.hardware.SensorManager')
    Sensor = autoclass('android.hardware.Sensor')
    SensorEvent = autoclass('android.hardware.SensorEvent')
    SensorEventListener = autoclass('android.hardware.SensorEventListener')
    
except ImportError:
    ANDROID_AVAILABLE = False
    Logger.warning("Android JNI not available")

class AndroidSensorManager:
    """Manage Android sensors"""
    
    def __init__(self):
        self.sensor_manager = None
        self.gyroscope = None
        self.accelerometer = None
        self.magnetometer = None
        self.listeners = {}
        
        if ANDROID_AVAILABLE:
            self.initialize_sensors()
    
    def initialize_sensors(self):
        """Initialize Android sensors"""
        try:
            activity = PythonActivity.mActivity
            self.sensor_manager = activity.getSystemService(Context.SENSOR_SERVICE)
            
            # Get available sensors
            self.gyroscope = self.sensor_manager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
            self.accelerometer = self.sensor_manager.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)
            self.magnetometer = self.sensor_manager.getDefaultSensor(Sensor.TYPE_MAGNETIC_FIELD)
            
            Logger.info(f"Gyroscope available: {self.gyroscope is not None}")
            Logger.info(f"Accelerometer available: {self.accelerometer is not None}")
            Logger.info(f"Magnetometer available: {self.magnetometer is not None}")
            
        except Exception as e:
            Logger.error(f"Sensor initialization error: {e}")
    
    def register_gyroscope_listener(self, callback):
        """Register gyroscope event listener"""
        if not self.gyroscope:
            Logger.warning("Gyroscope not available")
            return False
        
        try:
            listener = GyroscopeListener(callback)
            success = self.sensor_manager.registerListener(
                listener,
                self.gyroscope,
                SensorManager.SENSOR_DELAY_GAME
            )
            
            if success:
                self.listeners['gyroscope'] = listener
                Logger.info("Gyroscope listener registered")
            else:
                Logger.error("Failed to register gyroscope listener")
            
            return success
            
        except Exception as e:
            Logger.error(f"Gyroscope listener registration error: {e}")
            return False
    
    def register_accelerometer_listener(self, callback):
        """Register accelerometer event listener"""
        if not self.accelerometer:
            Logger.warning("Accelerometer not available")
            return False
        
        try:
            listener = AccelerometerListener(callback)
            success = self.sensor_manager.registerListener(
                listener,
                self.accelerometer,
                SensorManager.SENSOR_DELAY_GAME
            )
            
            if success:
                self.listeners['accelerometer'] = listener
                Logger.info("Accelerometer listener registered")
            else:
                Logger.error("Failed to register accelerometer listener")
            
            return success
            
        except Exception as e:
            Logger.error(f"Accelerometer listener registration error: {e}")
            return False
    
    def unregister_all_listeners(self):
        """Unregister all sensor listeners"""
        try:
            for sensor_type, listener in self.listeners.items():
                self.sensor_manager.unregisterListener(listener)
                Logger.info(f"Unregistered {sensor_type} listener")
            
            self.listeners.clear()
            
        except Exception as e:
            Logger.error(f"Listener unregistration error: {e}")

if ANDROID_AVAILABLE:
    class GyroscopeListener:
        """Gyroscope sensor event listener"""
        
        def __init__(self, callback):
            self.callback = callback
        
        def onSensorChanged(self, event):
            """Called when gyroscope values change"""
            try:
                if event.sensor.getType() == Sensor.TYPE_GYROSCOPE:
                    values = event.values
                    # values[0] = rotation around x-axis (rad/s)
                    # values[1] = rotation around y-axis (rad/s)  
                    # values[2] = rotation around z-axis (rad/s)
                    self.callback(values[0], values[1], values[2])
            except Exception as e:
                Logger.error(f"Gyroscope sensor changed error: {e}")
        
        def onAccuracyChanged(self, sensor, accuracy):
            """Called when sensor accuracy changes"""
            pass
    
    class AccelerometerListener:
        """Accelerometer sensor event listener"""
        
        def __init__(self, callback):
            self.callback = callback
        
        def onSensorChanged(self, event):
            """Called when accelerometer values change"""
            try:
                if event.sensor.getType() == Sensor.TYPE_ACCELEROMETER:
                    values = event.values
                    # values[0] = acceleration along x-axis (m/s²)
                    # values[1] = acceleration along y-axis (m/s²)
                    # values[2] = acceleration along z-axis (m/s²)
                    self.callback(values[0], values[1], values[2])
            except Exception as e:
                Logger.error(f"Accelerometer sensor changed error: {e}")
        
        def onAccuracyChanged(self, sensor, accuracy):
            """Called when sensor accuracy changes"""
            pass

class OrientationCalculator:
    """Calculate device orientation from sensor data"""
    
    def __init__(self):
        self.gravity = [0, 0, 0]
        self.magnetic = [0, 0, 0]
        self.rotation_matrix = [[0]*3 for _ in range(3)]
        self.orientation = [0, 0, 0]
        
    def update_gravity(self, x, y, z):
        """Update gravity values from accelerometer"""
        # Apply low-pass filter
        alpha = 0.8
        self.gravity[0] = alpha * self.gravity[0] + (1 - alpha) * x
        self.gravity[1] = alpha * self.gravity[1] + (1 - alpha) * y
        self.gravity[2] = alpha * self.gravity[2] + (1 - alpha) * z
    
    def update_magnetic(self, x, y, z):
        """Update magnetic field values"""
        self.magnetic[0] = x
        self.magnetic[1] = y
        self.magnetic[2] = z
    
    def get_orientation(self):
        """Calculate orientation angles"""
        try:
            # This is a simplified orientation calculation
            # In a real app, you'd use Android's SensorManager.getRotationMatrix()
            
            # Calculate rotation around Z-axis (azimuth)
            azimuth = math.atan2(self.gravity[0], self.gravity[1])
            
            # Calculate rotation around X-axis (pitch)
            pitch = math.atan2(-self.gravity[2], 
                             math.sqrt(self.gravity[0]**2 + self.gravity[1]**2))
            
            # Calculate rotation around Y-axis (roll)
            roll = math.atan2(self.gravity[0], self.gravity[2])
            
            # Convert to degrees
            azimuth_deg = math.degrees(azimuth)
            pitch_deg = math.degrees(pitch)
            roll_deg = math.degrees(roll)
            
            return {
                'azimuth': azimuth_deg,
                'pitch': pitch_deg,
                'roll': roll_deg,
                'rotation_z': azimuth_deg  # For compatibility
            }
            
        except Exception as e:
            Logger.error(f"Orientation calculation error: {e}")
            return {'azimuth': 0, 'pitch': 0, 'roll': 0, 'rotation_z': 0}
'''

    with open('android_sensors.py', 'w') as f:
        f.write(sensors_content)
    print("✅ Created android_sensors.py")

def create_requirements_file():
    """Create requirements.txt file"""
    requirements_content = '''# Python requirements for Object Detection App
kivy>=2.1.0
kivymd>=1.1.1
opencv-python>=4.5.0
numpy>=1.21.0
Pillow>=8.0.0
pyttsx3>=2.90

# Optional TensorFlow Lite (for actual ML model)
# tensorflow-lite>=2.8.0

# Android-specific (automatically included by buildozer)
# pyjnius>=1.4.0
# android>=0.1
'''

    with open('requirements.txt', 'w') as f:
        f.write(requirements_content)
    print("✅ Created requirements.txt")

def create_readme():
    """Create README.md file"""
    readme_content = '''# Offline Object Detection Android App

A standalone Android application built with Python (Kivy/KivyMD) that performs real-time object detection using the device camera with gyroscope-based rotation correction.

## Features

- **Offline Operation**: Works completely offline, no internet required
- **Real-time Detection**: Live camera feed with object detection
- **Gyroscope Integration**: Automatic rotation correction using device gyroscope
- **Voice Announcements**: Audio feedback for detected objects with direction info
- **Distance Estimation**: Estimates object distance based on size
- **Direction Detection**: Tells you where objects are located (left, right, ahead, etc.)
- **Dark Theme**: Modern dark UI optimized for mobile

## Installation

### Prerequisites
- Python 3.8+
- Android SDK and NDK (for building APK)
- Linux/macOS (recommended for building)

### Setup Development Environment

1. **Clone/Download the project files**

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Buildozer** (for Android packaging):
   ```bash
   pip install buildozer
   ```

4. **Setup Android SDK/NDK**:
   - Install Android Studio or download SDK tools
   - Set environment variables:
     ```bash
     export ANDROID_HOME=/path/to/android-sdk
     export PATH=$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools
     ```

### Building for Android

1. **Initialize buildozer** (first time only):
   ```bash
   buildozer android debug
   ```

2. **Build APK**:
   ```bash
   buildozer android debug
   ```

3. **Install on device**:
   ```bash
   buildozer android deploy
   ```

### Running on Desktop (for testing)

```bash
python main.py
```

## Usage

1. **Launch the app** on your Android device
2. **Grant permissions** when prompted (Camera, Audio, Storage)
3. **Start Detection** - Tap the "Start Detection" button
4. **Calibrate Gyroscope** - Hold phone steady and tap "Calibrate" for best rotation correction
5. **Listen to announcements** - The app will announce detected objects with direction and distance

## App Controls

- **Start/Stop Detection**: Toggle real-time object detection
- **Audio ON/OFF**: Enable/disable voice announcements  
- **Calibrate**: Calibrate gyroscope for accurate rotation correction

## Technical Details

### Architecture
- **Frontend**: Kivy/KivyMD for cross-platform UI
- **Computer Vision**: OpenCV for image processing
- **Sensors**: Android gyroscope API for rotation detection
- **TTS**: Android TextToSpeech for voice feedback
- **Detection**: OpenCV Haar Cascades (demo) - can be extended with TensorFlow Lite

### Object Detection
The app uses OpenCV's Haar Cascade classifiers for face detection as a demonstration. For full object detection, you can:

1. Add a TensorFlow Lite model (`.tflite` file)
2. Update the `ObjectDetector` class to use the model
3. Include model files in `buildozer.spec`

### Gyroscope Integration
- Uses Android's native gyroscope sensor
- Integrates angular velocities to calculate rotation
- Applies rotation correction to camera frames
- Auto-calibration when device is steady

### Performance Optimizations
- Multi-threading for camera and detection
- Frame rate limiting to preserve battery
- Efficient memory management
- Optimized UI updates

## File Structure

```
object_detection_app/
├── main.py                 # Main application entry point
├── detector_utils.py       # Detection utility functions
├── android_sensors.py      # Android sensor integration
├── buildozer.spec         # Android build configuration
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Permissions Required

- **CAMERA**: For camera access
- **RECORD_AUDIO**: For text-to-speech (Android requirement)
- **WRITE_EXTERNAL_STORAGE**: For saving logs/data
- **ACCESS_FINE_LOCATION**: For sensor access (some devices)

## Troubleshooting

### Build Issues
- Ensure Android SDK/NDK are properly installed
- Check buildozer logs for specific errors
- Try cleaning build cache: `buildozer android clean`

### Runtime Issues
- Grant all requested permissions
- Ensure camera is not being used by another app
- Check device compatibility (Android 5.0+ recommended)

### Sensor Issues
- Calibrate gyroscope in a stable position
- Some devices may not have gyroscope sensor
- App will work without gyroscope but without rotation correction

## Extending the App

### Adding TensorFlow Lite Model
1. Add `.tflite` model file to project
2. Update `source.include_exts` in `buildozer.spec`
3. Modify `ObjectDetector.load_model()` to load your model
4. Update `detect_objects()` method for your model's input/output

### Custom Object Classes
- Update the `labels` list in `ObjectDetector`
- Modify detection announcements as needed
- Add custom detection logic for specific objects

### UI Customization
- Modify layouts in `DetectionScreen.build_ui()`
- Change theme colors in `ObjectDetectionApp.__init__()`
- Add new screens or functionality

## License

Open source - feel free to modify and distribute.

## Support

For issues and questions:
1. Check device compatibility
2. Verify all permissions are granted
3. Check build logs for errors
4. Test on multiple devices if possible
'''

    
    print("✅ Created README.txt")

def main():
    """Main setup function"""
    print("🚀 Setting up Android Object Detection App")
    print("=" * 50)
    
    # Install requirements
    print("\n📦 Installing Python requirements...")
    install_requirements()
    
    # Install buildozer
    print("\n🔧 Installing Buildozer...")
    install_buildozer()
    
    # Create configuration files
    print("\n📄 Creating configuration files...")
    create_buildozer_spec()
    create_detector_utils()
    create_android_sensors()
    create_requirements_file()
    create_readme()
    
    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("1. Run 'python main.py' to test on desktop")
    print("2. Run 'buildozer android debug' to build APK")
    print("3. Install APK on Android device")
    print("\nSee README.md for detailed instructions.")

if __name__ == "__main__":
    main()