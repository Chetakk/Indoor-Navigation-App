/**
 * Motion-Based Depth Calibration Module
 * Uses accelerometer step detection and movement tracking to automatically
 * calibrate depth scale WITHOUT requiring object height assumptions.
 *
 * This solves the problem: not all people/tables/chairs are the same height!
 */

import { speak } from './audio.js';

// Motion tracking state
export const motionState = {
    // Accelerometer data
    acceleration: {
        x: 0,
        y: 0,
        z: 0,
        timestamp: 0
    },

    // Step detection
    steps: {
        count: 0,
        lastStepTime: 0,
        averageStepLength: 0.7, // meters (typical human step)
        distanceTraveled: 0, // meters
        stepBuffer: [], // For step detection algorithm
        stepThreshold: 1.5, // m/s^2 acceleration threshold for step
        cooldown: 300 // ms between steps
    },

    // Velocity estimation (double integration of acceleration)
    velocity: {
        x: 0,
        y: 0,
        z: 0,
        lastUpdate: 0
    },

    // Position tracking
    position: {
        x: 0,
        y: 0,
        z: 0
    },

    // Calibration state
    calibration: {
        scale: null, // Depth scale factor (meters per depth unit)
        confidence: 0, // 0-1, how confident we are in the scale
        samples: [], // Array of {depthChange, distanceMoved}
        minSamples: 3, // Minimum samples before we trust calibration
        ready: false
    },

    // Sensor status
    initialized: false,
    permissionGranted: false
};

/**
 * Initialize accelerometer for motion tracking
 * Works on Chrome, Firefox, Brave, Safari
 */
export async function initializeMotionTracking() {
    console.log('🏃 Initializing motion-based calibration...');

    try {
        // Try modern Accelerometer API first (Chrome)
        if ('Accelerometer' in window) {
            console.log('📱 Modern Accelerometer API detected');
            return await initializeModernAccelerometer();
        }

        // Fallback to DeviceMotionEvent (Firefox, Brave, Safari)
        if (typeof DeviceMotionEvent !== 'undefined') {
            console.log('📱 Using DeviceMotionEvent for accelerometer');
            return await initializeDeviceMotionAccelerometer();
        }

        console.warn('❌ No accelerometer APIs available');
        return false;

    } catch (error) {
        console.error('❌ Error initializing motion tracking:', error);
        return false;
    }
}

/**
 * Modern Accelerometer API (Chrome 67+)
 */
async function initializeModernAccelerometer() {
    try {
        const permission = await navigator.permissions.query({ name: 'accelerometer' });
        console.log('Accelerometer permission:', permission.state);

        if (permission.state === 'denied') {
            console.warn('❌ Accelerometer permission denied');
            return false;
        }

        // Use regular Accelerometer (includes gravity - we'll filter it ourselves)
        // LinearAccelerationSensor doesn't work on all devices
        const sensor = new Accelerometer({ frequency: 60 });

        sensor.addEventListener('reading', () => {
            const now = Date.now();
            const dt = motionState.acceleration.timestamp > 0
                ? (now - motionState.acceleration.timestamp) / 1000
                : 0;

            motionState.acceleration.x = sensor.x || 0;
            motionState.acceleration.y = sensor.y || 0;
            motionState.acceleration.z = sensor.z || 0;
            motionState.acceleration.timestamp = now;

            // DEBUG: Log acceleration values every 2 seconds
            if (now % 2000 < 100) {
                console.log('📊 Accelerometer reading:', {
                    x: motionState.acceleration.x.toFixed(3),
                    y: motionState.acceleration.y.toFixed(3),
                    z: motionState.acceleration.z.toFixed(3),
                    magnitude: Math.sqrt(
                        motionState.acceleration.x ** 2 +
                        motionState.acceleration.y ** 2 +
                        motionState.acceleration.z ** 2
                    ).toFixed(3)
                });
            }

            // Update velocity and position
            if (dt > 0 && dt < 0.1) {
                updateVelocityAndPosition(dt);
                detectStep();
            }

            if (!motionState.initialized) {
                motionState.initialized = true;
                console.log('✅ Modern accelerometer initialized');
            }
        });

        sensor.addEventListener('error', event => {
            console.error('❌ Accelerometer error:', event.error);
        });

        sensor.start();
        motionState.permissionGranted = true;
        console.log('✅ Motion tracking started');
        return true;

    } catch (error) {
        console.error('❌ Modern accelerometer failed:', error);
        return false;
    }
}

/**
 * DeviceMotionEvent fallback (Firefox, Brave, Safari)
 */
async function initializeDeviceMotionAccelerometer() {
    try {
        // Request permission for iOS 13+
        if (typeof DeviceMotionEvent.requestPermission === 'function') {
            console.log('📱 iOS detected - requesting motion permission...');
            const permission = await DeviceMotionEvent.requestPermission();

            if (permission !== 'granted') {
                console.warn('❌ iOS motion permission denied');
                return false;
            }
        }

        window.addEventListener('devicemotion', (event) => {
            if (event.accelerationIncludingGravity) {
                const now = Date.now();
                const dt = motionState.acceleration.timestamp > 0
                    ? (now - motionState.acceleration.timestamp) / 1000
                    : 0;

                // Use acceleration including gravity (we'll filter it)
                // This works better on Firefox/Brave
                const ax = event.accelerationIncludingGravity.x || 0;
                const ay = event.accelerationIncludingGravity.y || 0;
                const az = event.accelerationIncludingGravity.z || 0;

                // Remove gravity estimate (simplified - assumes phone held upright)
                motionState.acceleration.x = ax;
                motionState.acceleration.y = ay;
                motionState.acceleration.z = az - 9.81; // Remove gravity
                motionState.acceleration.timestamp = now;

                // Update velocity and position
                if (dt > 0 && dt < 0.1) {
                    updateVelocityAndPosition(dt);
                    detectStep();
                }

                if (!motionState.initialized) {
                    motionState.initialized = true;
                    console.log('✅ DeviceMotion accelerometer initialized');
                }
            }
        }, true);

        motionState.permissionGranted = true;
        console.log('✅ DeviceMotion tracking initialized');
        return true;

    } catch (error) {
        console.error('❌ DeviceMotion accelerometer failed:', error);
        return false;
    }
}

/**
 * Update velocity and position from acceleration (integration)
 */
function updateVelocityAndPosition(dt) {
    const acc = motionState.acceleration;
    const vel = motionState.velocity;
    const pos = motionState.position;

    // Integrate acceleration to get velocity (with drift correction)
    vel.x += acc.x * dt;
    vel.y += acc.y * dt;
    vel.z += acc.z * dt;

    // Apply damping to prevent drift (simple approach)
    const damping = 0.95;
    vel.x *= damping;
    vel.y *= damping;
    vel.z *= damping;

    // Integrate velocity to get position
    pos.x += vel.x * dt;
    pos.y += vel.y * dt;
    pos.z += vel.z * dt;

    vel.lastUpdate = Date.now();
}

/**
 * Detect steps using acceleration magnitude
 * Based on peak detection algorithm
 */
function detectStep() {
    const acc = motionState.acceleration;
    const steps = motionState.steps;
    const now = Date.now();

    // Calculate total acceleration magnitude
    // For regular Accelerometer (includes gravity), we look for CHANGES in magnitude
    // Gravity is ~9.8 m/s², so we subtract baseline
    const magnitude = Math.sqrt(acc.x * acc.x + acc.y * acc.y + acc.z * acc.z);

    // Remove gravity baseline (assuming phone held upright, gravity is mostly on one axis)
    const magnitudeWithoutGravity = Math.abs(magnitude - 9.8);

    // Add to buffer (use gravity-corrected value)
    steps.stepBuffer.push({ magnitude: magnitudeWithoutGravity, timestamp: now });

    // Keep buffer size manageable
    if (steps.stepBuffer.length > 30) {
        steps.stepBuffer.shift();
    }

    // Check cooldown
    if (now - steps.lastStepTime < steps.cooldown) {
        return;
    }

    // Find peaks in acceleration (indicates foot strike)
    if (steps.stepBuffer.length >= 3) {
        const idx = steps.stepBuffer.length - 2;
        const prev = steps.stepBuffer[idx - 1]?.magnitude || 0;
        const curr = steps.stepBuffer[idx].magnitude;
        const next = steps.stepBuffer[idx + 1]?.magnitude || 0;

        // DEBUG: Log peak detection every 2 seconds
        if (now % 2000 < 100) {
            console.log('🔍 Step detection:', {
                rawMag: magnitude.toFixed(3),
                correctedMag: curr.toFixed(3),
                threshold: steps.stepThreshold,
                isPeak: curr > prev && curr > next,
                aboveThreshold: curr > steps.stepThreshold,
                stepCount: steps.count
            });
        }

        // Peak detection: current value is higher than neighbors
        // Lower threshold to 0.2 m/s² for gentle walking detection
        if (curr > prev && curr > next && curr > 0.2) {
            // Step detected!
            steps.count++;
            steps.lastStepTime = now;
            steps.distanceTraveled += steps.averageStepLength;

            console.log(`🚶 Step detected! Count: ${steps.count}, Distance: ${steps.distanceTraveled.toFixed(2)}m, Magnitude: ${curr.toFixed(2)} m/s²`);
        }
    }
}

/**
 * Calculate depth scale from movement
 * Called when depth map changes and user has moved
 *
 * @param {Object} depthChange - {oldDepth, newDepth, trackedObject}
 * @returns {number|null} - Calibrated scale factor or null
 */
export function calibrateDepthFromMovement(depthChange) {
    if (!motionState.initialized || !depthChange) {
        return null;
    }

    const distanceMoved = motionState.steps.distanceTraveled;

    // Need meaningful movement (at least 1 meter)
    if (distanceMoved < 1.0) {
        console.log('⏳ Waiting for more movement... (need 1m+, have: ' + distanceMoved.toFixed(2) + 'm)');
        return null;
    }

    // Calculate depth change for tracked object
    const depthDelta = Math.abs(depthChange.newDepth - depthChange.oldDepth);

    // Depth must change meaningfully
    if (depthDelta < 10) {
        console.log('⏳ Depth change too small, need more data');
        return null;
    }

    // Calculate scale: distance_moved / depth_change
    const scale = distanceMoved / depthDelta;

    // Add sample to calibration
    motionState.calibration.samples.push({
        depthChange: depthDelta,
        distanceMoved: distanceMoved,
        scale: scale,
        timestamp: Date.now()
    });

    // Keep only recent samples (last 10)
    if (motionState.calibration.samples.length > 10) {
        motionState.calibration.samples.shift();
    }

    // Calculate average scale from samples
    if (motionState.calibration.samples.length >= motionState.calibration.minSamples) {
        const avgScale = motionState.calibration.samples.reduce((sum, s) => sum + s.scale, 0)
            / motionState.calibration.samples.length;

        // Calculate confidence from sample consistency
        const variance = motionState.calibration.samples.reduce((sum, s) =>
            sum + Math.pow(s.scale - avgScale, 2), 0) / motionState.calibration.samples.length;
        const stdDev = Math.sqrt(variance);
        const confidence = Math.max(0, Math.min(1, 1 - (stdDev / avgScale)));

        motionState.calibration.scale = avgScale;
        motionState.calibration.confidence = confidence;
        motionState.calibration.ready = confidence > 0.7;

        console.log(`📏 Depth calibration updated:
            - Scale: ${avgScale.toFixed(4)} m/depth_unit
            - Confidence: ${(confidence * 100).toFixed(1)}%
            - Samples: ${motionState.calibration.samples.length}
            - Ready: ${motionState.calibration.ready}`);

        if (motionState.calibration.ready) {
            speak('Depth calibration complete');
        }

        return avgScale;
    }

    console.log(`📊 Calibration sample ${motionState.calibration.samples.length}/${motionState.calibration.minSamples} collected`);
    return null;
}

/**
 * Get calibrated distance from depth value
 *
 * @param {number} depthValue - Raw depth from MiDaS
 * @returns {Object} - {distance, confidence, method}
 */
export function getCalibratedDistance(depthValue) {
    if (!motionState.calibration.ready || !motionState.calibration.scale) {
        return {
            distance: null,
            confidence: 0,
            method: 'uncalibrated'
        };
    }

    const distance = depthValue * motionState.calibration.scale;

    // Sanity check (0.1m to 50m range)
    if (distance < 0.1 || distance > 50) {
        return {
            distance: null,
            confidence: 0,
            method: 'out_of_range'
        };
    }

    return {
        distance: distance,
        confidence: motionState.calibration.confidence,
        method: 'motion_calibrated'
    };
}

/**
 * Reset motion tracking (useful for debugging)
 */
export function resetMotionTracking() {
    motionState.steps.count = 0;
    motionState.steps.distanceTraveled = 0;
    motionState.steps.stepBuffer = [];
    motionState.velocity = { x: 0, y: 0, z: 0, lastUpdate: 0 };
    motionState.position = { x: 0, y: 0, z: 0 };
    motionState.calibration.samples = [];
    motionState.calibration.scale = null;
    motionState.calibration.confidence = 0;
    motionState.calibration.ready = false;

    console.log('🔄 Motion tracking reset');
}

/**
 * Get motion tracking status for UI display
 */
export function getMotionStatus() {
    return {
        initialized: motionState.initialized,
        permissionGranted: motionState.permissionGranted,
        steps: motionState.steps.count,
        distanceTraveled: motionState.steps.distanceTraveled.toFixed(2) + 'm',
        calibrationReady: motionState.calibration.ready,
        calibrationConfidence: (motionState.calibration.confidence * 100).toFixed(1) + '%',
        scale: motionState.calibration.scale?.toFixed(4) || 'N/A'
    };
}

/**
 * Request motion permission (for iOS and modern browsers)
 */
export async function requestMotionPermission() {
    console.log('🔑 Requesting motion permission...');

    try {
        const success = await initializeMotionTracking();
        if (success) {
            setTimeout(() => {
                alert(`Motion tracking enabled!

This tracks your movement to automatically calibrate depth measurements.

Walk around naturally - the system will learn the depth scale from your steps.

No height assumptions needed!`);
                speak('Motion tracking enabled. Walk around to calibrate.');
            }, 500);
        } else {
            alert('Could not enable motion tracking. Depth estimation may be less accurate.');
        }
    } catch (error) {
        console.error('Error requesting motion permission:', error);
        alert('Error requesting motion permission: ' + error.message);
    }
}
