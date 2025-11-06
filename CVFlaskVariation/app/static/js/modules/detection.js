/**
 * Detection Module
 * Handles object detection, distance estimation, collision warnings, and announcements
 */

import { speak, queueAnnouncement, audioState } from './audio.js';
import TimingConfig from './timingConfig.js';

// Shared state for collision alerts
export const collisionAlerts = new Map(); // Track when we last alerted for each object
export let lastAnnouncement = {};
let canvas = null;
let previousTrackedObjects = new Map(); // Store previous frame's tracks for comparison with timestamps
let trackFirstSeen = new Map(); // Track when each object was first detected
let trackLastMovement = new Map(); // Track last movement state for each object
let trackingEnabled = true;

// Minimum confidence threshold - ignore predictions below this
let MIN_CONFIDENCE_THRESHOLD = 0.3; // 30% minimum confidence

// Scene change detection - prevents redundant audio when nothing changed
let previousSceneHash = '';
let previousSceneDetections = [];

/**
 * Generate a hash representing the current scene state
 * Used to detect significant changes that warrant new audio announcements
 * @param {Array<Object>} detections - Current frame detections
 * @returns {string} Hash representing scene state
 */
function generateSceneHash(detections) {
    if (!detections || detections.length === 0) {
        return 'empty_scene';
    }

    // Create signature for each object: trackID_class_distanceCategory_direction_movement
    const signatures = detections
        .filter(d => d.confidence >= MIN_CONFIDENCE_THRESHOLD)
        .map(d => {
            const imageWidth = canvas ? canvas.width : 640;
            const imageHeight = canvas ? canvas.height : 480;
            // Pass depth data if available
            const depthData = { distance: d.distance, distance_confidence: d.distance_confidence, distance_method: d.distance_method };
            const distanceInfo = estimateDistance(d.bbox, d.class_name, imageWidth, imageHeight, depthData);

            // Include collision severity for critical changes
            const collisionSeverity = d.collision?.collision_severity || 'none';
            const isApproaching = d.collision?.is_approaching ? 'approaching' : 'static';

            // Movement state
            const movementDir = d.movement?.direction || 'unknown';
            const speedClass = d.movement?.speed_class || 'unknown';

            // Create signature
            const trackId = d.track_id !== null && d.track_id !== undefined ? d.track_id : d.class_name;
            return `${trackId}|${d.class_name}|${distanceInfo.category}|${distanceInfo.directionDetails.horizontal}|${movementDir}|${speedClass}|${collisionSeverity}|${isApproaching}`;
        })
        .sort()
        .join('__');

    return signatures || 'empty_scene';
}

/**
 * Determine if scene has changed significantly enough to warrant new audio
 * @param {Array<Object>} currentDetections - Current frame detections
 * @returns {Object} Change analysis with shouldAnnounce flag and change type
 */
export function analyzeSceneChange(currentDetections) {
    const currentHash = generateSceneHash(currentDetections);

    // First frame or empty previous scene
    if (!previousSceneHash || previousSceneHash === 'empty_scene') {
        previousSceneHash = currentHash;
        previousSceneDetections = JSON.parse(JSON.stringify(currentDetections));
        return {
            shouldAnnounce: currentHash !== 'empty_scene',
            changeType: 'initial_scene',
            criticalChange: false
        };
    }

    // No change detected
    if (currentHash === previousSceneHash) {
        return {
            shouldAnnounce: false,
            changeType: 'no_change',
            criticalChange: false
        };
    }

    // Scene changed - analyze what changed
    const currentTrackIds = new Set(
        currentDetections
            .filter(d => d.confidence >= MIN_CONFIDENCE_THRESHOLD)
            .map(d => d.track_id !== null && d.track_id !== undefined ? d.track_id : d.class_name)
    );

    const previousTrackIds = new Set(
        previousSceneDetections
            .filter(d => d.confidence >= MIN_CONFIDENCE_THRESHOLD)
            .map(d => d.track_id !== null && d.track_id !== undefined ? d.track_id : d.class_name)
    );

    // Check for new objects (CRITICAL)
    const newObjects = [...currentTrackIds].filter(id => !previousTrackIds.has(id));

    // Check for critical collision warnings (CRITICAL)
    const hasCriticalCollision = currentDetections.some(d =>
        d.confidence >= MIN_CONFIDENCE_THRESHOLD &&
        d.collision?.collision_severity === 'high'
    );

    // Check for new approaching objects (HIGH PRIORITY)
    const hasNewApproachingObject = currentDetections.some(d => {
        if (d.confidence < MIN_CONFIDENCE_THRESHOLD) return false;
        const trackId = d.track_id !== null && d.track_id !== undefined ? d.track_id : d.class_name;
        const wasNotPreviouslyApproaching = !previousSceneDetections.some(pd => {
            const prevTrackId = pd.track_id !== null && pd.track_id !== undefined ? pd.track_id : pd.class_name;
            return prevTrackId === trackId && pd.collision?.is_approaching;
        });
        return d.collision?.is_approaching && wasNotPreviouslyApproaching;
    });

    // Check for movement changes (MEDIUM PRIORITY)
    const hasMovementChange = currentDetections.some(d => {
        if (d.confidence < MIN_CONFIDENCE_THRESHOLD) return false;
        const trackId = d.track_id !== null && d.track_id !== undefined ? d.track_id : d.class_name;
        const prevDetection = previousSceneDetections.find(pd => {
            const prevTrackId = pd.track_id !== null && pd.track_id !== undefined ? pd.track_id : pd.class_name;
            return prevTrackId === trackId;
        });

        if (!prevDetection) return false;

        const prevMovement = prevDetection.movement?.direction || 'stationary';
        const currentMovement = d.movement?.direction || 'stationary';

        return prevMovement !== currentMovement;
    });

    // Determine change type and criticality
    let changeType = 'minor_change';
    let criticalChange = false;

    if (hasCriticalCollision) {
        changeType = 'critical_collision';
        criticalChange = true;
    } else if (newObjects.length > 0) {
        changeType = 'new_objects';
        criticalChange = true;
    } else if (hasNewApproachingObject) {
        changeType = 'approaching_objects';
        criticalChange = true;
    } else if (hasMovementChange) {
        changeType = 'movement_change';
        criticalChange = false;
    }

    // Update previous state
    previousSceneHash = currentHash;
    previousSceneDetections = JSON.parse(JSON.stringify(currentDetections));

    return {
        shouldAnnounce: true,
        changeType: changeType,
        criticalChange: criticalChange,
        newObjectCount: newObjects.length
    };
}

/**
 * Set minimum confidence threshold for detections
 * @param {number} threshold - Confidence threshold (0.0 to 1.0)
 */
export function setConfidenceThreshold(threshold) {
    if (threshold >= 0 && threshold <= 1) {
        MIN_CONFIDENCE_THRESHOLD = threshold;
        console.log(`Confidence threshold set to ${(threshold * 100).toFixed(0)}%`);
    } else {
        console.error('Invalid threshold. Must be between 0.0 and 1.0');
    }
}

/**
 * Get current confidence threshold
 * @returns {number} Current threshold
 */
export function getConfidenceThreshold() {
    return MIN_CONFIDENCE_THRESHOLD;
}

/**
 * Set canvas reference for distance calculations
 * @param {HTMLCanvasElement} canvasElement
 */
export function setCanvas(canvasElement) {
    canvas = canvasElement;
}

/**
 * Set tracking enabled state
 * @param {boolean} enabled
 */
export function setTrackingEnabled(enabled) {
    trackingEnabled = enabled;
}

/**
 * Get object direction based on bounding box position
 * @param {Array<number>} bbox - Bounding box [x1, y1, x2, y2]
 * @param {number} imageWidth - Image width
 * @param {number} imageHeight - Image height
 * @returns {Object} Direction information
 */
export function getObjectDirection(bbox, imageWidth, imageHeight) {
    const [x1, y1, x2, y2] = bbox;

    // Calculate center point of the bounding box
    const centerX = (x1 + x2) / 2;
    const centerY = (y1 + y2) / 2;

    // Normalize coordinates to 0-1 range
    const normalizedX = centerX / imageWidth;
    const normalizedY = centerY / imageHeight;

    // No coordinate inversion needed - YOLO detections use standard image coordinates
    // where X=0 is left edge and X=width is right edge, matching the visual display

    console.log(`DEBUG DIRECTION - Object center: (${centerX.toFixed(1)}, ${centerY.toFixed(1)}), Image size: (${imageWidth}, ${imageHeight})`);
    console.log(`DEBUG DIRECTION - Normalized X: ${normalizedX.toFixed(3)} (0=left edge, 1=right edge)`);

    // Determine horizontal direction (more detailed zones)
    let horizontalDirection;
    if (normalizedX < 0.2) {
        horizontalDirection = "far left";
    } else if (normalizedX < 0.35) {
        horizontalDirection = "left";
    } else if (normalizedX < 0.45) {
        horizontalDirection = "slightly left";
    } else if (normalizedX < 0.55) {
        horizontalDirection = "center";
    } else if (normalizedX < 0.65) {
        horizontalDirection = "slightly right";
    } else if (normalizedX < 0.8) {
        horizontalDirection = "right";
    } else {
        horizontalDirection = "far right";
    }

    console.log(`DEBUG DIRECTION - Calculated horizontal: ${horizontalDirection} (normalizedX: ${normalizedX.toFixed(3)})`);

    // Determine vertical direction
    let verticalDirection;
    if (normalizedY < 0.3) {
        verticalDirection = "above";
    } else if (normalizedY < 0.7) {
        verticalDirection = "level";
    } else {
        verticalDirection = "below";
    }

    // Combine directions for natural speech
    let direction;
    if (horizontalDirection === "center") {
        if (verticalDirection === "above") {
            direction = "ahead and above";
        } else if (verticalDirection === "below") {
            direction = "ahead and below";
        } else {
            direction = "directly ahead";
        }
    } else {
        if (verticalDirection === "above") {
            direction = horizontalDirection + " and above";
        } else if (verticalDirection === "below") {
            direction = horizontalDirection + " and below";
        } else {
            direction = horizontalDirection;
        }
    }

    return {
        direction: direction,
        horizontal: horizontalDirection,
        vertical: verticalDirection,
        coordinates: { x: normalizedX, y: normalizedY }
    };
}

/**
 * Estimate distance with direction information
 * ENHANCED (2025-10-18): Now uses real depth estimation from backend when available!
 * @param {Array<number>} bbox - Bounding box [x1, y1, x2, y2]
 * @param {string} className - Object class name
 * @param {number} imageWidth - Image width (default 640)
 * @param {number} imageHeight - Image height (default 480)
 * @param {Object} depthData - Real depth data from backend {distance, distance_confidence, distance_method}
 * @returns {Object} Distance and direction information
 */
export function estimateDistance(bbox, className, imageWidth = 640, imageHeight = 480, depthData = null) {
    const [x1, y1, x2, y2] = bbox;
    const width = x2 - x1;
    const height = y2 - y1;
    const area = width * height;

    // Get direction information
    const directionInfo = getObjectDirection(bbox, imageWidth, imageHeight);

    let estimatedDistance;
    let distanceCategory;
    let distanceMeters = null;
    let usingRealDepth = false;

    // NEW (2025-10-18): Use real depth estimation from backend if available
    if (depthData && depthData.distance !== null && depthData.distance !== undefined) {
        distanceMeters = depthData.distance;
        usingRealDepth = true;

        // Convert meters to distance category and natural language
        if (distanceMeters < 1.0) {
            estimatedDistance = `${distanceMeters.toFixed(1)} meters`;  // "0.8 meters"
            distanceCategory = "immediate";
        } else if (distanceMeters < 2.0) {
            estimatedDistance = `${distanceMeters.toFixed(1)} meters`;  // "1.5 meters"
            distanceCategory = "immediate";
        } else if (distanceMeters < 4.0) {
            estimatedDistance = `${Math.round(distanceMeters)} meters`;  // "3 meters"
            distanceCategory = "near";
        } else if (distanceMeters < 8.0) {
            estimatedDistance = `${Math.round(distanceMeters)} meters`;  // "6 meters"
            distanceCategory = "medium";
        } else if (distanceMeters < 15.0) {
            estimatedDistance = `${Math.round(distanceMeters)} meters`;  // "12 meters"
            distanceCategory = "far";
        } else {
            estimatedDistance = `${Math.round(distanceMeters)} meters`;  // "20 meters"
            distanceCategory = "distant";
        }

        console.log(`✓ Using REAL depth: ${estimatedDistance} (method: ${depthData.distance_method}, conf: ${(depthData.distance_confidence * 100).toFixed(0)}%)`);
    } else {
        // FALLBACK: Use bbox-based estimation (old method)
        const videoArea = imageWidth * imageHeight;
        const objectRatio = area / videoArea;

        if (objectRatio > 0.3) {
            estimatedDistance = "very close";
            distanceCategory = "immediate";
        } else if (objectRatio > 0.15) {
            estimatedDistance = "close";
            distanceCategory = "near";
        } else if (objectRatio > 0.05) {
            estimatedDistance = "medium distance";
            distanceCategory = "medium";
        } else if (objectRatio > 0.01) {
            estimatedDistance = "far";
            distanceCategory = "far";
        } else {
            estimatedDistance = "very far";
            distanceCategory = "distant";
        }

        console.log(`⚠ Using bbox fallback: ${estimatedDistance} (ratio: ${(objectRatio * 100).toFixed(1)}%)`);
    }

    return {
        distance: estimatedDistance,
        category: distanceCategory,
        distanceMeters: distanceMeters,  // NEW: Real distance in meters
        usingRealDepth: usingRealDepth,  // NEW: Flag indicating if using real depth
        depthConfidence: depthData?.distance_confidence || 0,  // NEW: Confidence score
        depthMethod: depthData?.distance_method || 'bbox_fallback',  // NEW: Estimation method
        ratio: area / (imageWidth * imageHeight),  // Keep for legacy
        direction: directionInfo.direction,
        directionDetails: directionInfo
    };
}

/**
 * Check for collision warnings and announce them - CRITICAL for blind safety
 * BATCHES multiple critical warnings to prevent spam
 * @param {Array<Object>} detections - Array of detection objects
 */
export function checkCollisionWarnings(detections) {
    if (!audioState.enabled || detections.length === 0) return;

    const now = Date.now();
    const staleThreshold = TimingConfig.tracking.staleThreshold;

    // Collect all critical warnings to batch them
    const criticalWarnings = [];
    const otherWarnings = [];

    detections.forEach(detection => {
        // Skip low confidence detections
        if (detection.confidence < MIN_CONFIDENCE_THRESHOLD) {
            console.log(`Skipping low confidence collision check: ${detection.class_name} (${(detection.confidence * 100).toFixed(1)}%)`);
            return;
        }

        // CRITICAL FIX: Skip stale tracked objects
        const trackId = detection.track_id || detection.class_name;
        if (previousTrackedObjects.has(trackId)) {
            const prevData = previousTrackedObjects.get(trackId);
            if (now - prevData.lastSeen > staleThreshold) {
                console.log(`Skipping stale collision check: ${detection.class_name} (ID: ${trackId})`);
                return;
            }
        }

        const collision = detection.collision;
        if (!collision || !collision.collision_risk) return;

        const lastAlert = collisionAlerts.get(trackId) || 0;

        let warningMessage = '';
        let priority = 'normal';
        let alertInterval = TimingConfig.collision.defaultInterval;
        const objectName = detection.class_name;

        // Get movement information if available
        const movement = detection.movement;
        let movementDesc = '';

        if (movement && movement.direction !== 'stationary') {
            const directionMap = {
                'moving_right': 'moving right',
                'moving_left': 'moving left',
                'moving_away': 'moving away',
                'moving_closer': 'approaching'
            };

            const directionText = directionMap[movement.direction] || 'moving';
            const speedText = movement.speed_class || 'medium speed';
            movementDesc = ` ${directionText} at ${speedText}`;
        }

        // Get distance info for better context (with real depth!)
        const imageWidth = canvas ? canvas.width : 640;
        const imageHeight = canvas ? canvas.height : 480;
        const depthData = { distance: detection.distance, distance_confidence: detection.distance_confidence, distance_method: detection.distance_method };
        const distanceInfo = estimateDistance(detection.bbox, objectName, imageWidth, imageHeight, depthData);

        // Enhanced warnings with trajectory and movement
        switch(collision.collision_severity) {
            case 'high':
                if (collision.is_approaching) {
                    warningMessage = `Danger! ${objectName} approaching directly ahead${movementDesc}!`;
                } else {
                    warningMessage = `Warning! ${objectName} directly ahead!`;
                }
                priority = 'critical'; // Upgraded to critical for immediate threats
                alertInterval = TimingConfig.collision.criticalInterval;
                break;
            case 'medium':
                if (collision.is_approaching) {
                    warningMessage = `Caution! ${objectName} approaching from ${distanceInfo.direction}${movementDesc}`;
                } else {
                    warningMessage = `Caution! ${objectName} at ${distanceInfo.direction}`;
                }
                priority = 'high';
                alertInterval = TimingConfig.collision.mediumInterval;
                break;
            case 'low':
                if (collision.is_approaching) {
                    warningMessage = `${objectName} approaching from distance, ${distanceInfo.direction}`;
                } else {
                    warningMessage = `${objectName} nearby at ${distanceInfo.direction}`;
                }
                priority = 'normal';
                alertInterval = TimingConfig.collision.lowInterval;
                break;
        }

        // Check if enough time has passed for this specific object
        if (now - lastAlert < alertInterval) return;

        if (warningMessage) {
            // Collect warnings by priority for batching
            if (priority === 'critical') {
                criticalWarnings.push({ trackId, warningMessage, priority });
            } else {
                otherWarnings.push({ trackId, warningMessage, priority });
            }
        }
    });

    // ANTI-SPAM: Batch critical warnings into single announcement
    // This prevents "Danger! person..." -> "Danger! car..." -> "Danger! chair..." spam
    if (criticalWarnings.length > 0) {
        if (criticalWarnings.length === 1) {
            // Single critical warning - announce normally
            const warning = criticalWarnings[0];
            console.log('🚨 CRITICAL WARNING:', warning.warningMessage);
            speak(warning.warningMessage, 'critical', true);
            collisionAlerts.set(warning.trackId, now);
        } else {
            // Multiple critical warnings - batch them
            const objects = criticalWarnings.map(w => {
                // Extract object name from message
                const match = w.warningMessage.match(/(?:Danger|Warning)!\s+(\w+)/i);
                return match ? match[1] : 'object';
            });

            // Create batched message
            const batchedMessage = `Multiple dangers! ${objects.join(', ')} directly ahead!`;
            console.log('🚨 BATCHED CRITICAL WARNINGS:', batchedMessage, `(${criticalWarnings.length} objects)`);
            speak(batchedMessage, 'critical', true);

            // Update collision alerts for all objects
            criticalWarnings.forEach(w => collisionAlerts.set(w.trackId, now));
        }
    }

    // Announce other warnings normally (high/normal priority)
    otherWarnings.forEach(warning => {
        console.log('⚠️ COLLISION WARNING:', warning.warningMessage, `Priority: ${warning.priority}`);
        speak(warning.warningMessage, warning.priority, false);
        collisionAlerts.set(warning.trackId, now);
    });
}

/**
 * Announce tracking-specific events (new tracks, lost tracks, movement changes)
 * @param {Array<Object>} detections - Array of detection objects
 */
export function announceTrackingEvents(detections) {
    if (!audioState.enabled || !trackingEnabled) return;

    const now = Date.now();
    const currentTrackIds = new Set();

    // CRITICAL FIX: Build current track IDs FIRST
    detections.forEach(detection => {
        if (detection.confidence >= MIN_CONFIDENCE_THRESHOLD &&
            detection.track_id !== null &&
            detection.track_id !== undefined) {
            currentTrackIds.add(detection.track_id);
        }
    });

    // CRITICAL FIX: Clean up stale tracks BEFORE announcements
    // This prevents announcing objects that have already disappeared
    const staleThreshold = TimingConfig.tracking.staleThreshold;
    previousTrackedObjects.forEach((prevData, trackId) => {
        const isStale = !currentTrackIds.has(trackId) || (now - prevData.lastSeen > staleThreshold);
        if (isStale) {
            // Object left the scene or timed out - silently clean up tracking data
            console.log(`👋 TRACK LOST (silent cleanup): ${prevData.class_name} (ID: ${trackId})`);

            // Clean up all tracking data for this ID
            previousTrackedObjects.delete(trackId);
            trackFirstSeen.delete(trackId);
            trackLastMovement.delete(trackId);
            trackLastMovement.delete(`${trackId}_stationary`);
            collisionAlerts.delete(trackId);
        }
    });

    // Now process detections for announcements
    detections.forEach(detection => {
        // Skip low confidence detections
        if (detection.confidence < MIN_CONFIDENCE_THRESHOLD) {
            console.log(`Skipping low confidence tracking: ${detection.class_name} (${(detection.confidence * 100).toFixed(1)}%)`);
            return;
        }

        if (detection.track_id !== null && detection.track_id !== undefined) {
            // Check for new tracks
            if (!previousTrackedObjects.has(detection.track_id)) {
                // New object detected
                const imageWidth = canvas ? canvas.width : 640;
                const imageHeight = canvas ? canvas.height : 480;
                const depthData = { distance: detection.distance, distance_confidence: detection.distance_confidence, distance_method: detection.distance_method };
                const distanceInfo = estimateDistance(detection.bbox, detection.class_name, imageWidth, imageHeight, depthData);

                const announcement = `New ${detection.class_name} detected at ${distanceInfo.direction}`;
                console.log('🆕 NEW TRACK:', announcement);
                queueAnnouncement(announcement, 'high');

                // Track first seen time
                trackFirstSeen.set(detection.track_id, now);
            } else {
                // Check for significant movement changes
                const prevDetection = previousTrackedObjects.get(detection.track_id);
                const prevMovement = prevDetection.movement;
                const currentMovement = detection.movement;

                if (prevMovement && currentMovement) {
                    // Check if movement changed from stationary to moving
                    if (prevMovement.direction === 'stationary' && currentMovement.direction !== 'stationary') {
                        const directionMap = {
                            'moving_right': 'to the right',
                            'moving_left': 'to the left',
                            'moving_away': 'away',
                            'moving_closer': 'closer to you'
                        };
                        const directionText = directionMap[currentMovement.direction] || '';
                        const announcement = `${detection.class_name} started moving ${directionText}`;
                        console.log('🏃 MOVEMENT STARTED:', announcement);
                        queueAnnouncement(announcement, 'normal');
                        trackLastMovement.set(detection.track_id, currentMovement.direction);
                    }
                    // Check if speed increased significantly
                    else if (prevMovement.speed_class === 'slow' && currentMovement.speed_class === 'fast') {
                        const announcement = `${detection.class_name} speed increased`;
                        console.log('⚡ SPEED CHANGE:', announcement);
                        queueAnnouncement(announcement, 'high');
                    }
                    // Check if direction changed significantly
                    else if (prevMovement.direction !== 'stationary' &&
                             currentMovement.direction !== 'stationary' &&
                             prevMovement.direction !== currentMovement.direction) {
                        const lastAnnouncedDirection = trackLastMovement.get(detection.track_id);
                        if (lastAnnouncedDirection !== currentMovement.direction) {
                            const directionMap = {
                                'moving_right': 'to the right',
                                'moving_left': 'to the left',
                                'moving_away': 'away from you',
                                'moving_closer': 'toward you'
                            };
                            const directionText = directionMap[currentMovement.direction] || '';
                            const announcement = `${detection.class_name} changed direction, now moving ${directionText}`;
                            console.log('🔄 DIRECTION CHANGE:', announcement);
                            queueAnnouncement(announcement, 'normal');
                            trackLastMovement.set(detection.track_id, currentMovement.direction);
                        }
                    }
                }

                // Check for objects that have been stationary for a long time
                const firstSeenTime = trackFirstSeen.get(detection.track_id);
                if (firstSeenTime && (now - firstSeenTime) > TimingConfig.collision.stationaryThreshold) {
                    const movement = detection.movement;
                    if (movement && movement.direction === 'stationary') {
                        // Only announce periodically
                        const lastStationary = trackLastMovement.get(`${detection.track_id}_stationary`) || 0;
                        if (now - lastStationary > TimingConfig.collision.stationaryReannounce) {
                            const imageWidth = canvas ? canvas.width : 640;
                            const imageHeight = canvas ? canvas.height : 480;
                            const depthData = { distance: detection.distance, distance_confidence: detection.distance_confidence, distance_method: detection.distance_method };
                            const distanceInfo = estimateDistance(detection.bbox, detection.class_name, imageWidth, imageHeight, depthData);
                            const announcement = `${detection.class_name} stationary at ${distanceInfo.direction}`;
                            console.log('⏸️ LONG STATIONARY:', announcement);
                            queueAnnouncement(announcement, 'low');
                            trackLastMovement.set(`${detection.track_id}_stationary`, now);
                        }
                    }
                }
            }
        }
    });

    // Update previous tracked objects for next frame with timestamps
    // Only update objects that are in current detections
    detections.forEach(detection => {
        if (detection.track_id !== null &&
            detection.track_id !== undefined &&
            detection.confidence >= MIN_CONFIDENCE_THRESHOLD) {
            previousTrackedObjects.set(detection.track_id, {
                class_name: detection.class_name,
                movement: detection.movement,
                bbox: detection.bbox,
                collision: detection.collision,
                lastSeen: now  // CRITICAL: Add timestamp for stale detection
            });
        }
    });
}

/**
 * Announce detections with direction information and smart scene change handling
 * @param {Array<Object>} detections - Array of detection objects
 * @param {Object} sceneAnalysis - Scene change analysis from analyzeSceneChange()
 */
export function announceDetections(detections, sceneAnalysis = null) {
    console.log('Announcing detections:', detections.length, 'objects');

    if (!audioState.enabled || detections.length === 0) {
        console.log('Audio disabled or no detections');
        return;
    }

    // If no scene analysis provided, assume we should announce
    if (!sceneAnalysis) {
        sceneAnalysis = { shouldAnnounce: true, changeType: 'unknown', criticalChange: false };
    }

    // 1. Check for tracking events (new/lost tracks, movement changes)
    announceTrackingEvents(detections);

    // 2. Check for collisions (higher priority) - ALWAYS check for safety
    checkCollisionWarnings(detections);

    const now = Date.now();
    const announcements = [];

    // Group detections by class and find closest of each type
    const groupedDetections = {};
    detections.forEach((detection, index) => {
        // Skip low confidence detections
        if (detection.confidence < MIN_CONFIDENCE_THRESHOLD) {
            console.log(`Skipping low confidence announcement: ${detection.class_name} (${(detection.confidence * 100).toFixed(1)}%)`);
            return;
        }

        console.log(`Detection ${index}:`, detection);
        const className = detection.class_name;

        // Use actual image dimensions if available
        const imageWidth = canvas ? canvas.width : 640;
        const imageHeight = canvas ? canvas.height : 480;
        const depthData = { distance: detection.distance, distance_confidence: detection.distance_confidence, distance_method: detection.distance_method };
        const distanceInfo = estimateDistance(detection.bbox, className, imageWidth, imageHeight, depthData);

        console.log(`Distance and direction for ${className}:`, distanceInfo);

        if (!groupedDetections[className] ||
            distanceInfo.ratio > groupedDetections[className].distanceInfo.ratio) {
            groupedDetections[className] = { ...detection, distanceInfo };
        }
    });

    // 3. Create announcements for each object type with direction and movement
    Object.keys(groupedDetections).forEach(className => {
        const detection = groupedDetections[className];
        const lastTime = lastAnnouncement[className] || 0;

        // CRITICAL: Dynamic timing optimized for blind navigation safety
        let announcementInterval = TimingConfig.collision.farAnnouncementInterval;
        if (detection.distanceInfo.category === 'immediate') {
            announcementInterval = TimingConfig.collision.immediateAnnouncementInterval;
        } else if (detection.distanceInfo.category === 'near') {
            announcementInterval = TimingConfig.collision.nearAnnouncementInterval;
        } else if (detection.distanceInfo.category === 'medium') {
            announcementInterval = TimingConfig.collision.mediumAnnouncementInterval;
        }

        // Only announce if enough time has passed
        if (now - lastTime > announcementInterval) {
            const count = detections.filter(d => d.class_name === className).length;
            const countText = count > 1 ? `${count} ${className}s` : `${className}`;

            // Build movement description if available
            let movementDesc = '';
            const movement = detection.movement;
            if (movement && movement.direction !== 'stationary') {
                const directionMap = {
                    'moving_right': 'moving right',
                    'moving_left': 'moving left',
                    'moving_away': 'moving away',
                    'moving_closer': 'approaching'
                };
                const directionText = directionMap[movement.direction] || 'moving';
                const speedText = movement.speed_class || 'medium speed';
                movementDesc = `, ${directionText} at ${speedText}`;
            }

            // Enhanced announcement with direction and movement
            const announcement = `${countText} ${detection.distanceInfo.distance} to your ${detection.distanceInfo.direction}${movementDesc}`;

            // Adjust priority based on movement
            let priority = detection.distanceInfo.category === 'immediate' ? 'high' : 'normal';
            if (movement && movement.direction !== 'stationary' && detection.distanceInfo.category !== 'far') {
                priority = 'high'; // Moving objects nearby are higher priority
            }

            announcements.push({
                text: announcement,
                priority: priority,
                className: className,
                direction: detection.distanceInfo.direction,
                isMoving: movement && movement.direction !== 'stationary'
            });

            lastAnnouncement[className] = now;
            console.log('Added directional announcement with movement:', announcement);
        }
    });

    console.log('Total announcements with direction and movement:', announcements.length);

    // Announce in order of priority (immediate dangers first, then moving objects)
    announcements.sort((a, b) => {
        if (a.priority === b.priority) {
            // If same priority, moving objects first
            return a.isMoving && !b.isMoving ? -1 : 1;
        }
        return a.priority === 'high' ? -1 : 1;
    });

    // Queue announcements instead of speaking directly (better queue management)
    if (announcements.length > 0) {
        // Queue the most important detection
        const mainAnnouncement = announcements[0];
        console.log('Queueing directional announcement:', mainAnnouncement.text);
        queueAnnouncement(mainAnnouncement.text, mainAnnouncement.priority);

        // Queue additional moving objects if any (max 2 more)
        const additionalMoving = announcements.slice(1).filter(a => a.isMoving).slice(0, 2);
        additionalMoving.forEach(announcement => {
            queueAnnouncement(announcement.text, 'low');
        });
    } else {
        console.log('No new announcements to queue');
    }
}

/**
 * Clear tracking data (called when stopping detection)
 */
export function clearTrackingData() {
    previousTrackedObjects.clear();
    trackFirstSeen.clear();
    trackLastMovement.clear();
    collisionAlerts.clear();
    lastAnnouncement = {};
    console.log('✅ Cleared tracking data');
}
