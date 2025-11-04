/**
 * Audio Module
 * Handles text-to-speech, audio announcements, and priority queue management
 */

import TimingConfig from './timingConfig.js';

// Audio state
export const audioState = {
    enabled: true,
    queue: [],
    isPlaying: false,
    speechSynth: window.speechSynthesis,
    lastAnnouncement: {},
    MAX_QUEUE_SIZE: 1
};

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
        speak('Audio announcements enabled', 'high');
    } else {
        audioBtn.textContent = '🔇 Audio OFF';
        audioStatus.textContent = '🔇';
        audioState.speechSynth.cancel();
        audioState.queue = [];
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
 * Enhanced speech function with better error handling and queue management
 */
export function speak(text, priority = 'normal') {
    console.log('Attempting to speak:', text, 'Priority:', priority, 'Audio enabled:', audioState.enabled);

    if (!audioState.enabled) {
        console.log('Audio disabled, not speaking');
        return;
    }

    if (!audioState.speechSynth) {
        console.error('Speech synthesis not available');
        return;
    }

    // Check if already speaking
    const isSpeaking = audioState.speechSynth.speaking || audioState.speechSynth.pending;

    // For critical priority, interrupt immediately
    if (priority === 'critical' && isSpeaking) {
        console.log('Critical priority message - cancelling all speech');
        audioState.speechSynth.cancel();
        audioState.queue = [];
        speakImmediate(text, priority);
        return;
    }

    // Cancel current speech only if high priority
    if (priority === 'high' && isSpeaking) {
        console.log('High priority message - cancelling current speech');
        audioState.speechSynth.cancel();
        speakImmediate(text, priority);
        return;
    }

    // Don't speak if already speaking and normal/low priority - queue instead
    if (isSpeaking && (priority === 'normal' || priority === 'low')) {
        console.log('Already speaking, queueing message:', text);
        queueAnnouncement(text, priority);
        return;
    }

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

    // Event handlers
    audioState.isPlaying = true;
    utterance.onstart = () => console.log('🔊 Speech started:', text);
    utterance.onend = () => {
        console.log('✅ Speech ended:', text);
        audioState.isPlaying = false;
        // Process next in queue
        setTimeout(() => processAudioQueue(), TimingConfig.audio.queueProcessDelay);
    };
    utterance.onerror = (event) => {
        console.error('❌ Speech error:', event);
        audioState.isPlaying = false;
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
