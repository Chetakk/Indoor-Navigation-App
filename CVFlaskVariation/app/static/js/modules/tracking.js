/**
 * Tracking Module
 * Handles object tracking state, colors, and helper functions
 */

// Tracking variables
export let trackingEnabled = true;
export const trackedObjects = new Map(); // Store tracked objects by ID
export const trackColors = {}; // Store colors for each track ID
export const trackFirstSeen = new Map(); // Track when each object was first detected
export const trackLastMovement = new Map(); // Track last movement state for each object

/**
 * Get a consistent color for a track ID
 * @param {number|string} trackId - Track ID
 * @returns {string} RGB color string
 */
export function getTrackColor(trackId) {
    if (!trackColors[trackId]) {
        // Generate a consistent color based on track ID
        const hue = (trackId * 137.5) % 360; // Golden angle for color distribution
        trackColors[trackId] = `hsl(${hue}, 70%, 50%)`;
    }
    return trackColors[trackId];
}

/**
 * Set tracking enabled state
 * @param {boolean} enabled
 */
export function setTrackingEnabled(enabled) {
    trackingEnabled = enabled;
}

/**
 * Clear all tracking data
 */
export function clearTrackingData() {
    trackedObjects.clear();
    Object.keys(trackColors).forEach(key => delete trackColors[key]);
    trackFirstSeen.clear();
    trackLastMovement.clear();
    console.log('✅ Cleared all tracking data');
}

/**
 * Clean up stale track colors (for objects no longer tracked)
 * @param {Set<number|string>} currentTrackIds - Set of currently active track IDs
 */
export function cleanupStaleTrackColors(currentTrackIds) {
    Object.keys(trackColors).forEach(trackId => {
        if (!currentTrackIds.has(parseInt(trackId)) && !currentTrackIds.has(trackId)) {
            delete trackColors[trackId];
            console.log(`Cleaned up stale track color for ID ${trackId}`);
        }
    });
}
