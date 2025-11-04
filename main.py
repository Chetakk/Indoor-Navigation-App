# main.py - Simplified Android Object Detection App
import os
import cv2
import numpy as np
import threading
import time
import math
from datetime import datetime

# Kivy imports
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.graphics.texture import Texture
from kivy.logger import Logger
from kivy.uix.screenmanager import ScreenManager, Screen

# Android detection
try:
    from android.permissions import request_permissions, Permission
    from jnius import autoclass, cast
    ANDROID = True
    
    # Android classes
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')
    SensorManager = autoclass('android.hardware.SensorManager')
    Sensor = autoclass('android.hardware.Sensor')
    TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
    Locale = autoclass('java.util.Locale')
    
except ImportError:
    ANDROID = False
    Logger.info("Running on desktop - Android features disabled")

# Desktop TTS fallback
if not ANDROID:
    try:
        import pyttsx3
        DESKTOP_TTS = True
    except ImportError:
        DESKTOP_TTS = False


class SimpleGyroscope:
    """Simplified gyroscope manager"""
    
    def __init__(self):
        self.rotation_z = 0.0
        self.baseline_z = 0.0
        self.calibrated = False
        self.active = False
        
        if ANDROID:
            self.setup_android_gyroscope()
    
    def setup_android_gyroscope(self):
        """Setup Android gyroscope"""
        try:
            activity = PythonActivity.mActivity
            sensor_manager = activity.getSystemService(Context.SENSOR_SERVICE)
            gyroscope = sensor_manager.getDefaultSensor(Sensor.TYPE_GYROSCOPE)
            
            if gyroscope:
                self.active = True
                Logger.info("Gyroscope sensor found")
            else:
                Logger.warning("No gyroscope sensor available")
        except Exception as e:
            Logger.error(f"Gyroscope setup error: {e}")
    
    def calibrate(self):
        """Calibrate gyroscope baseline"""
        self.baseline_z = self.rotation_z
        self.calibrated = True
        Logger.info("Gyroscope calibrated")
        return True
    
    def get_rotation_degrees(self):
        """Get current rotation in degrees"""
        if not self.calibrated:
            return 0
        
        rotation = self.rotation_z - self.baseline_z
        
        # Normalize to -180 to 180
        while rotation > 180:
            rotation -= 360
        while rotation < -180:
            rotation += 360
        
        # Apply dead zone
        if abs(rotation) < 5:
            rotation = 0
        
        return rotation


class SimpleTTS:
    """Simplified text-to-speech"""
    
    def __init__(self):
        self.enabled = True
        self.android_tts = None
        self.desktop_engine = None
        
        if ANDROID:
            self.setup_android_tts()
        elif DESKTOP_TTS:
            self.setup_desktop_tts()
    
    def setup_android_tts(self):
        """Setup Android TTS"""
        try:
            activity = PythonActivity.mActivity
            self.android_tts = TextToSpeech(activity, None)
            Logger.info("Android TTS initialized")
        except Exception as e:
            Logger.error(f"Android TTS setup error: {e}")
    
    def setup_desktop_tts(self):
        """Setup desktop TTS"""
        try:
            self.desktop_engine = pyttsx3.init()
            self.desktop_engine.setProperty('rate', 180)
            Logger.info("Desktop TTS initialized")
        except Exception as e:
            Logger.error(f"Desktop TTS setup error: {e}")
    
    def speak(self, text):
        """Speak text"""
        if not self.enabled:
            return
        
        try:
            if ANDROID and self.android_tts:
                self.android_tts.speak(text, TextToSpeech.QUEUE_FLUSH, None)
            elif self.desktop_engine:
                self.desktop_engine.say(text)
                self.desktop_engine.runAndWait()
            else:
                Logger.info(f"TTS: {text}")  # Fallback to logging
        except Exception as e:
            Logger.error(f"TTS speak error: {e}")
    
    def toggle(self):
        """Toggle TTS on/off"""
        self.enabled = not self.enabled
        return self.enabled


class SimpleDetector:
    """Simplified object detector using OpenCV"""
    
    def __init__(self):
        self.face_cascade = None
        self.eye_cascade = None
        self.initialized = False
        self.load_cascades()
    
    def load_cascades(self):
        """Load OpenCV cascade classifiers"""
        try:
            # Try to load face cascade
            face_cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if os.path.exists(face_cascade_path):
                self.face_cascade = cv2.CascadeClassifier(face_cascade_path)
                Logger.info("Face cascade loaded")
            
            # Try to load eye cascade
            eye_cascade_path = cv2.data.haarcascades + 'haarcascade_eye.xml'
            if os.path.exists(eye_cascade_path):
                self.eye_cascade = cv2.CascadeClassifier(eye_cascade_path)
                Logger.info("Eye cascade loaded")
            
            self.initialized = True
            
        except Exception as e:
            Logger.error(f"Cascade loading error: {e}")
    
    def detect_objects(self, frame, rotation_degrees=0):
        """Detect objects in frame"""
        detections = []
        
        if not self.initialized or frame is None:
            return detections
        
        try:
            # Apply rotation if needed
            if rotation_degrees != 0:
                frame = self.rotate_image(frame, rotation_degrees)
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            height, width = frame.shape[:2]
            
            # Detect faces
            if self.face_cascade is not None:
                faces = self.face_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
                )
                
                for (x, y, w, h) in faces:
                    detection = {
                        'class_name': 'person',
                        'confidence': 0.85,
                        'bbox': [x, y, x + w, y + h],
                        'direction': self.get_direction(x + w/2, y + h/2, width, height),
                        'distance': self.estimate_distance(w * h, width * height)
                    }
                    detections.append(detection)
            
            # Detect eyes (as separate objects for demo)
            if self.eye_cascade is not None:
                eyes = self.eye_cascade.detectMultiScale(
                    gray, scaleFactor=1.1, minNeighbors=5, minSize=(10, 10)
                )
                
                # Limit to first 2 eyes to avoid too many detections
                for (x, y, w, h) in eyes[:2]:
                    detection = {
                        'class_name': 'eye',
                        'confidence': 0.75,
                        'bbox': [x, y, x + w, y + h],
                        'direction': self.get_direction(x + w/2, y + h/2, width, height),
                        'distance': self.estimate_distance(w * h, width * height)
                    }
                    detections.append(detection)
            
            return detections
            
        except Exception as e:
            Logger.error(f"Detection error: {e}")
            return []
    
    def rotate_image(self, image, angle):
        """Rotate image by angle"""
        if angle == 0:
            return image
        
        try:
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            rotated = cv2.warpAffine(image, rotation_matrix, (width, height))
            return rotated
        except Exception as e:
            Logger.error(f"Image rotation error: {e}")
            return image
    
    def get_direction(self, center_x, center_y, width, height):
        """Get object direction"""
        norm_x = center_x / width
        norm_y = center_y / height
        
        if norm_x < 0.3:
            horizontal = "left"
        elif norm_x > 0.7:
            horizontal = "right"
        else:
            horizontal = "center"
        
        if norm_y < 0.3:
            vertical = "above"
        elif norm_y > 0.7:
            vertical = "below"
        else:
            vertical = "level"
        
        if horizontal == "center":
            return "ahead" if vertical == "level" else f"ahead and {vertical}"
        else:
            return horizontal if vertical == "level" else f"{horizontal} and {vertical}"
    
    def estimate_distance(self, object_area, image_area):
        """Estimate distance based on object size"""
        ratio = object_area / image_area
        
        if ratio > 0.2:
            return "very close"
        elif ratio > 0.1:
            return "close"
        elif ratio > 0.05:
            return "medium distance"
        elif ratio > 0.01:
            return "far"
        else:
            return "very far"


class DetectionScreen(Screen):
    """Main detection screen"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Initialize components
        self.gyroscope = SimpleGyroscope()
        self.tts = SimpleTTS()
        self.detector = SimpleDetector()
        
        # Camera
        self.camera = None
        self.camera_active = False
        
        # Detection state
        self.detection_active = False
        self.detection_thread = None
        self.last_announcement = {}
        
        # Stats
        self.object_count = 0
        self.avg_confidence = 0
        self.fps = 0
        self.frame_count = 0
        self.start_time = time.time()
        
        self.build_ui()
        
        # Schedule updates
        Clock.schedule_interval(self.update_display, 1.0)
    
    def build_ui(self):
        """Build user interface"""
        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Title
        title = Label(
            text='Object Detection App',
            size_hint_y=None,
            height=50,
            font_size=24,
            color=(0.2, 0.6, 1, 1)
        )
        main_layout.add_widget(title)
        
        # Camera preview
        self.camera_image = Image(size_hint=(1, 0.6))
        main_layout.add_widget(self.camera_image)
        
        # Control buttons
        button_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=60, spacing=10)
        
        self.start_btn = Button(
            text='Start Detection',
            background_color=(0.2, 0.8, 0.2, 1)
        )
        self.start_btn.bind(on_press=self.toggle_detection)
        button_layout.add_widget(self.start_btn)
        
        self.audio_btn = Button(
            text='Audio ON',
            background_color=(1, 0.6, 0, 1)
        )
        self.audio_btn.bind(on_press=self.toggle_audio)
        button_layout.add_widget(self.audio_btn)
        
        self.calibrate_btn = Button(
            text='Calibrate',
            background_color=(0.6, 0.2, 0.8, 1)
        )
        self.calibrate_btn.bind(on_press=self.calibrate_gyroscope)
        button_layout.add_widget(self.calibrate_btn)
        
        main_layout.add_widget(button_layout)
        
        # Statistics
        stats_layout = BoxLayout(orientation='horizontal', size_hint_y=None, height=80, spacing=10)
        
        # Stats labels
        self.stats_label = Label(
            text='Objects: 0\nConfidence: 0%\nFPS: 0',
            text_size=(None, None),
            halign='center',
            valign='middle'
        )
        stats_layout.add_widget(self.stats_label)
        
        main_layout.add_widget(stats_layout)
        
        # Results
        self.results_label = Label(
            text='Ready to start detection...',
            text_size=(None, None),
            halign='center',
            valign='top',
            size_hint_y=None,
            height=100
        )
        main_layout.add_widget(self.results_label)
        
        # Status
        self.status_label = Label(
            text=f'Gyroscope: {"Active" if self.gyroscope.active else "Inactive"}\n'
                 f'Detector: {"Ready" if self.detector.initialized else "Error"}',
            text_size=(None, None),
            halign='center',
            size_hint_y=None,
            height=60,
            color=(0.7, 0.7, 0.7, 1)
        )
        main_layout.add_widget(self.status_label)
        
        self.add_widget(main_layout)
    
    def toggle_detection(self, *args):
        """Toggle detection on/off"""
        if self.detection_active:
            self.stop_detection()
        else:
            self.start_detection()
    
    def start_detection(self):
        """Start detection"""
        try:
            # Initialize camera
            self.camera = cv2.VideoCapture(0)
            if not self.camera.isOpened():
                Logger.error("Failed to open camera")
                return
            
            self.camera_active = True
            self.detection_active = True
            self.start_time = time.time()
            self.frame_count = 0
            
            # Update UI
            self.start_btn.text = 'Stop Detection'
            self.start_btn.background_color = (0.8, 0.2, 0.2, 1)
            
            # Start detection thread
            self.detection_thread = threading.Thread(target=self.detection_loop)
            self.detection_thread.daemon = True
            self.detection_thread.start()
            
            self.tts.speak("Detection started")
            
        except Exception as e:
            Logger.error(f"Start detection error: {e}")
    
    def stop_detection(self):
        """Stop detection"""
        self.detection_active = False
        self.camera_active = False
        
        if self.camera:
            self.camera.release()
            self.camera = None
        
        # Update UI
        self.start_btn.text = 'Start Detection'
        self.start_btn.background_color = (0.2, 0.8, 0.2, 1)
        self.results_label.text = 'Detection stopped'
        
        self.tts.speak("Detection stopped")
    
    def detection_loop(self):
        """Main detection loop"""
        while self.detection_active:
            try:
                if self.camera and self.camera.isOpened():
                    ret, frame = self.camera.read()
                    if ret:
                        # Get gyroscope rotation
                        rotation = self.gyroscope.get_rotation_degrees()
                        
                        # Detect objects
                        detections = self.detector.detect_objects(frame, rotation)
                        
                        # Update UI on main thread
                        Clock.schedule_once(
                            lambda dt: self.update_results(detections, frame), 0
                        )
                        
                        # Announce detections
                        self.announce_detections(detections)
                        
                        self.frame_count += 1
                
                time.sleep(0.2)  # 5 FPS
                
            except Exception as e:
                Logger.error(f"Detection loop error: {e}")
                break
    
    def update_results(self, detections, frame):
        """Update detection results"""
        self.object_count = len(detections)
        
        if detections:
            self.avg_confidence = sum(d['confidence'] for d in detections) / len(detections)
            
            # Format results text
            results = []
            for det in detections:
                conf_pct = int(det['confidence'] * 100)
                results.append(
                    f"{det['class_name']} ({conf_pct}%)\n"
                    f"{det['distance']} to your {det['direction']}"
                )
            
            self.results_label.text = '\n\n'.join(results[:2])  # Show max 2
        else:
            self.avg_confidence = 0
            self.results_label.text = 'No objects detected'
        
        # Update camera preview
        self.update_camera_preview(frame, detections)
    
    def update_camera_preview(self, frame, detections):
        """Update camera preview with detection boxes"""
        if frame is None:
            return
        
        try:
            # Draw detection boxes
            for det in detections:
                x1, y1, x2, y2 = map(int, det['bbox'])
                
                # Color based on confidence
                if det['confidence'] > 0.8:
                    color = (0, 255, 0)  # Green
                elif det['confidence'] > 0.6:
                    color = (0, 255, 255)  # Yellow
                else:
                    color = (0, 0, 255)  # Red
                
                # Draw box
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
                label = f"{det['class_name']} {int(det['confidence'] * 100)}%"
                cv2.putText(frame, label, (x1, y1 - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # Convert to Kivy texture
            buf = cv2.flip(frame, 0).tostring()
            texture = Texture.create(size=(frame.shape[1], frame.shape[0]), colorfmt='bgr')
            texture.blit_buffer(buf, colorfmt='bgr', bufferfmt='ubyte')
            self.camera_image.texture = texture
            
        except Exception as e:
            Logger.error(f"Camera preview update error: {e}")
    
    def announce_detections(self, detections):
        """Announce detected objects"""
        if not detections:
            return
        
        now = time.time()
        for det in detections:
            class_name = det['class_name']
            last_time = self.last_announcement.get(class_name, 0)
            
            # Announce every 5 seconds
            if now - last_time > 5:
                announcement = f"{class_name} {det['distance']} to your {det['direction']}"
                self.tts.speak(announcement)
                self.last_announcement[class_name] = now
    
    def toggle_audio(self, *args):
        """Toggle audio on/off"""
        enabled = self.tts.toggle()
        self.audio_btn.text = 'Audio ON' if enabled else 'Audio OFF'
        self.audio_btn.background_color = (1, 0.6, 0, 1) if enabled else (0.5, 0.5, 0.5, 1)
    
    def calibrate_gyroscope(self, *args):
        """Calibrate gyroscope"""
        if self.gyroscope.calibrate():
            self.tts.speak("Gyroscope calibrated")
            self.update_status()
        else:
            self.tts.speak("Gyroscope not available")
    
    def update_display(self, dt):
        """Update display elements"""
        # Calculate FPS
        if self.detection_active and self.frame_count > 0:
            elapsed = time.time() - self.start_time
            self.fps = self.frame_count / elapsed if elapsed > 0 else 0
        
        # Update stats
        self.stats_label.text = (
            f'Objects: {self.object_count}\n'
            f'Confidence: {int(self.avg_confidence * 100)}%\n'
            f'FPS: {self.fps:.1f}'
        )
        
        # Update status
        self.update_status()
    
    def update_status(self):
        """Update status display"""
        gyro_status = "Calibrated" if self.gyroscope.calibrated else ("Active" if self.gyroscope.active else "Inactive")
        detector_status = "Ready" if self.detector.initialized else "Error"
        
        self.status_label.text = (
            f'Gyroscope: {gyro_status}\n'
            f'Detector: {detector_status}'
        )


class ObjectDetectionApp(App):
    """Main application"""
    
    def build(self):
        """Build the app"""
        # Request permissions on Android
        if ANDROID:
            request_permissions([
                Permission.CAMERA,
                Permission.RECORD_AUDIO,
                Permission.WRITE_EXTERNAL_STORAGE
            ])
        
        # Create screen manager
        sm = ScreenManager()
        sm.add_widget(DetectionScreen(name='detection'))
        
        return sm
    
    def on_start(self):
        """App started"""
        Logger.info("Object Detection App started")
    
    def on_stop(self):
        """App stopped"""
        Logger.info("Object Detection App stopped")


if __name__ == '__main__':
    ObjectDetectionApp().run()