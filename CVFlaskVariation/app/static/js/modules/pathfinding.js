/**
 * Reactive Navigation Module
 * Handles real-time obstacle avoidance and navigation guidance
 * Uses reactive navigation instead of static A* pathfinding for dynamic environments
 */

import { speak, queueAnnouncement } from './audio.js';

// Navigation state
export let navigationGoal = null;
export let navigationGuidance = null;
export let pathfindingEnabled = false;
export let lastNavigationUpdate = 0;
const NAVIGATION_UPDATE_INTERVAL = 500; // Update guidance every 500ms

/**
 * Set navigation goal by clicking on canvas
 * @param {MouseEvent} event - Click event
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {HTMLVideoElement} video - Video element
 */
export function setNavigationGoal(event, canvas, video) {
    if (!pathfindingEnabled || !canvas) return;

    const rect = canvas.getBoundingClientRect();
    const scaleX = (video.videoWidth || 640) / canvas.width;
    const scaleY = (video.videoHeight || 480) / canvas.height;

    const clickX = (event.clientX - rect.left) * scaleX;
    const clickY = (event.clientY - rect.top) * scaleY;

    navigationGoal = [clickX, clickY];

    console.log('Navigation goal set:', navigationGoal);
    speak('Navigation goal set');

    // Calculate path if we have detections
    calculateNavigationPath(canvas, video);
}

/**
 * Calculate reactive navigation guidance
 * This runs continuously while navigation is active
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {HTMLVideoElement} video - Video element
 */
export async function calculateNavigationPath(canvas, video) {
    if (!navigationGoal || !pathfindingEnabled) {
        return;
    }

    // Throttle updates to avoid excessive API calls
    const now = Date.now();
    if (now - lastNavigationUpdate < NAVIGATION_UPDATE_INTERVAL) {
        return;
    }
    lastNavigationUpdate = now;

    try {
        // Get current detections with movement data
        if (!window.lastDetections || window.lastDetections.length === 0) {
            console.log('No detections available for navigation');
            // Still provide basic guidance toward goal
            navigationGuidance = {
                reached_goal: false,
                guidance: {
                    primary: 'Walk toward destination',
                    warnings: [],
                    full_message: 'Walk toward destination'
                }
            };
            return;
        }

        const response = await fetch('/navigate_reactive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                detections: window.lastDetections,
                goal: navigationGoal,
                image_width: video.videoWidth || 640,
                image_height: video.videoHeight || 480
            })
        });

        const data = await response.json();

        if (data.success) {
            navigationGuidance = data;

            if (data.reached_goal) {
                speak('Destination reached');
                navigationGoal = null;
                navigationGuidance = null;
                pathfindingEnabled = false;
                const pathfindingBtn = document.getElementById('pathfindingBtn');
                if (pathfindingBtn) {
                    pathfindingBtn.innerHTML = '🗺️ Enable Navigation';
                    pathfindingBtn.classList.remove('active');
                }
            } else {
                // Queue voice guidance (throttled by audio system)
                const message = data.guidance.full_message;
                console.log('Navigation guidance:', message);

                // Only announce if there are warnings or significant direction change
                if (data.guidance.warnings.length > 0 || data.deviation_angle > 20) {
                    queueAnnouncement(message, 'medium');
                }
            }
        } else {
            console.warn('Navigation error:', data.error);
        }
    } catch (error) {
        console.error('Navigation error:', error);
    }
}

/**
 * Toggle navigation mode
 */
export function togglePathfinding() {
    pathfindingEnabled = !pathfindingEnabled;
    const pathfindingBtn = document.getElementById('pathfindingBtn');

    if (pathfindingEnabled) {
        speak('Navigation mode enabled. Click on the video to set a destination');
        console.log('Reactive navigation enabled - click on canvas to set goal');
        if (pathfindingBtn) {
            pathfindingBtn.innerHTML = '🗺️ Disable Navigation';
            pathfindingBtn.classList.add('active');
        }
    } else {
        navigationGoal = null;
        navigationGuidance = null;
        speak('Navigation mode disabled');
        console.log('Navigation disabled');
        if (pathfindingBtn) {
            pathfindingBtn.innerHTML = '🗺️ Enable Navigation';
            pathfindingBtn.classList.remove('active');
        }
    }
}

/**
 * Get current navigation state
 * @returns {Object} Current navigation state
 */
export function getPathfindingState() {
    return {
        enabled: pathfindingEnabled,
        guidance: navigationGuidance,
        goal: navigationGoal
    };
}
