// timingConfig.js - Centralized timing configuration for all delays and intervals
// All timing values are in milliseconds

const TimingConfig = {
    // ===================================================================
    // DETECTION & CAMERA TIMING
    // ===================================================================
    detection: {
        // Main detection loop interval
        loopInterval: 300,  // How often to capture and send frames for detection

        // Request timeout
        requestTimeout: 200,  // Timeout for detection API requests

        // FPS counter update
        fpsUpdateInterval: 2000  // How often to update FPS statistics display
    },

    // ===================================================================
    // AUDIO & SPEECH TIMING
    // ===================================================================
    audio: {
        // Queue processing delay
        queueProcessDelay: 150,  // Delay between processing queued announcements

        // Test audio delay
        testAudioDelay: 2000  // Delay before fetching test audio
    },

    // ===================================================================
    // UI ANIMATIONS & EFFECTS
    // ===================================================================
    ui: {
        // Animation durations
        statsAnimationDuration: 200,  // Stats pulsing effect duration
        fpsAnimationDuration: 200,    // FPS pulsing effect duration
        realtimeStatsAnimationDuration: 200,  // Real-time stats animation
        detectionResultsFadeDelay: 200,  // Detection results fade transition

        // Status updates
        orientationStatusInterval: 3000  // Gyroscope status indicator update interval
    },

    // ===================================================================
    // COLLISION ALERTS & ANNOUNCEMENTS
    // ===================================================================
    collision: {
        // Alert intervals by severity
        defaultInterval: 3000,    // Default collision alert interval
        criticalInterval: 1000,   // High severity (CRITICAL threats)
        mediumInterval: 2000,     // Medium severity (approaching objects)
        lowInterval: 3500,        // Low severity (distant approaching)

        // Object announcement intervals by distance
        immediateAnnouncementInterval: 2000,  // CRITICAL immediate threats
        nearAnnouncementInterval: 4000,       // Close objects
        mediumAnnouncementInterval: 6000,     // Medium distance objects
        farAnnouncementInterval: 8000,        // Far objects (default)

        // Stationary object timing
        stationaryThreshold: 10000,    // Time before announcing stationary objects
        stationaryReannounce: 15000    // Time between re-announcements
    },

    // ===================================================================
    // VOICE COMMANDS & RECOGNITION
    // ===================================================================
    voice: {
        // Recognition restart delays
        errorRestartDelay: 1000,   // Delay to restart after error
        autoRestartDelay: 500,     // Delay when recognition ends

        // Initialization delays
        initDelay: 3000,           // Delay before initializing voice recognition
        activeMessageDelay: 5000,  // Delay for "voice commands active" announcement
        unsupportedMessageDelay: 5000  // Delay for browser compatibility message
    },

    // ===================================================================
    // MOBILE & GYROSCOPE INITIALIZATION
    // ===================================================================
    mobile: {
        // Gyroscope prompts and permissions
        gyroscopePromptDelay: 2000,        // Delay for mobile gyroscope permission prompt
        gyroscopePermissionAlertDelay: 1500,  // Delay before showing permission confirmation

        // Orientation indicators
        orientationIndicatorDelay: 1000,   // Delay to add orientation status indicator

        // Auto-start behavior
        detailsAutoHideDelay: 3000,        // Auto-hide project details on mobile
        autoStartDetectionDelay: 2000,     // Auto-start camera detection

        // Instructions
        desktopInstructionsDelay: 1500     // Desktop instruction audio delay
    },

    // ===================================================================
    // CANVAS & RENDERING
    // ===================================================================
    canvas: {
        // Note: Canvas clearing happens immediately on each frame
        // No delays for canvas operations - immediate rendering
        clearImmediate: true  // Flag indicating canvas clears without delay
    },

    // ===================================================================
    // TRACKING & OBJECT LIFECYCLE
    // ===================================================================
    tracking: {
        // Stale object threshold - time before removing disappeared objects
        staleThreshold: 3000  // 3 seconds - consistent across canvas and announcements
    }
};

// Freeze the configuration object to prevent accidental modifications
Object.freeze(TimingConfig);

// Export for ES6 modules
export default TimingConfig;

// Also attach to window for non-module usage
if (typeof window !== 'undefined') {
    window.TimingConfig = TimingConfig;
}
