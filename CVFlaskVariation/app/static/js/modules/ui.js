/**
 * UI/Rendering Module
 * Handles statistics updates, FPS counter, drawing detections, and UI elements
 */

import { getCurrentOrientation } from './gyroscope.js';
import { estimateDistance } from './detection.js';
import { getTrackColor, trackedObjects, trackingEnabled, cleanupStaleTrackColors } from './tracking.js';
import { getPathfindingState } from './pathfinding.js';
import TimingConfig from './timingConfig.js';

// UI state
let objectCount = 0;
let frameCount = 0;
let startTime = Date.now();
let avgConfidence = 0;
let canvas = null;
let ctx = null;
let video = null;
let detectionActive = false;
let detectionBoxesEnabled = true; // Toggle for drawing detection boxes

// Circular queue for detection results (keep last 1 - absolute latest only!)
const MAX_DETECTION_ITEMS = 1;
let detectionResultsQueue = [];

/**
 * Set canvas, context, and video references
 * @param {HTMLCanvasElement} canvasElement
 * @param {CanvasRenderingContext2D} contextElement
 * @param {HTMLVideoElement} videoElement
 */
export function setCanvasAndVideo(canvasElement, contextElement, videoElement) {
    canvas = canvasElement;
    ctx = contextElement;
    video = videoElement;
}

/**
 * Set detection active state
 * @param {boolean} active
 */
export function setDetectionActive(active) {
    detectionActive = active;
    if (active) {
        startTime = Date.now();
        frameCount = 0;
    }
}

/**
 * Increment frame count
 */
export function incrementFrameCount() {
    frameCount++;
}

/**
 * Update statistics display
 * @param {Array<Object>} detections - Array of detection objects
 */
export function updateStats(detections) {
    console.log('Updating stats with', detections.length, 'detections');

    const objectCountEl = document.getElementById('objectCount');
    const confidenceAvgEl = document.getElementById('confidenceAvg');

    // Update object count
    objectCount = detections.length;
    if (objectCountEl) {
        objectCountEl.textContent = objectCount;
        console.log('Updated object count to:', objectCount);
    }

    // Update average confidence
    if (detections.length > 0) {
        const totalConfidence = detections.reduce((sum, det) => sum + det.confidence, 0);
        avgConfidence = (totalConfidence / detections.length * 100);
        if (confidenceAvgEl) {
            confidenceAvgEl.textContent = avgConfidence.toFixed(1) + '%';
            console.log('Updated avg confidence to:', avgConfidence.toFixed(1) + '%');
        }
    } else {
        avgConfidence = 0;
        if (confidenceAvgEl) {
            confidenceAvgEl.textContent = '0%';
        }
    }

    // Add pulsing effect to stats when they update
    [objectCountEl, confidenceAvgEl].forEach(element => {
        if (element) {
            element.style.transform = 'scale(1.1)';
            element.style.transition = 'transform 0.2s ease';
            setTimeout(() => {
                element.style.transform = 'scale(1)';
            }, TimingConfig.ui.statsAnimationDuration);
        }
    });
}

/**
 * Update FPS counter
 */
export function updateFPS() {
    if (!detectionActive) return;

    const now = Date.now();
    const elapsed = (now - startTime) / 1000;
    const fps = elapsed > 0 ? (frameCount / elapsed) : 0;

    const fpsElement = document.getElementById('fpsCounter');
    if (fpsElement) {
        fpsElement.textContent = fps.toFixed(1);
        console.log('Updated FPS to:', fps.toFixed(1));

        // Add visual feedback for FPS updates
        fpsElement.style.transform = 'scale(1.05)';
        fpsElement.style.transition = 'transform 0.2s ease';
        setTimeout(() => {
            fpsElement.style.transform = 'scale(1)';
        }, TimingConfig.ui.fpsAnimationDuration);
    }
}

/**
 * Enhanced real-time statistics update
 */
export function updateRealtimeStats() {
    if (!detectionActive) return;

    console.log('Updating realtime stats');

    const now = Date.now();
    const elapsed = (now - startTime) / 1000;
    const currentFps = elapsed > 0 ? (frameCount / elapsed) : 0;

    // Update FPS
    const fpsElement = document.getElementById('fpsCounter');
    if (fpsElement) {
        fpsElement.textContent = currentFps.toFixed(1);
    }

    // Update other stats
    const objectCountEl = document.getElementById('objectCount');
    const confidenceAvgEl = document.getElementById('confidenceAvg');

    if (objectCountEl) {
        objectCountEl.textContent = objectCount.toString();
    }

    if (confidenceAvgEl) {
        confidenceAvgEl.textContent = avgConfidence.toFixed(1) + '%';
    }

    // Add pulsing effect to all stats
    ['objectCount', 'fpsCounter', 'confidenceAvg'].forEach(id => {
        const element = document.getElementById(id);
        if (element) {
            element.style.transform = 'scale(1.05)';
            element.style.transition = 'transform 0.2s ease';
            setTimeout(() => {
                element.style.transform = 'scale(1)';
            }, TimingConfig.ui.realtimeStatsAnimationDuration);
        }
    });
}

/**
 * Toggle header visibility
 */
export function toggleHeader() {
    const details = document.querySelector('.project-details');
    const toggleText = document.getElementById('toggleText');

    if (details.style.display === 'none') {
        details.style.display = 'grid';
        toggleText.textContent = 'Hide Details';
        details.style.animation = 'slideInDown 0.5s ease-out';
    } else {
        details.style.display = 'none';
        toggleText.textContent = 'Show Details';
    }
}

/**
 * Toggle detection boxes on/off
 */
export function toggleDetectionBoxes() {
    detectionBoxesEnabled = !detectionBoxesEnabled;

    const boxesBtn = document.getElementById('boxesBtnText');
    if (boxesBtn) {
        boxesBtn.textContent = detectionBoxesEnabled ? '📦 Boxes ON' : '📦 Boxes OFF';
    }

    console.log('Detection boxes:', detectionBoxesEnabled ? 'ENABLED' : 'DISABLED');

    // Clear canvas if disabled
    if (!detectionBoxesEnabled && canvas && ctx) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
}

/**
 * Draw detection boxes with tracking and direction labels
 * @param {Array<Object>} detections - Array of detection objects
 */
export function drawDetections(detections) {
    if (!canvas || !ctx) return;

    // ALWAYS clear previous drawings to remove old hitboxes
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Skip drawing if detection boxes are disabled
    if (!detectionBoxesEnabled) {
        console.log('Detection boxes disabled - skipping canvas drawing');
        return;
    }

    if (detections.length === 0) {
        console.log('No detections to draw - canvas cleared');
        return;
    }

    // Clean up stale tracked objects (not in current detections)
    const currentTrackIds = new Set();
    detections.forEach(detection => {
        if (detection.track_id !== null && detection.track_id !== undefined) {
            currentTrackIds.add(detection.track_id);
        }
    });

    // Remove tracked objects that are no longer detected - use centralized threshold
    const staleThreshold = TimingConfig.tracking.staleThreshold;
    const now = Date.now();
    trackedObjects.forEach((value, trackId) => {
        if (!currentTrackIds.has(trackId) || (now - value.lastSeen > staleThreshold)) {
            trackedObjects.delete(trackId);
            console.log(`Removed stale tracked object: ID ${trackId} (${value.class_name})`);
        }
    });

    // Clean up stale track colors
    cleanupStaleTrackColors(currentTrackIds);

    detections.forEach(detection => {
        const [x1, y1, x2, y2] = detection.bbox;
        const width = x2 - x1;
        const height = y2 - y1;

        // Update tracked objects map
        if (detection.track_id !== null && detection.track_id !== undefined) {
            trackedObjects.set(detection.track_id, {
                class_name: detection.class_name,
                lastSeen: Date.now(),
                trajectory: detection.trajectory || []
            });
        }

        // Get distance and direction info
        const distanceInfo = estimateDistance(detection.bbox, detection.class_name,
                                            video.videoWidth || 640, video.videoHeight || 480);

        // Scale coordinates to canvas size
        const scaleX = canvas.width / (video.videoWidth || 640);
        const scaleY = canvas.height / (video.videoHeight || 480);

        const scaledX = x1 * scaleX;
        const scaledY = y1 * scaleY;
        const scaledWidth = width * scaleX;
        const scaledHeight = height * scaleY;

        // Color code based on tracking or distance
        let boxColor, fillColor;

        // Use consistent color for tracked objects
        if (trackingEnabled && detection.track_id !== null && detection.track_id !== undefined) {
            const trackColor = getTrackColor(detection.track_id);
            boxColor = trackColor;
            fillColor = trackColor.replace('hsl', 'hsla').replace(')', ', 0.2)');
        } else {
            // Fallback to distance-based coloring
            switch(distanceInfo.category) {
                case 'immediate':
                    boxColor = '#ff0000'; // Red for very close
                    fillColor = 'rgba(255, 0, 0, 0.2)';
                    break;
                case 'near':
                    boxColor = '#ff8800'; // Orange for close
                    fillColor = 'rgba(255, 136, 0, 0.2)';
                    break;
                case 'medium':
                    boxColor = '#ffff00'; // Yellow for medium
                    fillColor = 'rgba(255, 255, 0, 0.2)';
                    break;
                case 'far':
                    boxColor = '#00ff00'; // Green for far
                    fillColor = 'rgba(0, 255, 0, 0.2)';
                    break;
                default:
                    boxColor = '#0088ff'; // Blue for very far
                    fillColor = 'rgba(0, 136, 255, 0.2)';
            }
        }

        // Set drawing style
        ctx.strokeStyle = boxColor;
        ctx.lineWidth = distanceInfo.category === 'immediate' ? 4 : 2;
        ctx.fillStyle = fillColor;
        ctx.font = '14px Arial';

        // Draw bounding box
        ctx.strokeRect(scaledX, scaledY, scaledWidth, scaledHeight);
        ctx.fillRect(scaledX, scaledY, scaledWidth, scaledHeight);

        // Enhanced labels with direction and tracking
        const confidence = (detection.confidence * 100).toFixed(1);
        const trackLabel = detection.track_id !== null ? `ID: ${detection.track_id}` : '';
        const label = `${detection.class_name} ${confidence}%`;
        const distanceLabel = `${distanceInfo.distance}`;
        const directionLabel = `Direction: ${distanceInfo.direction}`;

        // Add movement info if available
        let movementLabel = '';
        if (detection.movement && detection.movement.direction !== 'stationary') {
            const directionIcon = {
                'moving_right': '→',
                'moving_left': '←',
                'moving_up': '↑',
                'moving_down': '↓'
            }[detection.movement.direction] || '↔';

            movementLabel = `${directionIcon} ${detection.movement.speed_class}`;
        }

        // Calculate label background size
        ctx.font = 'bold 14px Arial';
        const labelWidth = Math.max(
            ctx.measureText(label).width,
            ctx.measureText(distanceLabel).width,
            ctx.measureText(directionLabel).width,
            trackLabel ? ctx.measureText(trackLabel).width : 0,
            movementLabel ? ctx.measureText(movementLabel).width : 0
        ) + 10;

        const labelHeight = trackLabel && movementLabel ? 85 : trackLabel || movementLabel ? 75 : 65;

        // Draw label background
        ctx.fillStyle = boxColor;
        ctx.fillRect(scaledX, scaledY - labelHeight, labelWidth, labelHeight);

        // Draw labels text
        ctx.fillStyle = 'white';
        let yOffset = -labelHeight + 15;

        // Track ID (if available)
        if (trackLabel) {
            ctx.font = 'bold 12px Arial';
            ctx.fillText(trackLabel, scaledX + 5, scaledY + yOffset);
            yOffset += 18;
        }

        // Class name and confidence
        ctx.font = 'bold 14px Arial';
        ctx.fillText(label, scaledX + 5, scaledY + yOffset);
        yOffset += 18;

        // Distance
        ctx.font = '12px Arial';
        ctx.fillText(distanceLabel, scaledX + 5, scaledY + yOffset);
        yOffset += 16;

        // Direction
        ctx.fillText(directionLabel, scaledX + 5, scaledY + yOffset);

        // Movement (if available)
        if (movementLabel) {
            yOffset += 16;
            ctx.fillText(movementLabel, scaledX + 5, scaledY + yOffset);
        }

        // Draw trajectory if tracking is enabled and trajectory exists
        if (trackingEnabled && detection.trajectory && detection.trajectory.length > 1) {
            ctx.strokeStyle = boxColor;
            ctx.lineWidth = 2;
            ctx.beginPath();

            detection.trajectory.forEach((point, idx) => {
                const trajX = point[0] * scaleX;
                const trajY = point[1] * scaleY;

                if (idx === 0) {
                    ctx.moveTo(trajX, trajY);
                } else {
                    ctx.lineTo(trajX, trajY);
                }
            });

            ctx.stroke();

            // Draw trajectory points
            detection.trajectory.forEach(point => {
                const trajX = point[0] * scaleX;
                const trajY = point[1] * scaleY;
                ctx.fillStyle = boxColor;
                ctx.beginPath();
                ctx.arc(trajX, trajY, 3, 0, 2 * Math.PI);
                ctx.fill();
            });
        }

        // Draw collision warning if present
        if (detection.collision && detection.collision.collision_risk) {
            const centerX = (scaledX + scaledWidth / 2);
            const centerY = (scaledY + scaledHeight / 2);

            // Draw warning icon based on severity
            let warningColor;
            switch(detection.collision.collision_severity) {
                case 'high':
                    warningColor = '#ff0000';
                    break;
                case 'medium':
                    warningColor = '#ff8800';
                    break;
                default:
                    warningColor = '#ffff00';
            }

            // Pulsing warning circle
            const pulseSize = 30 + Math.sin(Date.now() / 200) * 5;
            ctx.strokeStyle = warningColor;
            ctx.lineWidth = 3;
            ctx.beginPath();
            ctx.arc(centerX, centerY, pulseSize, 0, 2 * Math.PI);
            ctx.stroke();

            // Warning triangle
            ctx.fillStyle = warningColor;
            ctx.font = 'bold 24px Arial';
            ctx.fillText('⚠', centerX - 12, centerY + 8);

            // Draw predicted position if available
            if (detection.collision.predicted_position) {
                const predX = detection.collision.predicted_position[0] * scaleX;
                const predY = detection.collision.predicted_position[1] * scaleY;

                // Draw line from current to predicted position
                ctx.strokeStyle = warningColor;
                ctx.lineWidth = 2;
                ctx.setLineDash([5, 5]);
                ctx.beginPath();
                ctx.moveTo(centerX, centerY);
                ctx.lineTo(predX, predY);
                ctx.stroke();
                ctx.setLineDash([]);

                // Draw predicted position marker
                ctx.fillStyle = warningColor;
                ctx.beginPath();
                ctx.arc(predX, predY, 8, 0, 2 * Math.PI);
                ctx.fill();
            }
        }
    });

    // Draw reactive navigation guidance if available
    const pathfindingState = getPathfindingState();
    const userX = canvas.width / 2;
    const userY = canvas.height - 20;

    // Draw user position (center bottom)
    ctx.fillStyle = '#0088ff';
    ctx.font = 'bold 30px Arial';
    ctx.fillText('📍', userX - 15, userY);

    if (pathfindingState.enabled && pathfindingState.guidance) {
        const scaleX = canvas.width / (video.videoWidth || 640);
        const scaleY = canvas.height / (video.videoHeight || 480);
        const guidance = pathfindingState.guidance;

        // Draw goal marker
        if (pathfindingState.goal) {
            const goalX = pathfindingState.goal[0] * scaleX;
            const goalY = pathfindingState.goal[1] * scaleY;

            // Pulsing goal marker
            const pulseSize = 20 + Math.sin(Date.now() / 300) * 5;
            ctx.fillStyle = '#00ff00';
            ctx.beginPath();
            ctx.arc(goalX, goalY, pulseSize, 0, 2 * Math.PI);
            ctx.fill();

            ctx.font = 'bold 30px Arial';
            ctx.fillText('🎯', goalX - 15, goalY + 10);

            // Draw direct line to goal (dashed)
            if (guidance.goal_direction) {
                ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
                ctx.lineWidth = 2;
                ctx.setLineDash([10, 10]);
                ctx.beginPath();
                ctx.moveTo(userX, userY);
                ctx.lineTo(goalX, goalY);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }

        // Draw safe direction arrow (the main navigation aid)
        if (guidance.safe_direction) {
            const arrowLength = 150; // pixels
            const safeDir = guidance.safe_direction;

            // Calculate arrow endpoint
            const arrowEndX = userX + safeDir[0] * arrowLength * scaleX;
            const arrowEndY = userY + safeDir[1] * arrowLength * scaleY;

            // Determine arrow color based on deviation from goal
            let arrowColor = '#00ff00'; // Green by default
            if (guidance.deviation_angle > 45) {
                arrowColor = '#ff8800'; // Orange if significant deviation
            } else if (guidance.deviation_angle > 20) {
                arrowColor = '#ffff00'; // Yellow if moderate deviation
            }

            // Draw thick arrow shaft
            ctx.strokeStyle = arrowColor;
            ctx.lineWidth = 8;
            ctx.lineCap = 'round';
            ctx.beginPath();
            ctx.moveTo(userX, userY);
            ctx.lineTo(arrowEndX, arrowEndY);
            ctx.stroke();

            // Draw arrowhead
            const headLength = 25;
            const angle = Math.atan2(safeDir[1], safeDir[0]);

            ctx.fillStyle = arrowColor;
            ctx.beginPath();
            ctx.moveTo(arrowEndX, arrowEndY);
            ctx.lineTo(
                arrowEndX - headLength * Math.cos(angle - Math.PI / 6),
                arrowEndY - headLength * Math.sin(angle - Math.PI / 6)
            );
            ctx.lineTo(
                arrowEndX - headLength * Math.cos(angle + Math.PI / 6),
                arrowEndY - headLength * Math.sin(angle + Math.PI / 6)
            );
            ctx.closePath();
            ctx.fill();

            // Draw guidance text overlay
            if (guidance.guidance && guidance.guidance.primary) {
                const textY = canvas.height - 80;
                const textX = canvas.width / 2;

                // Draw semi-transparent background
                ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
                const textWidth = ctx.measureText(guidance.guidance.primary).width + 20;
                ctx.fillRect(textX - textWidth/2, textY - 25, textWidth, 35);

                // Draw guidance text
                ctx.fillStyle = arrowColor;
                ctx.font = 'bold 16px Arial';
                ctx.textAlign = 'center';
                ctx.fillText(guidance.guidance.primary, textX, textY);
                ctx.textAlign = 'left';
            }
        }

        // Highlight obstacles in path
        if (guidance.obstacles) {
            guidance.obstacles.forEach(obs => {
                if (obs.in_path) {
                    const [x1, y1, x2, y2] = obs.bbox;
                    const obsX = (x1 + x2) / 2 * scaleX;
                    const obsY = (y1 + y2) / 2 * scaleY;

                    // Draw warning circle around obstacle
                    const warningColor = obs.is_moving ? '#ff0000' : '#ff8800';
                    ctx.strokeStyle = warningColor;
                    ctx.lineWidth = 3;
                    ctx.beginPath();
                    ctx.arc(obsX, obsY, 40, 0, 2 * Math.PI);
                    ctx.stroke();

                    // Draw warning icon
                    ctx.fillStyle = warningColor;
                    ctx.font = 'bold 24px Arial';
                    ctx.fillText('⚠', obsX - 12, obsY + 8);
                }
            });
        }
    }
}

/**
 * Update real-time detections display with gyroscope information
 * Uses circular queue to show only latest detections
 * @param {Array<Object>} detections - Array of detection objects
 */
export function updateRealtimeDetections(detections) {
    const resultsContainer = document.getElementById('detectionResults');

    // Group detections by class name FIRST
    const groupedDetections = {};
    detections.forEach(detection => {
        const className = detection.class_name;
        if (!groupedDetections[className]) {
            groupedDetections[className] = [];
        }
        groupedDetections[className].push(detection);
    });

    // Add new grouped detections to circular queue (FIFO)
    Object.keys(groupedDetections).forEach(className => {
        const detectionData = {
            className,
            detections: groupedDetections[className],
            timestamp: Date.now()
        };

        // Remove oldest if queue is full
        if (detectionResultsQueue.length >= MAX_DETECTION_ITEMS) {
            const removed = detectionResultsQueue.shift();
            console.log('Detection queue full - removed oldest:', removed.className);
        }

        // Check if this class already exists in queue - update it instead
        const existingIndex = detectionResultsQueue.findIndex(item => item.className === className);
        if (existingIndex >= 0) {
            detectionResultsQueue[existingIndex] = detectionData; // Update existing
        } else {
            detectionResultsQueue.push(detectionData); // Add new
        }
    });

    // Clear previous results with fade effect
    resultsContainer.style.opacity = '0.5';

    setTimeout(() => {
        resultsContainer.innerHTML = '';

        if (detectionResultsQueue.length === 0) {
            resultsContainer.innerHTML = `
                <div style="text-align: center; padding: 20px;">
                    <div style="font-size: 3rem; margin-bottom: 10px;">🔍</div>
                    <p style="color: var(--text-secondary); font-style: italic;">
                        No objects detected
                    </p>
                </div>
            `;
        } else {
            // Render from queue (newest items)
            detectionResultsQueue.forEach((queueItem, index) => {
                const className = queueItem.className;
                const detectionList = queueItem.detections;
                const count = detectionList.length;
                const avgConfidence = detectionList.reduce((sum, det) => sum + det.confidence, 0) / count;

                // Get direction for the closest object of this type
                const closestDetection = detectionList.reduce((closest, current) => {
                    const currentArea = (current.bbox[2] - current.bbox[0]) * (current.bbox[3] - current.bbox[1]);
                    const closestArea = (closest.bbox[2] - closest.bbox[0]) * (closest.bbox[3] - closest.bbox[1]);
                    return currentArea > closestArea ? current : closest;
                });

                const imageWidth = canvas ? canvas.width : 640;
                const imageHeight = canvas ? canvas.height : 480;
                const distanceInfo = estimateDistance(closestDetection.bbox, className, imageWidth, imageHeight);

                const item = document.createElement('div');
                item.className = 'detection-item';
                item.style.animationDelay = `${index * 0.1}s`;

                // Add confidence color coding
                let confidenceColor = '#ef4444'; // red for low confidence
                if (avgConfidence > 0.7) confidenceColor = '#10b981'; // green for high
                else if (avgConfidence > 0.5) confidenceColor = '#f59e0b'; // yellow for medium

                // Get current gyroscope status
                const gyroData = getCurrentOrientation();
                const gyroStatus = gyroData ?
                    (gyroData.calibrated ?
                        `🎯 TRUE Gyro: ${gyroData.gyroscope_rotation.toFixed(1)}° (${gyroData.angular_velocity_z.toFixed(3)} rad/s)` :
                        '⚙️ TRUE Gyro: Not Calibrated'
                    ) :
                    '❌ TRUE Gyro: Disabled';

                item.innerHTML = `
                    <div class="detection-class">
                        ${count}x ${className}
                    </div>
                    <div class="detection-confidence" style="color: ${confidenceColor}">
                        Avg: ${(avgConfidence * 100).toFixed(1)}%
                        <span style="margin-left: 10px; font-size: 0.8em;">
                            ${avgConfidence > 0.8 ? '🎯' : avgConfidence > 0.6 ? '✨' : '⚡'}
                        </span>
                    </div>
                    <div style="color: var(--text-secondary); font-size: 0.85rem; margin-top: 4px;">
                        Distance: ${distanceInfo.distance}
                    </div>
                    <div style="color: #4CAF50; font-size: 0.85rem; margin-top: 4px; font-weight: 600;">
                        📍 Direction: ${distanceInfo.direction}
                    </div>
                    <div style="color: #2196F3; font-size: 0.75rem; margin-top: 4px;">
                        ${gyroStatus}
                    </div>
                `;

                resultsContainer.appendChild(item);
            });
        }

        resultsContainer.style.opacity = '1';
    }, TimingConfig.ui.detectionResultsFadeDelay);
}

/**
 * Add orientation status indicator to the page
 */
export function addOrientationStatusIndicator() {
    const statusContainer = document.querySelector('.stats-container') || document.body;

    const orientationStatus = document.createElement('div');
    orientationStatus.id = 'orientationStatus';
    orientationStatus.style.cssText = `
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: rgba(0, 0, 0, 0.7);
        border-radius: 8px;
        color: white;
        font-size: 0.9rem;
        margin-top: 10px;
    `;

    function updateOrientationStatus() {
        const currentOrientation = getCurrentOrientation();

        if (!currentOrientation) {
            orientationStatus.innerHTML = `
                <span style="color: #ff4444;">❌</span>
                <span>TRUE Gyroscope: Disabled</span>
            `;
        } else if (!currentOrientation.calibrated) {
            orientationStatus.innerHTML = `
                <span style="color: #ffaa00;">⚙️</span>
                <span>TRUE Gyroscope: Not Calibrated</span>
                <button onclick="window.calibrateGyroscope()" style="margin-left: 8px; padding: 4px 8px; border: none; border-radius: 4px; background: #FF9800; color: white; cursor: pointer;">Calibrate</button>
            `;
        } else {
            orientationStatus.innerHTML = `
                <span style="color: #44ff44;">🎯</span>
                <span>TRUE Gyroscope Active (${currentOrientation.gyroscope_rotation.toFixed(1)}°)</span>
                <span style="font-size: 0.8em; color: #aaa;">
                    Angular Vel: ${currentOrientation.angular_velocity_z.toFixed(3)} rad/s
                </span>
                ${(!currentOrientation || !currentOrientation.calibrated ?
                    '<button onclick="window.calibrateGyroscope()" style="margin-left: 8px; padding: 4px 8px; border: none; border-radius: 4px; background: #FF9800; color: white; cursor: pointer;">Calibrate</button>' :
                    '')}
            `;
        }
    }

    updateOrientationStatus();
    statusContainer.appendChild(orientationStatus);

    // Update status regularly
    setInterval(updateOrientationStatus, TimingConfig.ui.orientationStatusInterval);
}
