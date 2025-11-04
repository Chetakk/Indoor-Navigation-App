/**
 * Gyroscope Module
 * Handles TRUE gyroscope sensor data, initialization, calibration, and orientation functions
 */

import { speak } from './audio.js';
import TimingConfig from './timingConfig.js';

// TRUE GYROSCOPE: Pure gyroscope sensor data
export const gyroscopeData = {
    x: 0,        // Angular velocity around X axis (rad/s)
    y: 0,        // Angular velocity around Y axis (rad/s)
    z: 0,        // Angular velocity around Z axis (rad/s)
    last_update: 0,
    initialized: false,
    calibrated: false,
    // Integrated rotation angles from angular velocities
    rotation_x: 0,  // Cumulative rotation around X axis
    rotation_y: 0,  // Cumulative rotation around Y axis
    rotation_z: 0,  // Cumulative rotation around Z axis
    baseline_z: 0,  // Baseline Z rotation for calibration
    integration_time: 0
};

export let gyroscopePermissionGranted = false;

/**
 * REAL GYROSCOPE: Initialize actual gyroscope sensor
 * @returns {Promise<boolean>} Success status
 */
export async function initializeOrientation() {
    console.log('🎯 Initializing TRUE gyroscope sensor...');

    try {
        // Check if Gyroscope API is supported
        if ('Gyroscope' in window) {
            console.log('🔬 Modern Gyroscope API detected');
            return await initializeModernGyroscope();
        }

        // Fallback to DeviceMotionEvent for gyroscope data
        if (typeof DeviceMotionEvent !== 'undefined') {
            console.log('📱 Using DeviceMotionEvent for gyroscope data');
            return await initializeDeviceMotionGyroscope();
        }

        console.warn('❌ No gyroscope APIs available');
        return false;

    } catch (error) {
        console.error('❌ Error initializing gyroscope:', error);
        return false;
    }
}

/**
 * Modern Gyroscope API (Chrome 67+)
 * @returns {Promise<boolean>} Success status
 */
async function initializeModernGyroscope() {
    try {
        // Request permission for gyroscope
        const permission = await navigator.permissions.query({ name: 'gyroscope' });
        console.log('Modern gyroscope permission:', permission.state);

        if (permission.state === 'denied') {
            console.warn('❌ Modern gyroscope permission denied');
            return false;
        }

        // Create gyroscope sensor
        const sensor = new Gyroscope({ frequency: 60 }); // 60 Hz

        sensor.addEventListener('reading', () => {
            const now = Date.now();
            const dt = gyroscopeData.integration_time > 0 ? (now - gyroscopeData.integration_time) / 1000 : 0;

            gyroscopeData.x = sensor.angularVelocityX || 0;
            gyroscopeData.y = sensor.angularVelocityY || 0;
            gyroscopeData.z = sensor.angularVelocityZ || 0;
            gyroscopeData.last_update = now;

            // Integrate angular velocities to get rotation angles
            if (dt > 0 && dt < 0.1) { // Ignore large time gaps
                gyroscopeData.rotation_x += gyroscopeData.x * dt;
                gyroscopeData.rotation_y += gyroscopeData.y * dt;
                gyroscopeData.rotation_z += gyroscopeData.z * dt;
            }
            gyroscopeData.integration_time = now;

            // Auto-calibrate baseline
            if (!gyroscopeData.calibrated && Math.abs(gyroscopeData.z) < 0.1) {
                gyroscopeData.baseline_z = gyroscopeData.rotation_z;
                gyroscopeData.calibrated = true;
                console.log('🎯 Modern gyroscope calibrated - baseline Z:', gyroscopeData.baseline_z.toFixed(3));
            }

            if (!gyroscopeData.initialized) {
                gyroscopeData.initialized = true;
                console.log('✅ Modern gyroscope initialized');
            }
        });

        sensor.addEventListener('error', event => {
            console.error('❌ Modern gyroscope error:', event.error);
        });

        sensor.start();
        gyroscopePermissionGranted = true;
        console.log('✅ Modern gyroscope started successfully');
        return true;

    } catch (error) {
        console.error('❌ Modern gyroscope initialization failed:', error);
        return false;
    }
}

/**
 * DeviceMotionEvent gyroscope fallback
 * @returns {Promise<boolean>} Success status
 */
async function initializeDeviceMotionGyroscope() {
    try {
        // Request permission for iOS 13+
        if (typeof DeviceMotionEvent.requestPermission === 'function') {
            console.log('📱 iOS detected - requesting motion permission...');

            const permission = await DeviceMotionEvent.requestPermission();
            console.log('DeviceMotion permission result:', permission);

            if (permission !== 'granted') {
                console.warn('❌ iOS motion permission denied');
                return false;
            }
        }

        // Set up device motion listener for gyroscope data
        window.addEventListener('devicemotion', (event) => {
            if (event.rotationRate) {
                const now = Date.now();
                const dt = gyroscopeData.integration_time > 0 ? (now - gyroscopeData.integration_time) / 1000 : 0;

                // Get angular velocities in rad/s
                gyroscopeData.x = (event.rotationRate.beta || 0) * (Math.PI / 180); // Convert deg/s to rad/s
                gyroscopeData.y = (event.rotationRate.gamma || 0) * (Math.PI / 180);
                gyroscopeData.z = (event.rotationRate.alpha || 0) * (Math.PI / 180);
                gyroscopeData.last_update = now;

                // Integrate angular velocities to get rotation angles
                if (dt > 0 && dt < 0.1) { // Ignore large time gaps
                    gyroscopeData.rotation_x += gyroscopeData.x * dt;
                    gyroscopeData.rotation_y += gyroscopeData.y * dt;
                    gyroscopeData.rotation_z += gyroscopeData.z * dt;
                }
                gyroscopeData.integration_time = now;

                // Auto-calibrate baseline when device is still
                if (!gyroscopeData.calibrated &&
                    Math.abs(gyroscopeData.x) < 0.1 &&
                    Math.abs(gyroscopeData.y) < 0.1 &&
                    Math.abs(gyroscopeData.z) < 0.1) {
                    gyroscopeData.baseline_z = gyroscopeData.rotation_z;
                    gyroscopeData.calibrated = true;
                    console.log('🎯 DeviceMotion gyroscope calibrated - baseline Z:', gyroscopeData.baseline_z.toFixed(3));
                }

                if (!gyroscopeData.initialized) {
                    gyroscopeData.initialized = true;
                    console.log('✅ DeviceMotion gyroscope initialized');
                }

                // Debug log every 5 seconds
                if (Date.now() % 5000 < 100) {
                    console.log('🎯 True gyroscope data:', {
                        'x (rad/s)': gyroscopeData.x.toFixed(3),
                        'y (rad/s)': gyroscopeData.y.toFixed(3),
                        'z (rad/s)': gyroscopeData.z.toFixed(3),
                        'rotation_z (rad)': gyroscopeData.rotation_z.toFixed(3),
                        calibrated: gyroscopeData.calibrated
                    });
                }
            }
        }, true);

        gyroscopePermissionGranted = true;
        gyroscopeData.integration_time = Date.now();
        console.log('✅ DeviceMotion gyroscope tracking initialized');
        return true;

    } catch (error) {
        console.error('❌ DeviceMotion gyroscope initialization failed:', error);
        return false;
    }
}

/**
 * TRUE GYROSCOPE: Calculate rotation from pure gyroscope angular velocities
 * @returns {number} Rotation in degrees
 */
export function calculateGyroscopeRotation() {
    if (!gyroscopeData.initialized || !gyroscopeData.calibrated) {
        return 0;
    }

    // Use integrated Z-axis rotation (yaw) for screen rotation
    const currentRotationZ = gyroscopeData.rotation_z;
    const baselineRotationZ = gyroscopeData.baseline_z;

    // Calculate rotation relative to baseline in radians
    let rotationRad = currentRotationZ - baselineRotationZ;

    // Convert to degrees
    let rotationDeg = rotationRad * (180 / Math.PI);

    // Normalize to -180 to 180 range
    while (rotationDeg > 180) rotationDeg -= 360;
    while (rotationDeg < -180) rotationDeg += 360;

    // Apply thresholds to avoid micro-corrections from sensor noise
    if (Math.abs(rotationDeg) < 5) {
        rotationDeg = 0;  // Dead zone for small rotations
    }

    // Snap to common angles for stability (with tighter tolerances for gyroscope)
    if (Math.abs(rotationDeg - 90) < 8) rotationDeg = 90;        // Portrait right
    else if (Math.abs(rotationDeg + 90) < 8) rotationDeg = -90;  // Portrait left
    else if (Math.abs(Math.abs(rotationDeg) - 180) < 8) {        // Upside down
        rotationDeg = rotationDeg > 0 ? 180 : -180;
    }

    console.log('🎯 True gyroscope rotation calculation:', {
        currentRotationZ: currentRotationZ.toFixed(4),
        baselineRotationZ: baselineRotationZ.toFixed(4),
        rotationRad: rotationRad.toFixed(4),
        rotationDeg: rotationDeg.toFixed(1)
    });

    return rotationDeg;
}

/**
 * TRUE GYROSCOPE: Get pure gyroscope sensor data
 * @returns {Object|null} Orientation data or null if not initialized
 */
export function getCurrentOrientation() {
    const now = Date.now();

    console.log('📊 Getting TRUE gyroscope data:', {
        permissionGranted: gyroscopePermissionGranted,
        initialized: gyroscopeData.initialized,
        calibrated: gyroscopeData.calibrated,
        dataAge: gyroscopeData.last_update ? (now - gyroscopeData.last_update) : 'never',
        angularVelocityZ: gyroscopeData.z?.toFixed(4) + ' rad/s',
        integratedRotationZ: gyroscopeData.rotation_z?.toFixed(4) + ' rad'
    });

    // Return null if not properly initialized
    if (!gyroscopePermissionGranted || !gyroscopeData.initialized) {
        console.warn('⚠️ True gyroscope not initialized');
        return null;
    }

    // Calculate rotation from integrated gyroscope data
    const calculatedRotation = calculateGyroscopeRotation();

    // Return true gyroscope-based orientation data
    return {
        // Pure gyroscope rotation calculation
        gyroscope_rotation: calculatedRotation,
        // Raw gyroscope angular velocities (rad/s)
        angular_velocity_x: gyroscopeData.x,
        angular_velocity_y: gyroscopeData.y,
        angular_velocity_z: gyroscopeData.z,
        // Integrated rotation angles (rad)
        integrated_rotation_x: gyroscopeData.rotation_x,
        integrated_rotation_y: gyroscopeData.rotation_y,
        integrated_rotation_z: gyroscopeData.rotation_z,
        // Baseline for calibration
        baseline_rotation_z: gyroscopeData.baseline_z,
        timestamp: gyroscopeData.last_update,
        data_age_ms: now - gyroscopeData.last_update,
        calibrated: gyroscopeData.calibrated,
        source: 'true_gyroscope'
    };
}

/**
 * TRUE GYROSCOPE: Manual calibration function
 */
export function calibrateGyroscope() {
    console.log('🎯 Manual TRUE gyroscope calibration...');

    if (!gyroscopePermissionGranted || !gyroscopeData.initialized) {
        alert('❌ True gyroscope not available. Please enable gyroscope tracking first.');
        return;
    }

    // Set current integrated rotation as baseline
    gyroscopeData.baseline_z = gyroscopeData.rotation_z;
    gyroscopeData.calibrated = true;

    const message = `✅ TRUE Gyroscope Calibrated!
Current orientation set as baseline:
• Z Rotation: ${gyroscopeData.baseline_z.toFixed(4)} rad
• Angular Velocity Z: ${gyroscopeData.z.toFixed(4)} rad/s

Hold your phone in this position during detection for best results.`;

    console.log('🎯 Manual TRUE gyroscope calibration completed:', {
        baseline_rotation_z: gyroscopeData.baseline_z.toFixed(4),
        current_angular_velocity_z: gyroscopeData.z.toFixed(4)
    });

    alert(message);
    speak('True gyroscope calibrated successfully');
}

/**
 * TRUE GYROSCOPE: Request gyroscope permission with calibration
 * @returns {Promise<void>}
 */
export async function requestOrientationPermission() {
    console.log('🔑 Manual TRUE gyroscope permission request...');

    try {
        const success = await initializeOrientation();
        if (success) {
            // Wait a moment for initial readings
            setTimeout(() => {
                alert('TRUE Gyroscope tracking enabled!\n\nThis uses actual gyroscope sensor data (angular velocities) for precise rotation detection.\n\nPlease hold your phone steady and tap "Calibrate" to set the baseline position.');

                // Test the gyroscope data immediately
                const testData = getCurrentOrientation();
                console.log('Test TRUE gyroscope data after permission:', testData);
                if (testData) {
                    speak('True gyroscope tracking is now active. Please calibrate your baseline position for accurate rotation detection.');
                }
            }, TimingConfig.mobile.gyroscopePermissionAlertDelay);
        } else {
            alert('❌ Could not enable TRUE gyroscope tracking. Detection will work but without rotation correction.');
        }
    } catch (error) {
        console.error('Error requesting gyroscope permission:', error);
        alert('❌ Error requesting TRUE gyroscope permission: ' + error.message);
    }
}
