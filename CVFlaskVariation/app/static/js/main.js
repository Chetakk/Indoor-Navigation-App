/**
 * Main Application Entry Point
 * Imports all modules and initializes the application
 */

// Import all modules
import { toggleAudio, testAudio, speak, audioState } from './modules/audio.js';
import { initializeOrientation, calibrateGyroscope, requestOrientationPermission, gyroscopePermissionGranted, gyroscopeData } from './modules/gyroscope.js';
import { estimateDistance } from './modules/detection.js';
import { togglePathfinding, setNavigationGoal, getPathfindingState } from './modules/pathfinding.js';
import { toggleHeader, toggleDetectionBoxes, addOrientationStatusIndicator } from './modules/ui.js';
import { startCamera, stopDetection, startRealtimeAnalysis, getCameraState } from './modules/camera.js';
import TimingConfig from './modules/timingConfig.js';

// Make functions globally available for onclick handlers
window.startCamera = startCamera;
window.stopDetection = stopDetection;
window.toggleAudio = toggleAudio;
window.testAudio = testAudio;
window.calibrateGyroscope = calibrateGyroscope;
window.requestOrientationPermission = requestOrientationPermission;
window.togglePathfinding = togglePathfinding;
window.toggleHeader = toggleHeader;
window.toggleDetectionBoxes = toggleDetectionBoxes;

// Make pathfinding state accessible
Object.defineProperty(window, 'pathfindingEnabled', {
    get: () => getPathfindingState().enabled
});

/**
 * Test backend connection
 */
async function testConnection() {
    console.log('🧪 Testing backend connection...');
    speak('Testing backend connection');

    try {
        console.log('📡 Fetching /test_connection...');
        const response = await fetch('/test_connection', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ test: true })
        });

        console.log('📡 Response status:', response.status);
        console.log('📡 Response headers:', [...response.headers.entries()]);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        console.log('✅ Test response:', data);

        const message = `✅ Backend connection successful!\nMessage: ${data.message}\nTimestamp: ${new Date(data.timestamp * 1000).toLocaleTimeString()}`;
        alert(message);
        speak('Backend connection test successful');

    } catch (error) {
        console.error('❌ Connection test failed:', error);
        alert(`❌ Connection test failed:\n${error.message}\n\nCheck console for details.`);
        speak('Backend connection test failed');
    }
}

window.testConnection = testConnection;

/**
 * Test stats function
 */
function testStats() {
    console.log('Testing stats update...');

    // Test with sample data including direction
    const sampleDetections = [
        { class_name: 'person', confidence: 0.85, bbox: [100, 50, 300, 400] },
        { class_name: 'car', confidence: 0.92, bbox: [400, 200, 500, 250] },
        { class_name: 'person', confidence: 0.78, bbox: [200, 100, 350, 450] }
    ];

    console.log('Updating stats with sample data:', sampleDetections);
    // These functions are imported from ui module
    // updateStats(sampleDetections);
    // updateRealtimeDetections(sampleDetections);

    console.log('Stats test completed');
}

window.testStats = testStats;

/**
 * Check if device is mobile
 * @returns {boolean}
 */
function isMobileDevice() {
    return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

/**
 * Helper function: Announce current objects on demand
 */
function announceCurrentObjects() {
    const cameraState = getCameraState();

    if (!cameraState.detectionActive) {
        speak("Detection is not active. Say start to begin.", 'high');
        return;
    }

    if (!window.lastDetections || window.lastDetections.length === 0) {
        speak("No objects currently detected.", 'high');
        return;
    }

    // Group detections by class
    const groupedDetections = {};
    window.lastDetections.forEach(detection => {
        const className = detection.class_name;
        if (!groupedDetections[className]) {
            groupedDetections[className] = [];
        }
        groupedDetections[className].push(detection);
    });

    // Announce each type
    const announcements = [];
    Object.keys(groupedDetections).forEach(className => {
        const detectionList = groupedDetections[className];
        const count = detectionList.length;

        // Get closest object of this type
        const closestDetection = detectionList.reduce((closest, current) => {
            const currentArea = (current.bbox[2] - current.bbox[0]) * (current.bbox[3] - current.bbox[1]);
            const closestArea = (closest.bbox[2] - closest.bbox[0]) * (closest.bbox[3] - closest.bbox[1]);
            return currentArea > closestArea ? current : closest;
        });

        const distanceInfo = estimateDistance(closestDetection.bbox, className, 640, 480);

        const countText = count > 1 ? `${count} ${className}s` : className;
        announcements.push(`${countText} ${distanceInfo.distance} to your ${distanceInfo.direction}`);
    });

    if (announcements.length > 0) {
        const fullAnnouncement = `I see ${announcements.length} type${announcements.length > 1 ? 's' : ''} of objects. ` +
                                 announcements.slice(0, 3).join('. ') + '.';
        speak(fullAnnouncement, 'high');
    }
}

window.announceCurrentObjects = announceCurrentObjects;

/**
 * Handle "find" voice commands for object navigation
 * @param {string} command - The voice command text
 */
function handleFindCommand(command) {
    console.log('Processing find command:', command);

    // Extract the object name from command
    // Patterns: "find bench", "find the chair", "find a door", "find table"
    const findMatch = command.match(/find\s+(the\s+|a\s+)?(\w+)/i);

    if (!findMatch) {
        speak("I couldn't understand what object to find. Try saying 'find door' or 'find chair'.", 'high');
        return;
    }

    const targetObject = findMatch[2].toLowerCase();
    console.log('Looking for object:', targetObject);

    // Check if detection is active
    const cameraState = getCameraState();
    if (!cameraState.detectionActive) {
        speak("Please start detection first by saying 'start'.", 'high');
        return;
    }

    // Check if we have recent detections
    if (!window.lastDetections || window.lastDetections.length === 0) {
        speak(`No objects detected. Cannot find ${targetObject}.`, 'high');
        return;
    }

    // Search for the target object in current detections
    let foundObject = null;
    let closestMatch = null;
    let minDistance = Infinity;

    window.lastDetections.forEach(detection => {
        const detectionName = detection.class_name.toLowerCase();

        // Exact match or partial match
        if (detectionName === targetObject || detectionName.includes(targetObject) || targetObject.includes(detectionName)) {
            const distanceInfo = estimateDistance(detection.bbox, detection.class_name, 640, 480);
            const bboxArea = (detection.bbox[2] - detection.bbox[0]) * (detection.bbox[3] - detection.bbox[1]);

            // Use bbox area as proxy for distance (larger = closer)
            if (bboxArea < minDistance) {
                minDistance = bboxArea;
                foundObject = detection;
                closestMatch = distanceInfo;
            }
        }
    });

    if (foundObject) {
        // Enable pathfinding if not already enabled
        if (!window.pathfindingEnabled) {
            togglePathfinding();
        }

        // Calculate center of the found object in video coordinates
        const centerX = (foundObject.bbox[0] + foundObject.bbox[2]) / 2;
        const centerY = (foundObject.bbox[1] + foundObject.bbox[3]) / 2;

        // Set navigation goal to the object's center
        const detectionCanvas = document.getElementById('detectionCanvas');
        const videoElement = document.getElementById('videoElement');

        if (detectionCanvas && videoElement) {
            // Convert from video coordinates to client coordinates
            const rect = detectionCanvas.getBoundingClientRect();
            const scaleX = detectionCanvas.width / (videoElement.videoWidth || 640);
            const scaleY = detectionCanvas.height / (videoElement.videoHeight || 480);

            // Transform: video coords -> canvas coords -> client coords
            const canvasX = centerX * scaleX;
            const canvasY = centerY * scaleY;
            const clientX = canvasX + rect.left;
            const clientY = canvasY + rect.top;

            // Create a synthetic event to set the goal
            const syntheticEvent = {
                clientX: clientX,
                clientY: clientY
            };

            setNavigationGoal(syntheticEvent, detectionCanvas, videoElement);

            // Announce success
            const announcement = `Found ${foundObject.class_name} ${closestMatch.distance} to your ${closestMatch.direction}. Setting navigation path.`;
            speak(announcement, 'high');
        }
    } else {
        // Object not found in current detections
        const suggestion = getSimilarObjects(targetObject);
        if (suggestion) {
            speak(`${targetObject} not found. Did you mean ${suggestion}?`, 'high');
        } else {
            speak(`Cannot find ${targetObject}. Currently visible objects are: ${getCurrentObjectList()}.`, 'high');
        }
    }
}

/**
 * Get a list of currently visible objects
 * @returns {string} Comma-separated list of object names
 */
function getCurrentObjectList() {
    if (!window.lastDetections || window.lastDetections.length === 0) {
        return 'none';
    }

    const uniqueObjects = [...new Set(window.lastDetections.map(d => d.class_name))];
    return uniqueObjects.slice(0, 5).join(', ');
}

/**
 * Suggest similar objects based on partial matching
 * @param {string} target - The target object name
 * @returns {string|null} Similar object name or null
 */
function getSimilarObjects(target) {
    if (!window.lastDetections || window.lastDetections.length === 0) {
        return null;
    }

    const uniqueObjects = [...new Set(window.lastDetections.map(d => d.class_name.toLowerCase()))];

    // Find objects that partially match
    for (const obj of uniqueObjects) {
        if (obj.includes(target) || target.includes(obj)) {
            return obj;
        }
    }

    return null;
}

/**
 * Initialize voice commands for accessibility
 */
let voiceRecognition = null;
let voiceCommandsEnabled = false;

function initializeVoiceCommands() {
    // Check if speech recognition is available
    if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
        console.warn('Accessibility: Speech recognition not available');
        return false;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    voiceRecognition = new SpeechRecognition();

    // Configure recognition
    voiceRecognition.continuous = true;
    voiceRecognition.interimResults = false;
    voiceRecognition.lang = 'en-US';

    voiceRecognition.onresult = function(event) {
        const command = event.results[event.results.length - 1][0].transcript.toLowerCase().trim();
        console.log('Voice command received:', command);

        const cameraState = getCameraState();

        // Process commands
        if (command.includes('start') || command.includes('begin')) {
            console.log('Voice: Starting detection');
            speak("Starting detection", 'high');
            if (!cameraState.detectionActive) {
                startCamera();
            }
        }
        else if (command.includes('stop') || command.includes('pause')) {
            console.log('Voice: Stopping detection');
            speak("Detection stopped", 'high');
            if (cameraState.detectionActive) {
                startCamera(); // Toggle off
            }
        }
        else if (command.includes('where') || command.includes('what')) {
            console.log('Voice: Announcing current objects');
            announceCurrentObjects();
        }
        else if (command.includes('find')) {
            console.log('Voice: Find command detected');
            handleFindCommand(command);
        }
        else if (command.includes('help')) {
            console.log('Voice: Showing help');
            const helpText = "Say start to begin detection, stop to pause, where am I to hear current objects, or find followed by an object name like find door, find bench, find chair, or find table to navigate to that object";
            speak(helpText, 'normal');
        }
        else if (command.includes('audio on') || command.includes('enable audio')) {
            if (!audioState.enabled) toggleAudio();
            speak("Audio enabled", 'high');
        }
        else if (command.includes('audio off') || command.includes('disable audio')) {
            if (audioState.enabled) toggleAudio();
            speak("Audio disabled", 'high');
        }
    };

    voiceRecognition.onerror = function(event) {
        console.error('Voice recognition error:', event.error);

        // Auto-restart on certain errors
        if (event.error === 'no-speech' || event.error === 'audio-capture') {
            console.log('Voice recognition: Restarting after error');
            setTimeout(() => {
                if (voiceCommandsEnabled && voiceRecognition) {
                    voiceRecognition.start();
                }
            }, TimingConfig.voice.errorRestartDelay);
        }
    };

    voiceRecognition.onend = function() {
        console.log('Voice recognition ended');
        // Auto-restart if still enabled
        if (voiceCommandsEnabled) {
            console.log('Voice recognition: Auto-restarting');
            setTimeout(() => {
                if (voiceCommandsEnabled && voiceRecognition) {
                    voiceRecognition.start();
                }
            }, TimingConfig.voice.autoRestartDelay);
        }
    };

    voiceCommandsEnabled = true;
    return true;
}

// Initialize app on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Initializing application...');

    // Add some initial stats
    document.getElementById('objectCount').textContent = '0';
    document.getElementById('fpsCounter').textContent = '0';
    document.getElementById('confidenceAvg').textContent = '0%';

    // Add click handler for canvas to set navigation goals
    const detectionCanvas = document.getElementById('detectionCanvas');
    const videoElement = document.getElementById('videoElement');
    if (detectionCanvas && videoElement) {
        detectionCanvas.addEventListener('click', (event) => {
            setNavigationGoal(event, detectionCanvas, videoElement);
        });
        console.log('Canvas click handler added for pathfinding');
    }

    // Initialize TRUE gyroscope tracking on page load
    console.log('Page loaded, initializing TRUE gyroscope...');
    initializeOrientation().then(success => {
        if (success) {
            console.log('✅ TRUE Gyroscope tracking initialized automatically');
        } else {
            console.log('❌ TRUE Gyroscope tracking not available - manual activation may be needed');
        }
    });

    // Add smooth scrolling for mobile
    document.documentElement.style.scrollBehavior = 'smooth';

    // Optimize for mobile performance
    if (isMobileDevice()) {
        // Reduce particle count for mobile
        const particles = document.querySelectorAll('.particle');
        particles.forEach((particle, index) => {
            if (index > 4) particle.style.display = 'none';
        });

        // Show TRUE gyroscope status on mobile
        setTimeout(() => {
            if (!gyroscopePermissionGranted) {
                console.log('Mobile detected - offering TRUE gyroscope permission');
                const shouldRequest = confirm('Enable TRUE gyroscope sensor for precise phone rotation correction in object detection?\n\nThis uses actual gyroscope angular velocity data for maximum accuracy.');
                if (shouldRequest) {
                    requestOrientationPermission();
                }
            }
        }, TimingConfig.mobile.gyroscopePromptDelay);
    }

    // Add orientation status indicator
    setTimeout(addOrientationStatusIndicator, TimingConfig.mobile.orientationIndicatorDelay);
});

// Handle visibility change to pause detection when tab is not active
document.addEventListener('visibilitychange', function() {
    const cameraState = getCameraState();

    if (document.hidden && cameraState.detectionActive) {
        // Pause detection when tab is hidden
        console.log('Tab hidden - detection will be paused by camera module');
    } else if (!document.hidden && cameraState.detectionActive) {
        // Resume detection when tab becomes visible
        startRealtimeAnalysis();
    }
});

// Enhanced error handling
window.addEventListener('error', function(e) {
    console.error('Global error:', e.error);
});

window.addEventListener('unhandledrejection', function(e) {
    console.error('Unhandled promise rejection:', e.reason);
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    stopDetection();
});

// Auto-hide project details on mobile
if (window.innerWidth <= 768) {
    setTimeout(() => {
        const details = document.querySelector('.project-details');
        const toggleText = document.getElementById('toggleText');
        if (details && toggleText) {
            details.style.display = 'none';
            toggleText.textContent = 'Show Details';
        }
    }, TimingConfig.mobile.detailsAutoHideDelay);
}

// AUTO-START: Automatically start detection for blind users
window.addEventListener('load', function() {
    // Check if auto-start is enabled (default: true for accessibility)
    const autoStartEnabled = localStorage.getItem('autoStart') !== 'false';

    console.log('Accessibility: Auto-start enabled:', autoStartEnabled);

    if (autoStartEnabled && isMobileDevice()) {
        // Wait for page to fully load
        setTimeout(() => {
            console.log('Accessibility: Auto-starting camera and detection...');
            speak("Welcome to blind navigation system. Starting camera and detection automatically.", 'high');

            // Auto-start camera and detection
            startCamera().then(() => {
                console.log('Accessibility: Auto-start successful');
                speak("Detection started. I will announce objects around you.", 'high');
            }).catch(err => {
                console.error('Accessibility: Auto-start failed:', err);
                speak("Please allow camera access when prompted.", 'high');
            });
        }, TimingConfig.mobile.autoStartDetectionDelay);
    } else if (!isMobileDevice()) {
        // Desktop: Show audio instructions only
        setTimeout(() => {
            const instructions = "Welcome to blind navigation system. " +
                               "Say 'start' to begin detection, " +
                               "or press the start button. " +
                               "The system will describe objects around you.";
            speak(instructions, 'high');
        }, TimingConfig.mobile.desktopInstructionsDelay);
    }
});

// Start voice commands automatically on ALL devices (desktop + mobile)
window.addEventListener('load', function() {
    setTimeout(() => {
        console.log('Accessibility: Initializing voice commands...');
        const initialized = initializeVoiceCommands();

        if (initialized) {
            try {
                voiceRecognition.start();
                console.log('Accessibility: Voice commands started successfully');

                // Inform user after a delay (so it doesn't overlap with auto-start message)
                setTimeout(() => {
                    const deviceType = isMobileDevice() ? 'mobile' : 'desktop';
                    console.log(`Voice commands active on ${deviceType}`);
                    speak("Voice commands active. Say start, stop, help, or find followed by an object name.", 'normal');
                }, TimingConfig.voice.activeMessageDelay);
            } catch (error) {
                console.error('Accessibility: Voice commands failed to start:', error);
                console.error('Error details:', error.message);

                // On desktop, speech recognition might need user interaction first
                if (!isMobileDevice()) {
                    console.log('Desktop mode: Voice commands may require user interaction to activate');
                    // Add a button click handler to start voice recognition on first interaction
                    document.addEventListener('click', function startVoiceOnClick() {
                        if (!voiceCommandsEnabled || !voiceRecognition) return;
                        try {
                            voiceRecognition.start();
                            console.log('Voice commands started after user interaction');
                            speak("Voice commands now active", 'normal');
                            document.removeEventListener('click', startVoiceOnClick);
                        } catch (err) {
                            console.error('Failed to start voice commands after click:', err);
                        }
                    }, { once: false });
                }
            }
        } else {
            console.warn('Voice commands not available on this device/browser');
            // Inform user that voice commands are not supported
            if (!isMobileDevice()) {
                console.log('Desktop browser may not support Speech Recognition API');
                setTimeout(() => {
                    speak("Voice commands are not available in this browser. Please use Chrome or Edge for voice command support.", 'normal');
                }, TimingConfig.voice.unsupportedMessageDelay);
            }
        }
    }, TimingConfig.voice.initDelay);
});

// Add keyboard shortcut for accessibility (spacebar to start/stop)
document.addEventListener('keydown', function(event) {
    // Spacebar: Toggle detection
    if (event.code === 'Space' && !event.target.matches('input, textarea')) {
        event.preventDefault();
        console.log('Accessibility: Spacebar pressed - toggling camera');
        startCamera();
    }
});

console.log('✅ Main application module loaded');
