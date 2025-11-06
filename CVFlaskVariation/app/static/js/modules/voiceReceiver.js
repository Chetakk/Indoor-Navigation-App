/**
 * Voice Receiver Module for Client
 * Receives and plays voice messages from dashboard operator
 */

import { speak, audioState } from './audio.js';

class VoiceReceiver {
    constructor() {
        this.isActive = false;
        this.isPlaying = false;
        this.pollInterval = null;
        this.lastSequence = -1;
        this.audioContext = null;
        this.audioQueue = [];
        this.currentSource = null;
        this.isProcessingQueue = false;

        console.log('VoiceReceiver initialized');
    }

    /**
     * Initialize audio context (requires user gesture)
     */
    async initAudioContext() {
        if (this.audioContext) {
            return true;
        }

        try {
            // Create audio context
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();

            // Resume if suspended (iOS requirement)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }

            console.log('AudioContext initialized:', this.audioContext.state);
            return true;

        } catch (error) {
            console.error('Failed to initialize AudioContext:', error);
            return false;
        }
    }

    /**
     * Start polling for voice chunks
     */
    async start() {
        if (this.isActive) {
            console.log('Voice receiver already active');
            return;
        }

        console.log('Starting voice receiver...');

        // Initialize audio context
        const audioReady = await this.initAudioContext();
        if (!audioReady) {
            console.error('Failed to initialize audio context');
            return;
        }

        this.isActive = true;
        this.lastSequence = -1;
        this.audioQueue = [];

        // Start polling for audio chunks (every 100ms for low latency)
        this.pollInterval = setInterval(() => {
            this.pollVoiceChunks();
        }, 100);

        console.log('Voice receiver started - polling every 100ms');
    }

    /**
     * Stop polling and cleanup
     */
    stop() {
        if (!this.isActive) {
            return;
        }

        console.log('Stopping voice receiver...');

        // Stop polling
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }

        // Stop current audio
        if (this.currentSource) {
            try {
                this.currentSource.stop();
            } catch (e) {
                // Ignore if already stopped
            }
            this.currentSource = null;
        }

        // Clear queue
        this.audioQueue = [];
        this.isActive = false;
        this.isPlaying = false;
        this.lastSequence = -1;

        console.log('Voice receiver stopped');
    }

    /**
     * Poll server for new voice chunks
     */
    async pollVoiceChunks() {
        try {
            const response = await fetch(`/client/voice/chunks?last_sequence=${this.lastSequence}`, {
                method: 'GET',
                cache: 'no-cache'
            });

            if (!response.ok) {
                console.error('Failed to poll voice chunks:', response.status);
                return;
            }

            const data = await response.json();

            if (data.success) {
                // Check if voice session is active
                if (!data.voice_session_active && this.isPlaying) {
                    console.log('Voice session ended by operator');
                    this.isPlaying = false;
                    this.hideVoiceIndicator();
                }

                // Process new chunks
                if (data.chunks && data.chunks.length > 0) {
                    console.log(`Received ${data.chunks.length} new audio chunks`);

                    for (const chunk of data.chunks) {
                        this.audioQueue.push(chunk);
                        this.lastSequence = Math.max(this.lastSequence, chunk.sequence);
                    }

                    // Show voice indicator
                    if (!this.isPlaying) {
                        this.isPlaying = true;
                        this.showVoiceIndicator();

                        // Pause TTS if speaking
                        if (audioState.isPlaying) {
                            audioState.speechSynth.cancel();
                            console.log('Paused TTS for voice message');
                        }
                    }

                    // Start processing queue if not already processing
                    if (!this.isProcessingQueue) {
                        this.processAudioQueue();
                    }
                }
            }

        } catch (error) {
            console.error('Error polling voice chunks:', error);
        }
    }

    /**
     * Process audio queue and play chunks
     */
    async processAudioQueue() {
        if (this.isProcessingQueue || this.audioQueue.length === 0) {
            return;
        }

        this.isProcessingQueue = true;

        while (this.audioQueue.length > 0) {
            const chunk = this.audioQueue.shift();

            try {
                await this.playAudioChunk(chunk.data);
            } catch (error) {
                console.error('Error playing audio chunk:', error);
            }
        }

        this.isProcessingQueue = false;

        // Hide indicator if queue is empty and no more chunks coming
        setTimeout(() => {
            if (this.audioQueue.length === 0 && this.isPlaying) {
                this.isPlaying = false;
                this.hideVoiceIndicator();
                console.log('Voice playback finished');
            }
        }, 500);
    }

    /**
     * Play a single audio chunk
     * @param {string} base64Audio - Base64 encoded audio data
     */
    async playAudioChunk(base64Audio) {
        return new Promise(async (resolve, reject) => {
            try {
                // Decode base64 to ArrayBuffer
                const binaryString = atob(base64Audio);
                const bytes = new Uint8Array(binaryString.length);
                for (let i = 0; i < binaryString.length; i++) {
                    bytes[i] = binaryString.charCodeAt(i);
                }

                // Decode audio data
                const audioBuffer = await this.audioContext.decodeAudioData(bytes.buffer);

                // Create audio source
                const source = this.audioContext.createBufferSource();
                source.buffer = audioBuffer;
                source.connect(this.audioContext.destination);

                // Track current source
                this.currentSource = source;

                // Play audio
                source.onended = () => {
                    this.currentSource = null;
                    resolve();
                };

                source.start(0);

            } catch (error) {
                console.error('Error playing audio chunk:', error);
                reject(error);
            }
        });
    }

    /**
     * Show voice indicator UI
     */
    showVoiceIndicator() {
        const indicator = document.getElementById('voiceIndicator');
        if (indicator) {
            indicator.style.display = 'flex';
        }
        console.log('Voice indicator shown');
    }

    /**
     * Hide voice indicator UI
     */
    hideVoiceIndicator() {
        const indicator = document.getElementById('voiceIndicator');
        if (indicator) {
            indicator.style.display = 'none';
        }
        console.log('Voice indicator hidden');
    }
}

// Export singleton instance
export default VoiceReceiver;
