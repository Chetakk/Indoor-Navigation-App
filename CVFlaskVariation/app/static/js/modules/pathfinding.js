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
let navigationInterval = null; // Interval for continuous guidance updates

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

    console.log('========================================');
    console.log('NAVIGATION GOAL SET:', navigationGoal);
    console.log('========================================');
    speak('Navigation goal set', 'high');

    // Calculate path immediately
    calculateNavigationPath(canvas, video);

    // Start continuous navigation guidance loop
    startNavigationLoop(canvas, video);
}

/**
 * Start continuous navigation guidance loop
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {HTMLVideoElement} video - Video element
 */
function startNavigationLoop(canvas, video) {
    // Clear any existing interval
    if (navigationInterval) {
        clearInterval(navigationInterval);
    }

    console.log('Starting continuous navigation guidance loop');

    // Run navigation updates continuously
    navigationInterval = setInterval(() => {
        if (pathfindingEnabled && navigationGoal) {
            console.log('Navigation loop: Calculating path...');
            calculateNavigationPath(canvas, video);
        } else {
            console.log('Navigation loop: Stopping (pathfinding disabled or no goal)');
            stopNavigationLoop();
        }
    }, NAVIGATION_UPDATE_INTERVAL);
}

/**
 * Stop continuous navigation guidance loop
 */
function stopNavigationLoop() {
    if (navigationInterval) {
        console.log('Stopping navigation guidance loop');
        clearInterval(navigationInterval);
        navigationInterval = null;
    }
}

/**
 * Calculate reactive navigation guidance
 * This runs continuously while navigation is active
 * @param {HTMLCanvasElement} canvas - Canvas element
 * @param {HTMLVideoElement} video - Video element
 */
export async function calculateNavigationPath(canvas, video) {
    if (!navigationGoal || !pathfindingEnabled) {
        console.log('Navigation calculation skipped: No goal or pathfinding disabled');
        return;
    }

    // Throttle updates to avoid excessive API calls
    const now = Date.now();
    if (now - lastNavigationUpdate < NAVIGATION_UPDATE_INTERVAL) {
        console.log(`Navigation throttled: ${now - lastNavigationUpdate}ms since last update`);
        return;
    }
    lastNavigationUpdate = now;

    console.log('Calculating navigation path...');

    try {
        // Get current detections with movement data
        console.log('Checking detections for navigation...');
        console.log('window.lastDetections available:', !!window.lastDetections);
        console.log('Detection count:', window.lastDetections ? window.lastDetections.length : 0);

        if (!window.lastDetections || window.lastDetections.length === 0) {
            console.log('No detections available for navigation - providing basic guidance');
            // Still provide basic guidance toward goal
            navigationGuidance = {
                reached_goal: false,
                guidance: {
                    primary: 'Walk toward destination',
                    warnings: [],
                    full_message: 'Walk toward destination'
                }
            };
            speak('Walk toward destination', 'normal');
            return;
        }

        console.log(`Processing navigation with ${window.lastDetections.length} detections`);

        console.log('Sending navigation request to /navigate_reactive...');
        console.log('Goal:', navigationGoal);
        console.log('Detections:', window.lastDetections.length);

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

        console.log('Navigation response status:', response.status);

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();
        console.log('Navigation response data:', data);

        if (data.success) {
            navigationGuidance = data;

            if (data.reached_goal) {
                console.log('DESTINATION REACHED!');
                speak('Destination reached', 'high');
                navigationGoal = null;
                navigationGuidance = null;
                pathfindingEnabled = false;
                stopNavigationLoop();
                const pathfindingBtn = document.getElementById('pathfindingBtn');
                if (pathfindingBtn) {
                    pathfindingBtn.innerHTML = '🗺️ Enable Navigation';
                    pathfindingBtn.classList.remove('active');
                }
            } else {
                // Navigation guidance - HIGH priority for blind navigation
                const message = data.guidance.full_message;
                console.log('========================================');
                console.log('NAVIGATION GUIDANCE:', message);
                console.log('User position:', data.user_position);
                console.log('Distance to goal:', data.distance_to_goal, 'meters');
                console.log('Warnings:', data.guidance.warnings);
                console.log('Deviation angle:', data.deviation_angle);
                console.log('========================================');

                // Determine priority based on warnings and deviation
                let priority = 'normal';
                if (data.guidance.warnings.length > 0) {
                    // Obstacles in path - HIGH priority to avoid collision
                    priority = 'high';
                } else if (data.deviation_angle > 30) {
                    // Significant direction change needed - HIGH priority
                    priority = 'high';
                }

                // Always announce navigation guidance (user wants to reach the goal!)
                // Use speak() with critical=false to respect cooldowns but still guide user
                speak(message, priority, false);
            }
        } else {
            console.error('Navigation failed:', data.error);
            speak(`Navigation error: ${data.error}`, 'high');
        }
    } catch (error) {
        console.error('========================================');
        console.error('NAVIGATION ERROR:', error);
        console.error('Error details:', {
            name: error.name,
            message: error.message,
            stack: error.stack
        });
        console.error('========================================');
    }
}

/**
 * Toggle navigation mode
 */
export async function togglePathfinding() {
    pathfindingEnabled = !pathfindingEnabled;
    const pathfindingBtn = document.getElementById('pathfindingBtn');

    if (pathfindingEnabled) {
        speak('Navigation mode enabled. Click on the video to set a destination', 'high');
        console.log('========================================');
        console.log('NAVIGATION MODE ENABLED');
        console.log('Click on canvas to set goal');
        console.log('========================================');
        if (pathfindingBtn) {
            pathfindingBtn.innerHTML = '🗺️ Disable Navigation';
            pathfindingBtn.classList.add('active');
        }
    } else {
        navigationGoal = null;
        navigationGuidance = null;
        stopNavigationLoop(); // Stop the continuous guidance loop

        // Reset navigation session on backend
        try {
            console.log('Resetting navigation session on backend...');
            const response = await fetch('/reset_navigation', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            if (response.ok) {
                const data = await response.json();
                console.log('Navigation session reset:', data.message);
            } else {
                console.error('Failed to reset navigation session:', response.statusText);
            }
        } catch (error) {
            console.error('Error resetting navigation session:', error);
        }

        speak('Navigation mode disabled', 'high');
        console.log('========================================');
        console.log('NAVIGATION MODE DISABLED');
        console.log('========================================');
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
