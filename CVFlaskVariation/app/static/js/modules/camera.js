/**
 * Camera Module
 * Handles camera initialization, video stream, and real-time detection loop
 */

import { initializeOrientation, getCurrentOrientation, gyroscopeData, gyroscopePermissionGranted } from './gyroscope.js';
import { audioState, clearAudioQueue } from './audio.js';
import { announceDetections, clearTrackingData as clearDetectionTracking, setCanvas, setTrackingEnabled as setDetectionTrackingEnabled, analyzeSceneChange } from './detection.js';
import { clearTrackingData as clearTrackingState, setTrackingEnabled } from './tracking.js';
import { getPathfindingState, calculateNavigationPath } from './pathfinding.js';
import { drawDetections, updateRealtimeDetections, updateStats, updateRealtimeStats, updateFPS, setCanvasAndVideo, setDetectionActive, incrementFrameCount } from './ui.js';
import TimingConfig from './timingConfig.js';
import { motionState, initializeMotionTracking } from './motionCalibration.js';

// Camera state
export let stream = null;
export let detectionActive = false;
let detectionInterval = null;
let currentAbortController = null;
let isProcessingRequest = false;
let canvas = null;
let ctx = null;
let video = null;
let trackingEnabled = true;
let requestIdCounter = 0;
let latestRequestId = 0;

// Camera registry state
let cameraId = null;
let heartbeatInterval = null;
let frameCount = 0;
let detectionCount = 0;
let lastFpsUpdate = Date.now();
let currentFps = 0;
let dashboardStreamingEnabled = true;
let frameUploadInterval = null;
let lastFrameUploadTime = 0;
let frameUploadStallWarningShown = false;

/**
 * Register this camera with the server
 */
async function registerCamera() {
    try {
        // Check if we already have a camera ID
        const storedId = localStorage.getItem('cameraId');

        // Get device info
        const deviceName = navigator.userAgent.includes('Mobile') ? 'Mobile Device' : 'Desktop Device';
        const browserInfo = navigator.userAgent.match(/(Chrome|Firefox|Safari|Edge)\/[\d.]+/)?.[0] || 'Unknown Browser';

        const response = await fetch('/admin/cameras/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                camera_id: storedId,
                camera_name: `${deviceName} - ${browserInfo}`
            })
        });

        if (!response.ok) {
            throw new Error(`Registration failed: ${response.status}`);
        }

        const data = await response.json();

        if (data.success) {
            cameraId = data.camera_id;
            localStorage.setItem('cameraId', cameraId);
            console.log(`📷 Camera registered with ID: ${cameraId}`);

            // Start heartbeat
            startHeartbeat();
        } else {
            console.error('Camera registration failed:', data.error);
        }
    } catch (error) {
        console.error('Error registering camera:', error);
    }
}

/**
 * Unregister camera from server
 */
async function unregisterCamera() {
    if (!cameraId) return;

    try {
        await fetch(`/admin/cameras/unregister/${cameraId}`, {
            method: 'POST'
        });
        console.log(`📷 Camera unregistered: ${cameraId}`);
    } catch (error) {
        console.error('Error unregistering camera:', error);
    }
}

/**
 * Send heartbeat to server
 */
async function sendHeartbeat() {
    if (!cameraId) return;

    try {
        // Calculate FPS
        const now = Date.now();
        const timeDiff = (now - lastFpsUpdate) / 1000;
        if (timeDiff >= 1) {
            currentFps = frameCount / timeDiff;
            frameCount = 0;
            lastFpsUpdate = now;
        }

        // Get battery info if available
        let batteryLevel = null;
        let isCharging = null;
        if (navigator.getBattery) {
            const battery = await navigator.getBattery();
            batteryLevel = Math.round(battery.level * 100);
            isCharging = battery.charging;
        }

        // Get geolocation if available (requires user permission)
        let latitude = null;
        let longitude = null;
        if (navigator.geolocation) {
            // Don't block on geolocation - just send null if not available
            // In production, you might want to request this separately
        }

        const heartbeatData = {
            detection_active: detectionActive,
            audio_enabled: audioState.enabled,
            pathfinding_enabled: getPathfindingState().enabled,
            dashboard_streaming_enabled: dashboardStreamingEnabled,
            total_detections: detectionCount,
            total_frames: frameCount,
            fps: currentFps,
            battery_level: batteryLevel,
            is_charging: isCharging,
            latitude: latitude,
            longitude: longitude
        };

        await fetch(`/admin/cameras/heartbeat/${cameraId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(heartbeatData)
        });

        // Debug log every 10th heartbeat
        if (Math.random() < 0.1) {
            console.log('💓 Heartbeat sent:', heartbeatData);
        }
    } catch (error) {
        console.error('Error sending heartbeat:', error);
    }
}

/**
 * Start heartbeat interval
 */
function startHeartbeat() {
    // Stop existing heartbeat if any
    stopHeartbeat();

    // Send heartbeat every 5 seconds
    heartbeatInterval = setInterval(sendHeartbeat, 5000);

    // Send initial heartbeat immediately
    sendHeartbeat();

    console.log('💓 Heartbeat started (5s interval)');
}

/**
 * Stop heartbeat interval
 */
function stopHeartbeat() {
    if (heartbeatInterval) {
        clearInterval(heartbeatInterval);
        heartbeatInterval = null;
        console.log('💓 Heartbeat stopped');
    }
}

/**
 * Start camera and detection
 */
export async function startCamera() {
    const videoElement = document.getElementById('videoElement');
    const detectionCanvas = document.getElementById('detectionCanvas');
    const startBtn = document.getElementById('startBtn');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const startBtnText = document.getElementById('startBtnText');
    const cameraContainer = document.getElementById('cameraContainer');
    const realtimeIndicator = document.getElementById('realtimeIndicator');

    try {
        console.log(stream);
        if (stream) {
            // Stop camera and detection
            stopDetection();
            stopHeartbeat();
            stopFrameUpload();

            stream.getTracks().forEach(track => track.stop());
            stream = null;
            videoElement.srcObject = null;
            videoElement.style.display = 'none';
            detectionCanvas.style.display = 'none';

            startBtnText.innerHTML = 'Start Camera & Detection';
            statusDot.classList.remove('active', 'detecting');
            statusText.textContent = 'Camera Disconnected';

            // Hide real-time indicator
            realtimeIndicator.classList.remove('active');
            cameraContainer.classList.remove('recording');

            return;
        }

        startBtnText.innerHTML = '<div class="loading"></div>Starting Camera...';

        // Initialize TRUE gyroscope tracking if not done yet
        if (!gyroscopePermissionGranted) {
            console.log('Initializing TRUE gyroscope tracking...');
            await initializeOrientation();
        }

        // Initialize motion tracking for depth calibration (NO HEIGHT ASSUMPTIONS!)
        if (!motionState.initialized) {
            console.log('🚶 Initializing motion tracking for depth calibration...');
            await initializeMotionTracking();
        }

        // Request camera access
        const constraints = {
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 },
                frameRate: { ideal: 30 },
                facingMode: 'environment' // Use back camera on mobile
            }
        };

        stream = await navigator.mediaDevices.getUserMedia(constraints);
        videoElement.srcObject = stream;

        // Wait for video to be ready
        await new Promise((resolve) => {
            videoElement.onloadedmetadata = () => {
                videoElement.play();
                resolve();
            };
        });

        // Setup canvas for detection overlay
        video = videoElement;
        canvas = detectionCanvas;
        ctx = canvas.getContext('2d');

        // Set canvas size to match video
        canvas.width = videoElement.videoWidth || 640;
        canvas.height = videoElement.videoHeight || 480;

        // Set canvas and video in other modules
        setCanvasAndVideo(canvas, ctx, video);
        setCanvas(canvas);

        // Show video and canvas
        videoElement.style.display = 'block';
        detectionCanvas.style.display = 'block';

        // Update status to detecting
        statusDot.classList.add('detecting');
        const gyroStatus = gyroscopePermissionGranted ?
            (gyroscopeData.calibrated ? 'with TRUE Gyroscope Correction' : 'with TRUE Gyroscope (needs calibration)') :
            '';
        statusText.textContent = `Camera Connected - Real-time Detection Active ${gyroStatus}`;

        // Show real-time indicator
        realtimeIndicator.classList.add('active');
        cameraContainer.classList.add('recording');

        // Start detection automatically
        detectionActive = true;
        setDetectionActive(true);
        startRealtimeAnalysis();

        // Update button text
        startBtnText.innerHTML = 'Stop Camera & Detection';

        // Register camera with server for overseer monitoring
        await registerCamera();

        // Start frame upload if streaming enabled
        const storedStreamingPref = localStorage.getItem('dashboardStreamingEnabled');
        if (storedStreamingPref !== 'false') {
            startFrameUpload();
        }

    } catch (err) {
        console.error('Error accessing camera:', err);
        alert('Error accessing camera. Please ensure camera permissions are granted and camera is not in use by another application.');
        startBtnText.innerHTML = 'Start Camera & Detection';
    }
}

/**
 * Stop detection and clear data
 */
export function stopDetection() {
    const videoElement = document.getElementById('videoElement');
    const detectionCanvas = document.getElementById('detectionCanvas');
    const cameraContainer = document.getElementById('cameraContainer');
    const statusDot = document.getElementById('statusDot');
    const statusText = document.getElementById('statusText');
    const realtimeIndicator = document.getElementById('realtimeIndicator');

    console.log('🛑 Stopping detection and cancelling pending requests...');

    detectionActive = false;
    setDetectionActive(false);
    isProcessingRequest = false;

    // Cancel any pending fetch requests
    if (currentAbortController) {
        currentAbortController.abort();
        currentAbortController = null;
        console.log('✅ Aborted pending request');
    }

    // Clear canvas
    if (canvas && ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }

    // Clear tracking data from all modules
    clearTrackingState();
    clearDetectionTracking();
    audioState.queue = [];
    audioState.isPlaying = false;
    console.log('✅ Cleared tracking data and audio queue');

    // Update status
    statusDot.classList.remove('detecting');
    statusText.textContent = 'Detection Stopped';

    // Hide real-time indicator
    realtimeIndicator.classList.remove('active');
    cameraContainer.classList.remove('recording');

    if (detectionInterval) {
        clearInterval(detectionInterval);
        detectionInterval = null;
    }

    // Stop any ongoing speech
    if (audioState.speechSynth) {
        audioState.speechSynth.cancel();
    }
}

/**
 * Start real-time analysis with gyroscope-based rotation
 */
export function startRealtimeAnalysis() {
    // Clear any existing interval
    if (detectionInterval) {
        clearInterval(detectionInterval);
    }

    console.log('🚀 Starting real-time analysis with TRUE gyroscope-based rotation...');
    console.log('🔍 Detection interval being set with loop interval:', TimingConfig.detection.loopInterval, 'ms');

    // REAL-TIME for blind navigation: immediate hazard detection
    detectionInterval = setInterval(async () => {
        console.log('⏰ Detection loop tick - entering interval callback');
        if (!detectionActive || !video || !canvas || !ctx) {
            console.log('❌ Detection inactive or missing elements:', {
                detectionActive,
                video: !!video,
                canvas: !!canvas,
                ctx: !!ctx
            });
            return;
        }

        // Skip if already processing a request
        if (isProcessingRequest) {
            console.log('⏭️ Skipping frame - previous request still processing');
            return;
        }

        // CRITICAL: Declare timeoutId in outer scope so it's accessible in catch/finally blocks
        let timeoutId = null;

        try {
            isProcessingRequest = true;

            // Assign a unique request ID to track this request
            requestIdCounter++;
            const thisRequestId = requestIdCounter;
            latestRequestId = thisRequestId;
            console.log(`🆔 Starting request #${thisRequestId}`);

            // Create new abort controller for this request
            currentAbortController = new AbortController();
            // Capture frame from video
            const tempCanvas = document.createElement('canvas');
            const tempCtx = tempCanvas.getContext('2d');
            tempCanvas.width = video.videoWidth || 640;
            tempCanvas.height = video.videoHeight || 480;

            // Draw current video frame
            tempCtx.drawImage(video, 0, 0);
            const imageData = tempCanvas.toDataURL('image/jpeg', 0.8);

            // Get current TRUE gyroscope-based orientation data
            const currentOrientation = getCurrentOrientation();

            console.log('📤 Sending detection request:', {
                imageSize: `${tempCanvas.width}x${tempCanvas.height}`,
                trueGyroscopeIncluded: !!currentOrientation,
                gyroscopeData: currentOrientation ? {
                    rotation: currentOrientation.gyroscope_rotation,
                    calibrated: currentOrientation.calibrated,
                    source: currentOrientation.source,
                    angularVelocityZ: currentOrientation.angular_velocity_z?.toFixed(4)
                } : null
            });

            // Prepare request payload
            const requestData = {
                image: imageData,
                tracking_enabled: trackingEnabled
            };

            // Add TRUE gyroscope-based orientation data if available
            if (currentOrientation) {
                requestData.orientation = currentOrientation;
                console.log('✅ Including TRUE gyroscope data in request:', {
                    rotation: currentOrientation.gyroscope_rotation,
                    calibrated: currentOrientation.calibrated,
                    angular_velocity_z: currentOrientation.angular_velocity_z?.toFixed(4),
                    integrated_rotation_z: currentOrientation.integrated_rotation_z?.toFixed(4)
                });
            } else {
                console.warn('⚠️ No TRUE gyroscope data available - sending without rotation correction');
            }

            // Add motion calibration data if available (NO HEIGHT ASSUMPTIONS!)
            // Always include motion data if we have steps, even if not fully calibrated
            if (motionState.initialized && motionState.steps.count > 0) {
                // Use preliminary scale if calibration not ready yet
                const scale = motionState.calibration.scale || (motionState.steps.distanceTraveled / 500); // rough estimate
                const confidence = motionState.calibration.confidence || 0.3; // low confidence until calibrated

                requestData.motion_calibration = {
                    scale: scale,
                    confidence: confidence,
                    steps: motionState.steps.count,
                    distance: motionState.steps.distanceTraveled
                };

                console.log('🚶 Including motion calibration data:', {
                    scale: scale.toFixed(4),
                    confidence: (confidence * 100).toFixed(1) + '%',
                    steps: motionState.steps.count,
                    distance: motionState.steps.distanceTraveled.toFixed(2) + 'm',
                    calibrated: motionState.calibration.ready
                });
            } else {
                console.log('⏳ Motion tracking status:', {
                    initialized: motionState.initialized,
                    steps: motionState.steps.count,
                    distance: motionState.steps.distanceTraveled.toFixed(2) + 'm',
                    calibrated: motionState.calibration.ready
                });
            }

            // Send to server for detection with abort signal and timeout
            timeoutId = setTimeout(() => {
                console.error(`⏱️ Request timeout after ${TimingConfig.detection.requestTimeout}ms`);
                if (currentAbortController) {
                    currentAbortController.abort();
                }
            }, TimingConfig.detection.requestTimeout);

            console.log('📡 Sending request to /detect_image...');
            const response = await fetch('/detect_image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestData),
                signal: currentAbortController.signal
            });

            clearTimeout(timeoutId); // Clear timeout if request completes
            timeoutId = null;
            console.log(`📡 Response received for request #${thisRequestId}, status:`, response.status);

            // Check if this is a stale response
            if (thisRequestId !== latestRequestId) {
                console.warn(`⚠️ Ignoring stale response from request #${thisRequestId} (latest: #${latestRequestId})`);
                isProcessingRequest = false;
                return;
            }

            console.log('📡 Response headers:', [...response.headers.entries()]);
            console.log('📡 Response OK:', response.ok);

            if (!response.ok) {
                const errorText = await response.text();
                console.error('❌ HTTP error response body:', errorText);
                throw new Error(`HTTP error! status: ${response.status}, body: ${errorText.substring(0, 200)}`);
            }

            console.log('📡 Parsing JSON response...');
            const data = await response.json();
            console.log('📦 JSON parsed successfully:', data);

            // Check if detection is still active before processing response
            if (!detectionActive) {
                console.log('🛑 Detection stopped - ignoring response');
                isProcessingRequest = false;
                return;
            }

            // Double-check this is still the latest request after async operations
            if (thisRequestId !== latestRequestId) {
                console.warn(`⚠️ Ignoring stale response from request #${thisRequestId} after JSON parse (latest: #${latestRequestId})`);
                isProcessingRequest = false;
                return;
            }

            if (data.success) {
                // Increment frame counter for camera registry
                frameCount++;

                // Increment detection counter if we have detections
                if (data.detections && data.detections.length > 0) {
                    detectionCount += data.detections.length;
                }

                console.log('✅ Detection successful:', {
                    detections: data.detections.length,
                    rotationApplied: data.rotation_applied,
                    orientationSource: data.orientation_source,
                    trueGyroscopeAvailable: data.gyroscope_available,
                    collisionWarnings: data.collision_warnings || 0
                });

                // Log TRUE gyroscope rotation correction info
                if (data.orientation_corrected) {
                    console.log(`🎯 Applied ${data.rotation_applied}° TRUE gyroscope-based rotation correction`);
                } else {
                    console.log('➡️ No TRUE gyroscope rotation correction applied');
                }

                // SMART SCENE CHANGE DETECTION: Only clear queue if scene actually changed
                // Analyze scene to determine if announcements are needed
                const sceneAnalysis = analyzeSceneChange(data.detections);
                console.log('🔍 Scene analysis:', sceneAnalysis);

                if (sceneAnalysis.shouldAnnounce) {
                    // Only clear queue if there's a significant scene change
                    if (sceneAnalysis.criticalChange) {
                        console.log('⚠️ CRITICAL scene change - clearing audio queue for urgent updates');
                        clearAudioQueue();
                    } else {
                        console.log('ℹ️ Minor scene change - keeping audio queue (will queue new announcements)');
                        // Don't clear queue for minor changes - let state machine handle it
                    }
                } else {
                    console.log('✅ No scene change - skipping audio announcements to avoid interruption');
                }

                // Store detections for pathfinding
                window.lastDetections = data.detections;

                drawDetections(data.detections);
                updateRealtimeDetections(data.detections);
                updateStats(data.detections);

                // Only announce if scene has changed
                if (sceneAnalysis.shouldAnnounce) {
                    announceDetections(data.detections, sceneAnalysis);
                }

                // Recalculate path if pathfinding is enabled and goal is set
                const pathfindingState = getPathfindingState();
                if (pathfindingState.enabled && pathfindingState.goal) {
                    calculateNavigationPath(canvas, video);
                }

                incrementFrameCount();
                console.log('📊 Frame incremented');

                updateRealtimeStats();
            } else {
                console.error('❌ Detection failed:', data.error);
            }
        } catch (error) {
            // CRITICAL: Clear timeout to prevent memory leak
            if (timeoutId !== null) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }

            // Don't log abort errors - they're expected when stopping
            if (error.name === 'AbortError') {
                console.log('✅ Request cancelled successfully');
            } else {
                console.error('❌ Real-time detection error:', error);
                console.error('Error details:', {
                    name: error.name,
                    message: error.message,
                    stack: error.stack
                });
            }
        } finally {
            // Ensure timeout is cleared even if error handling fails
            if (timeoutId !== null) {
                clearTimeout(timeoutId);
                timeoutId = null;
            }

            isProcessingRequest = false;
            currentAbortController = null;
            console.log('🔓 Request processing unlocked');
        }
    }, TimingConfig.detection.loopInterval);

    // Update FPS counter
    const fpsInterval = setInterval(() => {
        if (!detectionActive) {
            console.log('⏹️ Stopping FPS interval');
            clearInterval(fpsInterval);
            return;
        }
        console.log('📈 Updating FPS from interval');
        updateFPS();
    }, TimingConfig.detection.fpsUpdateInterval);
}

/**
 * Set tracking enabled state
 * @param {boolean} enabled
 */
export function setTrackingEnabledState(enabled) {
    trackingEnabled = enabled;
    setTrackingEnabled(enabled);
    setDetectionTrackingEnabled(enabled);
}

/**
 * Get camera state
 * @returns {Object} Camera state
 */
export function getCameraState() {
    return {
        stream: stream,
        detectionActive: detectionActive,
        isProcessingRequest: isProcessingRequest,
        dashboardStreamingEnabled: dashboardStreamingEnabled
    };
}

/**
 * Toggle dashboard streaming on/off
 * @param {boolean} enabled - Whether to enable streaming
 */
export function toggleDashboardStreaming(enabled) {
    dashboardStreamingEnabled = enabled;

    if (enabled) {
        console.log('📹 Dashboard streaming enabled');
        startFrameUpload();
    } else {
        console.log('🔒 Dashboard streaming disabled - privacy mode active');
        stopFrameUpload();
    }

    // Update stored preference
    localStorage.setItem('dashboardStreamingEnabled', enabled);
}

/**
 * Upload frame to server for dashboard viewing from base64 data
 * This is called from the detection loop to reuse frames
 */
function uploadFrameFromData(imageDataURL) {
    if (!cameraId || !dashboardStreamingEnabled) {
        return;
    }

    try {
        // Extract base64 data (remove data:image/jpeg;base64, prefix)
        const frameData = imageDataURL.split(',')[1];

        // Upload to server (don't await - fire and forget for better performance)
        fetch(`/admin/cameras/${cameraId}/upload_frame`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ frame: frameData })
        }).catch(err => {
            // Silently handle errors to avoid console spam
            if (Math.random() < 0.02) {
                console.error('Frame upload error:', err);
            }
        });
    } catch (error) {
        // Silently ignore errors
    }
}

/**
 * Start frame upload - high-frequency for smooth dashboard viewing
 */
function startFrameUpload() {
    stopFrameUpload(); // Stop any existing interval

    if (!dashboardStreamingEnabled) {
        return;
    }

    lastFrameUploadTime = Date.now();
    frameUploadStallWarningShown = false;

    // Upload frames at 30 FPS (33ms interval) for smooth dashboard viewing
    // This is separate from detection frames which run at 6-7 FPS
    frameUploadInterval = setInterval(() => {
        if (!cameraId || !video || !dashboardStreamingEnabled || !detectionActive) {
            return;
        }

        try {
            const now = Date.now();
            const timeSinceLastUpload = now - lastFrameUploadTime;

            // Warn if interval is being throttled (should be ~33ms but allow up to 100ms)
            if (timeSinceLastUpload > 100 && !frameUploadStallWarningShown) {
                console.warn(`⚠️ Frame upload interval throttled: ${timeSinceLastUpload}ms (expected 33ms) - Browser may be throttling timers`);
                frameUploadStallWarningShown = true;
            }

            lastFrameUploadTime = now;

            // Quick frame capture
            const tempCanvas = document.createElement('canvas');
            tempCanvas.width = video.videoWidth || 640;
            tempCanvas.height = video.videoHeight || 480;
            const tempCtx = tempCanvas.getContext('2d');

            // Draw current video frame
            tempCtx.drawImage(video, 0, 0);

            // Convert to base64 JPEG with medium quality for balance (60%)
            const imageData = tempCanvas.toDataURL('image/jpeg', 0.6);

            // Upload using existing function
            uploadFrameFromData(imageData);
        } catch (error) {
            // Log errors occasionally
            if (Math.random() < 0.05) {
                console.error('Frame upload error:', error);
            }
        }
    }, 33); // 33ms = ~30 FPS

    console.log('📹 Frame upload started at 30 FPS (33ms interval) for smooth dashboard streaming');
}

/**
 * Stop frame upload
 */
function stopFrameUpload() {
    if (frameUploadInterval) {
        clearInterval(frameUploadInterval);
        frameUploadInterval = null;
        console.log('📹 Frame upload stopped');
    }
}

/**
 * Monitor page visibility to detect when browser throttles timers
 */
function initializeVisibilityMonitoring() {
    // Listen for page visibility changes
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            console.warn('⚠️ Page hidden - Browser may throttle timers and stop frame uploads');
            console.warn('⚠️ Keep this tab active and screen on for continuous operation');
        } else {
            console.log('✅ Page visible again - Timers should resume normal operation');
            // Reset throttle warning flag when page becomes visible again
            frameUploadStallWarningShown = false;
        }
    });

    // Also monitor for screen wake lock if supported (prevents screen from turning off)
    if ('wakeLock' in navigator) {
        console.log('✅ Wake Lock API supported - can prevent screen sleep');
    } else {
        console.warn('⚠️ Wake Lock API not supported - screen may turn off and stop detection');
    }
}

// Initialize visibility monitoring on module load
if (typeof document !== 'undefined') {
    initializeVisibilityMonitoring();
}
