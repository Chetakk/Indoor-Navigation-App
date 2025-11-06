/**
 * Voice Communication Module for Dashboard
 * Handles microphone capture and real-time audio streaming to cameras
 */

class VoiceComm {
    constructor() {
        this.mediaRecorder = null;
        this.audioStream = null;
        this.isRecording = false;
        this.isBroadcasting = false;
        this.targetCameraId = null;
        this.targetCameraName = null;
        this.audioChunks = [];
        this.sequenceNumber = 0;
        this.uploadInterval = null;

        // Recording settings - WebM with Opus codec for efficient voice transmission
        this.mimeType = this.getSupportedMimeType();
        this.chunkDuration = 200; // milliseconds - balance between latency and overhead

        console.log('VoiceComm initialized with mime type:', this.mimeType);
    }

    /**
     * Get supported MIME type for audio recording
     * Prefers WebM with Opus codec for best compression and quality
     */
    getSupportedMimeType() {
        const types = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/mp4',
            'audio/mpeg'
        ];

        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                return type;
            }
        }

        console.warn('No optimal audio format supported, using default');
        return '';
    }

    /**
     * Request microphone permission and start voice session
     * @param {string} cameraId - Target camera ID (null for broadcast)
     * @param {string} cameraName - Target camera name
     */
    async startVoiceSession(cameraId = null, cameraName = null) {
        try {
            console.log('Starting voice session...', cameraId ? `to ${cameraName}` : 'broadcast');

            // Check if already recording
            if (this.isRecording) {
                console.warn('Already recording');
                return { success: false, error: 'Already recording' };
            }

            // Request microphone access
            this.audioStream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true,
                    sampleRate: 48000
                }
            });

            console.log('Microphone access granted');

            // Set target
            this.targetCameraId = cameraId;
            this.targetCameraName = cameraName;
            this.isBroadcasting = (cameraId === null);

            // Initialize MediaRecorder
            const options = this.mimeType ? { mimeType: this.mimeType } : {};
            this.mediaRecorder = new MediaRecorder(this.audioStream, options);
            this.sequenceNumber = 0;
            this.audioChunks = [];

            // Handle data available event - this fires periodically
            this.mediaRecorder.ondataavailable = async (event) => {
                if (event.data && event.data.size > 0) {
                    console.log(`Audio chunk received: ${event.data.size} bytes`);
                    this.audioChunks.push(event.data);

                    // Send chunk immediately for low latency
                    await this.sendAudioChunk(event.data);
                }
            };

            this.mediaRecorder.onstart = () => {
                console.log('MediaRecorder started');
                this.isRecording = true;
            };

            this.mediaRecorder.onstop = () => {
                console.log('MediaRecorder stopped');
                this.isRecording = false;
            };

            this.mediaRecorder.onerror = (event) => {
                console.error('MediaRecorder error:', event.error);
            };

            // Notify server to start voice session
            const endpoint = this.isBroadcasting
                ? '/admin/cameras/broadcast/voice/start'
                : `/admin/cameras/${cameraId}/voice/start`;

            const response = await fetch(endpoint, { method: 'POST' });
            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Failed to start voice session on server');
            }

            // Start recording with timeslice for regular chunk delivery
            this.mediaRecorder.start(this.chunkDuration);
            console.log('Recording started with', this.chunkDuration, 'ms chunks');

            return { success: true, message: 'Voice session started' };

        } catch (error) {
            console.error('Error starting voice session:', error);
            this.cleanup();
            return { success: false, error: error.message };
        }
    }

    /**
     * Send audio chunk to server
     * @param {Blob} audioBlob - Audio data blob
     */
    async sendAudioChunk(audioBlob) {
        try {
            // Convert blob to base64
            const base64Audio = await this.blobToBase64(audioBlob);

            // Prepare endpoint
            const endpoint = this.isBroadcasting
                ? '/admin/cameras/broadcast/voice/chunk'
                : `/admin/cameras/${this.targetCameraId}/voice/chunk`;

            // Send to server
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    audio: base64Audio,
                    sequence: this.sequenceNumber
                })
            });

            const data = await response.json();

            if (data.success) {
                console.log(`Chunk ${this.sequenceNumber} sent successfully (queue: ${data.queue_length || data.recipients})`);
                this.sequenceNumber++;
            } else {
                console.error('Failed to send chunk:', data.error);
            }

        } catch (error) {
            console.error('Error sending audio chunk:', error);
        }
    }

    /**
     * Convert Blob to base64 string
     * @param {Blob} blob - Audio blob
     * @returns {Promise<string>} Base64 encoded string
     */
    blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => {
                // Extract base64 data (remove data:audio/...;base64, prefix)
                const base64 = reader.result.split(',')[1];
                resolve(base64);
            };
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }

    /**
     * Stop voice session
     */
    async stopVoiceSession() {
        try {
            console.log('Stopping voice session...');

            // Stop MediaRecorder
            if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                this.mediaRecorder.stop();
            }

            // Notify server to stop voice session
            const endpoint = this.isBroadcasting
                ? '/admin/cameras/broadcast/voice/stop'
                : `/admin/cameras/${this.targetCameraId}/voice/stop`;

            const response = await fetch(endpoint, { method: 'POST' });
            const data = await response.json();

            if (!data.success) {
                console.error('Failed to stop voice session on server:', data.error);
            }

            // Cleanup
            this.cleanup();

            return { success: true, message: 'Voice session stopped' };

        } catch (error) {
            console.error('Error stopping voice session:', error);
            this.cleanup();
            return { success: false, error: error.message };
        }
    }

    /**
     * Cleanup resources
     */
    cleanup() {
        // Stop all audio tracks
        if (this.audioStream) {
            this.audioStream.getTracks().forEach(track => track.stop());
            this.audioStream = null;
        }

        // Clear recorder
        this.mediaRecorder = null;
        this.isRecording = false;
        this.isBroadcasting = false;
        this.targetCameraId = null;
        this.targetCameraName = null;
        this.audioChunks = [];
        this.sequenceNumber = 0;

        console.log('VoiceComm cleaned up');
    }

    /**
     * Get current recording status
     */
    getStatus() {
        return {
            isRecording: this.isRecording,
            isBroadcasting: this.isBroadcasting,
            targetCameraId: this.targetCameraId,
            targetCameraName: this.targetCameraName,
            sequenceNumber: this.sequenceNumber,
            chunksSent: this.sequenceNumber
        };
    }
}

// Export for use in other modules
export default VoiceComm;
