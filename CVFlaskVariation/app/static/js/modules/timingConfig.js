// timingConfig.js - Centralized timing configuration for all delays and intervals
// All timing values are in milliseconds
//
// OPTIMIZED FOR 12MS REAL-TIME INFERENCE (7ms model + 5ms overhead)
// TensorRT-accelerated YOLOv8 achieves ~12ms total prediction time
// Previous system was designed for 70-160ms predictions
// New timing enables true real-time blind navigation assistance

const TimingConfig = {
    // ===================================================================
    // DETECTION & CAMERA TIMING - OPTIMIZED FOR 12MS INFERENCE
    // ===================================================================
    detection: {
        // Main detection loop interval - DOUBLED frame rate for real-time performance
        loopInterval: 150,  // OPTIMIZED: 150ms (was 300ms) - Process 2x more frames with 12ms inference
                           // Achieves ~6-7 FPS instead of 3-4 FPS
                           // Enables faster hazard detection for blind navigation

        // Request timeout - Increased to handle depth model initialization on first request
        requestTimeout: 3000,  // Timeout for detection API requests (handles initial depth model load ~1.2s + processing)

        // FPS counter update
        fpsUpdateInterval: 2000  // How often to update FPS statistics display
    },

    // ===================================================================
    // AUDIO & SPEECH TIMING - OPTIMIZED FOR REAL-TIME RESPONSIVENESS
    // ===================================================================
    audio: {
        // Queue processing delay - FASTER for real-time audio feedback
        queueProcessDelay: 100,  // OPTIMIZED: 100ms (was 150ms) - Faster queue processing

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
    // COLLISION ALERTS & ANNOUNCEMENTS - OPTIMIZED FOR 12MS REAL-TIME
    // ===================================================================
    collision: {
        // Alert intervals by severity - ANTI-SPAM TUNED for low req-res times
        defaultInterval: 2000,    // OPTIMIZED: 2000ms (was 3000ms) - Faster default alerts
        criticalInterval: 2000,   // INCREASED: 2000ms (was 500ms) - Prevents "danger" spam with fast inference
        mediumInterval: 2500,     // INCREASED: 2500ms (was 1500ms) - Reduces approaching object spam
        lowInterval: 3000,        // INCREASED: 3000ms (was 2500ms) - Reduces distant warning spam

        // Object announcement intervals by distance - ANTI-SPAM TUNED
        immediateAnnouncementInterval: 2000,  // INCREASED: 2000ms (was 1000ms) - Prevents immediate threat spam
        nearAnnouncementInterval: 3000,       // INCREASED: 3000ms (was 2000ms) - Reduces close object spam
        mediumAnnouncementInterval: 5000,     // INCREASED: 5000ms (was 4000ms) - Balanced medium distance updates
        farAnnouncementInterval: 7000,        // INCREASED: 7000ms (was 6000ms) - Reduces far object spam

        // Stationary object timing - FASTER cleanup and re-announcement
        stationaryThreshold: 10000,    // Time before announcing stationary objects (unchanged - good balance)
        stationaryReannounce: 15000    // Time between re-announcements (unchanged - prevents audio clutter)
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
    // TRACKING & OBJECT LIFECYCLE - OPTIMIZED FOR 12MS REAL-TIME
    // ===================================================================
    tracking: {
        // Stale object threshold - REDUCED for faster cleanup with real-time detection
        staleThreshold: 1500  // OPTIMIZED: 1500ms (was 3000ms) - Faster stale object cleanup
                             // With 12ms inference and 150ms loop, objects disappear faster
                             // Prevents announcing objects that have already moved away
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
