/**
 * Audio Module
 * Handles text-to-speech, audio announcements, and priority queue management
 */

import TimingConfig from './timingConfig.js';

// Audio state with intelligent state machine
export const audioState = {
    enabled: true,
    queue: [],
    isPlaying: false,
    speechSynth: window.speechSynthesis,
    lastAnnouncement: {},
    MAX_QUEUE_SIZE: 1,
    // Audio state machine for smart interrupts
    currentState: 'IDLE', // IDLE, SPEAKING_CRITICAL, SPEAKING_HIGH, SPEAKING_NORMAL, SPEAKING_LOW
    currentPriority: null,
    currentText: null,
    // Critical warning cooldown - prevents multi-object spam
    lastCriticalWarningTime: 0,
    CRITICAL_COOLDOWN_MS: 3000,  // INCREASED: 3 seconds (was 1.5s) - prevents danger spam with low req-res times
    // Global rate limiter - prevents ANY audio spam regardless of priority
    lastAnySpeechTime: 0,
    MIN_SPEECH_INTERVAL_MS: 800  // MINIMUM 800ms between ANY speech - prevents overwhelming audio flood
};

/**
 * Determine if new audio should interrupt currently playing audio
 * Based on priority hierarchy and state machine
 * @param {string} newPriority - Priority of new announcement
 * @param {boolean} isCriticalSceneChange - Whether this is a critical scene change
 * @param {string} newText - Text of new announcement (to check for duplicates)
 * @returns {boolean} True if should interrupt
 */
export function shouldInterruptAudio(newPriority, isCriticalSceneChange = false, newText = '') {
    // If not playing, no interrupt needed
    if (!audioState.isPlaying || audioState.currentState === 'IDLE') {
        return false; // Not interrupting, just proceed normally
    }

    const currentPriority = audioState.currentPriority;
    const currentText = audioState.currentText;

    // CRITICAL FIX: Never interrupt if we're saying the same thing
    // This prevents "Danger! Danger! Danger!" spam without actually hearing what the danger is
    if (newText && currentText && newText === currentText) {
        console.log('NO INTERRUPT: Same message already being spoken');
        return false;
    }

    // CRITICAL FIX: Multi-object spam prevention with cooldown
    // If currently speaking critical warning, don't interrupt with another critical for 1.5 seconds
    // This prevents "Danger! person..." -> "Danger! car..." -> "Danger! person..." spam
    if (newPriority === 'critical' && currentPriority === 'critical') {
        const now = Date.now();
        const timeSinceCriticalStarted = now - audioState.lastCriticalWarningTime;

        if (timeSinceCriticalStarted < audioState.CRITICAL_COOLDOWN_MS) {
            console.log(`NO INTERRUPT: Critical cooldown active (${timeSinceCriticalStarted}ms / ${audioState.CRITICAL_COOLDOWN_MS}ms) - queuing instead`);
            return false; // Queue the new critical warning instead of interrupting
        }
    }

    // CRITICAL FIX: Check if same warning about same object (fuzzy match)
    // e.g., "Danger! person approaching" vs "Danger! person approaching"
    if (newText && currentText && newPriority === 'critical' && currentPriority === 'critical') {
        // Extract object name from warning message
        const extractObject = (text) => {
            const match = text.match(/(?:Danger|Warning|Caution)!\s+(\w+)/i);
            return match ? match[1] : null;
        };

        const newObject = extractObject(newText);
        const currentObject = extractObject(currentText);

        if (newObject && currentObject && newObject === currentObject) {
            console.log(`NO INTERRUPT: Already warning about same object (${currentObject})`);
            return false;
        }
    }

    // Priority hierarchy (higher number = higher priority)
    const priorityLevels = {
        'low': 1,
        'normal': 2,
        'high': 3,
        'critical': 4
    };

    const currentLevel = priorityLevels[currentPriority] || 0;
    const newLevel = priorityLevels[newPriority] || 0;

    // ALWAYS interrupt for critical scene changes (new hazards, collisions)
    // BUT only if it's a DIFFERENT object/warning
    if (isCriticalSceneChange && newPriority === 'critical') {
        console.log('INTERRUPT: Critical scene change detected (new object)');
        return true;
    }

    // Critical priority interrupts LOWER priority (but not same critical)
    if (newPriority === 'critical' && currentPriority !== 'critical') {
        console.log('INTERRUPT: Critical priority overrides lower priority audio');
        return true;
    }

    // High priority interrupts normal and low
    if (newPriority === 'high' && (currentPriority === 'normal' || currentPriority === 'low')) {
        console.log('INTERRUPT: High priority overrides lower priority audio');
        return true;
    }

    // Same or lower priority does NOT interrupt - queue instead
    if (newLevel <= currentLevel) {
        console.log(`NO INTERRUPT: ${newPriority} (${newLevel}) does not interrupt ${currentPriority} (${currentLevel})`);
        return false;
    }

    return false;
}

/**
 * Toggle audio on/off
 */
export function toggleAudio() {
    audioState.enabled = !audioState.enabled;
    const audioBtn = document.getElementById('audioBtnText');
    const audioStatus = document.getElementById('audioStatus');

    if (audioState.enabled) {
        audioBtn.textContent = '🔊 Audio ON';
        audioStatus.textContent = '🔊';
        speak('Audio announcements enabled', 'high', false);
    } else {
        audioBtn.textContent = '🔇 Audio OFF';
        audioStatus.textContent = '🔇';
        audioState.speechSynth.cancel();
        audioState.queue = [];
        audioState.currentState = 'IDLE';
        audioState.currentPriority = null;
    }

    console.log('Audio enabled:', audioState.enabled);
}

/**
 * Queue announcement with FIFO overwrite (circular buffer)
 * New information is prioritized - oldest items are removed when full
 */
export function queueAnnouncement(text, priority = 'normal') {
    console.log('Queuing announcement:', text, 'Priority:', priority);

    // Limit queue size - just remove oldest item (FIFO)
    if (audioState.queue.length >= audioState.MAX_QUEUE_SIZE) {
        const removed = audioState.queue.shift(); // Remove oldest item
        console.log('Queue full - removed oldest item:', removed.text);
    }

    audioState.queue.push({ text, priority, timestamp: Date.now() });
    processAudioQueue();
}

/**
 * Clear the audio queue
 * Used when new detection response arrives to prevent stale announcements
 */
export function clearAudioQueue() {
    const queueSize = audioState.queue.length;
    if (queueSize > 0) {
        console.log(`Clearing audio queue (${queueSize} items) for fresh detections`);
        audioState.queue = [];
    }
}

/**
 * Process audio queue with priority handling
 */
function processAudioQueue() {
    if (!audioState.enabled || audioState.isPlaying || audioState.queue.length === 0) {
        return;
    }

    // Sort by priority: critical > high > normal > low
    const priorityOrder = { critical: 0, high: 1, normal: 2, low: 3 };
    audioState.queue.sort((a, b) => priorityOrder[a.priority] - priorityOrder[b.priority]);

    // Get highest priority announcement
    const announcement = audioState.queue.shift();

    // If it's critical, clear the queue and speak immediately
    if (announcement.priority === 'critical') {
        audioState.queue = [];
        audioState.speechSynth.cancel();
    }

    speakImmediate(announcement.text, announcement.priority);
}

/**
 * Enhanced speech function with state machine and smart interrupt logic
 * @param {string} text - Text to speak
 * @param {string} priority - Priority level (critical, high, normal, low)
 * @param {boolean} isCriticalSceneChange - Whether this represents a critical scene change
 */
export function speak(text, priority = 'normal', isCriticalSceneChange = false) {
    console.log('Attempting to speak:', text, 'Priority:', priority, 'Critical scene change:', isCriticalSceneChange);

    if (!audioState.enabled) {
        console.log('Audio disabled, not speaking');
        return;
    }

    if (!audioState.speechSynth) {
        console.error('Speech synthesis not available');
        return;
    }

    // GLOBAL RATE LIMITER: Prevent audio spam regardless of priority
    const now = Date.now();
    const timeSinceLastSpeech = now - audioState.lastAnySpeechTime;

    if (timeSinceLastSpeech < audioState.MIN_SPEECH_INTERVAL_MS) {
        console.log(`RATE LIMITED: Only ${timeSinceLastSpeech}ms since last speech (min: ${audioState.MIN_SPEECH_INTERVAL_MS}ms) - queuing instead`);
        queueAnnouncement(text, priority);
        return;
    }

    // Check if already speaking
    const isSpeaking = audioState.speechSynth.speaking || audioState.speechSynth.pending;

    // Use state machine to determine if we should interrupt
    if (isSpeaking) {
        const shouldInterrupt = shouldInterruptAudio(priority, isCriticalSceneChange, text);

        if (shouldInterrupt) {
            console.log(`INTERRUPTING: ${priority} message interrupting ${audioState.currentPriority}`);
            audioState.speechSynth.cancel();
            audioState.queue = [];
            speakImmediate(text, priority);
            return;
        } else {
            // Don't interrupt - queue instead
            console.log(`QUEUEING: ${priority} message queued (not interrupting ${audioState.currentPriority})`);
            queueAnnouncement(text, priority);
            return;
        }
    }

    // Not speaking, proceed immediately
    speakImmediate(text, priority);
}

/**
 * Immediate speech function (internal use)
 */
function speakImmediate(text, priority) {
    const utterance = new SpeechSynthesisUtterance(text);

    // Adjust speech rate based on priority for blind navigation
    if (priority === 'critical') {
        utterance.rate = 1.2; // Fastest for CRITICAL warnings
        utterance.volume = 1.0; // Maximum volume for safety
    } else if (priority === 'high') {
        utterance.rate = 1.1; // Faster for urgent warnings
        utterance.volume = 1.0; // Maximum volume for safety
    } else {
        utterance.rate = 0.95; // Normal pace for informational
        utterance.volume = 0.9;
    }

    utterance.pitch = 1;

    // Update state machine
    audioState.isPlaying = true;
    audioState.currentPriority = priority;
    audioState.currentText = text;
    audioState.currentState = `SPEAKING_${priority.toUpperCase()}`;

    // Track speech timing for rate limiting
    const now = Date.now();
    audioState.lastAnySpeechTime = now;

    // Track when critical warnings start for cooldown management
    if (priority === 'critical') {
        audioState.lastCriticalWarningTime = now;
    }

    // Event handlers
    utterance.onstart = () => {
        console.log(`🔊 Speech started [${priority}]:`, text);
        console.log(`State: ${audioState.currentState}`);
    };

    utterance.onend = () => {
        console.log('✅ Speech ended:', text);
        audioState.isPlaying = false;
        audioState.currentPriority = null;
        audioState.currentText = null;
        audioState.currentState = 'IDLE';

        // Process next in queue
        setTimeout(() => processAudioQueue(), TimingConfig.audio.queueProcessDelay);
    };

    utterance.onerror = (event) => {
        console.error('❌ Speech error:', event);
        audioState.isPlaying = false;
        audioState.currentPriority = null;
        audioState.currentText = null;
        audioState.currentState = 'IDLE';
        processAudioQueue();
    };

    // Try to use a clear voice
    const voices = audioState.speechSynth.getVoices();

    if (voices.length > 0) {
        const preferredVoice = voices.find(voice =>
            voice.lang.startsWith('en') &&
            (voice.name.includes('Google') || voice.name.includes('Microsoft') || voice.name.includes('Samantha'))
        ) || voices[0];

        if (preferredVoice) {
            utterance.voice = preferredVoice;
            console.log('Using voice:', preferredVoice.name);
        }
    }

    try {
        audioState.speechSynth.speak(utterance);
        console.log('✅ Speech synthesis started');
    } catch (error) {
        console.error('❌ Error starting speech:', error);
        audioState.isPlaying = false;
    }
}

/**
 * Test audio system
 */
export function testAudio() {
    console.log('Testing audio with direction...');
    console.log('Speech synthesis available:', !!audioState.speechSynth);
    console.log('Audio enabled:', audioState.enabled);

    if (!audioState.speechSynth) {
        alert('Speech synthesis not supported in this browser');
        return;
    }

    // Test basic speech with direction
    speak('Audio test: person very close to your left', 'high');

    // Test with sample detection data
    setTimeout(() => {
        fetch('/test_audio')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    console.log('Test detection data:', data.detections);
                    // This will be handled by the detection module
                    if (window.announceDetections) {
                        window.announceDetections(data.detections);
                    }
                }
            })
            .catch(error => {
                console.error('Test audio error:', error);
            });
    }, TimingConfig.audio.testAudioDelay);
}
