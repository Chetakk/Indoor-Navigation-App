/**
 * Camera Module
 * Handles camera initialization, video stream, and real-time detection loop
 */

import { initializeOrientation, getCurrentOrientation, gyroscopeData, gyroscopePermissionGranted } from './gyroscope.js';
import { audioState, clearAudioQueue } from './audio.js';
import { announceDetections, clearTrackingData as clearDetectionTracking, setCanvas, setTrackingEnabled as setDetectionTrackingEnabled } from './detection.js';
import { clearTrackingData as clearTrackingState, setTrackingEnabled } from './tracking.js';
import { getPathfindingState, calculateNavigationPath } from './pathfinding.js';
import { drawDetections, updateRealtimeDetections, updateStats, updateRealtimeStats, updateFPS, setCanvasAndVideo, setDetectionActive, incrementFrameCount } from './ui.js';
import TimingConfig from './timingConfig.js';

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

    // REAL-TIME for blind navigation: immediate hazard detection
    detectionInterval = setInterval(async () => {
        if (!detectionActive || !video || !canvas || !ctx) {
            console.log('❌ Detection inactive or missing elements');
            return;
        }

        // Skip if already processing a request
        if (isProcessingRequest) {
            console.log('⏭️ Skipping frame - previous request still processing');
            return;
        }

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

            // Send to server for detection with abort signal and timeout
            const timeoutId = setTimeout(() => {
                console.error('⏱️ Request timeout');
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

                // CRITICAL FIX: Clear audio queue when new detection response arrives
                // This prevents announcements for objects that have disappeared
                clearAudioQueue();

                // Store detections for pathfinding
                window.lastDetections = data.detections;

                drawDetections(data.detections);
                updateRealtimeDetections(data.detections);
                updateStats(data.detections);
                announceDetections(data.detections);

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
        isProcessingRequest: isProcessingRequest
    };
}
