# android_sensors.py - Android sensor integration
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
