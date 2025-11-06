# Voice Call Troubleshooting Guide

## Overview
The voice call system allows dashboard operators to speak directly to client cameras in real-time. This document explains how to diagnose and fix voice call issues.

## System Architecture

### Components
1. **Dashboard (Sender)**
   - File: `app/static/js/modules/voiceComm.js`
   - Captures microphone audio
   - Encodes to WebM/Opus format
   - Sends 200ms chunks to server

2. **Client (Receiver)**
   - File: `app/static/js/modules/voiceReceiver.js`
   - Polls server every 100ms for new audio chunks
   - Decodes and plays audio via Web Audio API

3. **Backend**
   - Routes: `app/routes/cameras.py` (dashboard endpoints)
   - Routes: `app/routes/client.py` (client polling endpoint)
   - Registry: `app/services/camera_registry.py` (manages audio queues)

### Data Flow
```
Dashboard Microphone
  |
  v
MediaRecorder (200ms chunks)
  |
  v
Base64 encoding
  |
  v
POST /admin/cameras/{id}/voice/chunk
  |
  v
Camera Registry (audio_chunks_queue)
  |
  v
GET /client/voice/chunks (polling every 100ms)
  |
  v
Base64 decoding
  |
  v
Web Audio API playback
  |
  v
Client Speaker
```

## Common Issues and Solutions

### Issue 1: "Microphone Permission Denied"

**Symptoms:**
- Alert shows "Microphone permission denied"
- Voice call button does nothing
- Console shows `NotAllowedError` or `PermissionDeniedError`

**Root Causes:**
1. HTTPS not enabled (browsers require HTTPS for microphone access)
2. User denied permission in browser prompt
3. Browser settings block microphone access
4. Operating system denied microphone permission

**Solutions:**

**A. Enable HTTPS (Required)**
```bash
# Check if SSL is enabled in config.py
USE_SSL = True
SSL_CERT = 'cert.pem'
SSL_KEY = 'key.pem'

# Generate self-signed certificate if needed
openssl req -x509 -newkey rsa:4096 -nodes \
  -keyout key.pem -out cert.pem -days 365
```

**B. Browser Settings**
- Chrome: chrome://settings/content/microphone
- Firefox: about:preferences#privacy
- Edge: edge://settings/content/microphone

Check that:
1. Microphone is not blocked globally
2. Site has permission to use microphone
3. Correct microphone is selected

**C. Test Microphone**
1. Go to `/admin/voice-test` page
2. Click "Start Microphone" button
3. Check system requirements section
4. Review test log for specific errors

### Issue 2: "No Audio Received on Client"

**Symptoms:**
- Dashboard shows "recording and transmitting"
- Client voice indicator never appears
- No audio plays on client device

**Root Causes:**
1. Client session not registered
2. Voice receiver not started
3. Network connectivity issues
4. Audio chunks not reaching server

**Solutions:**

**A. Verify Session Registration**
```javascript
// Check browser console on client page
// Should see:
"Client session registered: <camera_id>"
"Voice receiver active - ready for voice messages"
```

If not registered:
```javascript
// Manually trigger registration
registerClientSession();
```

**B. Check Network Connectivity**
```bash
# From client machine, test endpoints
curl -k https://192.168.1.14:5000/client/voice/chunks?last_sequence=-1

# Should return:
# {"success": true, "voice_session_active": false, "chunks": []}
```

**C. Verify Audio Queue**
```javascript
// Check server logs for:
"Voice session started for camera <id>"
"Audio chunk uploaded"

// If no logs, check dashboard console for send errors
```

**D. Test with Voice Test Page**
1. Open `/admin/voice-test` on both dashboard and client
2. Register session on both
3. Start receiver on client
4. Start transmitter on dashboard
5. Monitor test log for detailed errors

### Issue 3: "Audio Choppy or Distorted"

**Symptoms:**
- Audio plays but sounds robotic or choppy
- Frequent gaps or stuttering
- Echo or feedback

**Root Causes:**
1. Network latency or packet loss
2. CPU overload on client or server
3. Audio chunk size mismatch
4. Echo cancellation not working

**Solutions:**

**A. Adjust Chunk Duration**
```javascript
// In voiceComm.js, line 20
this.chunkDuration = 200; // Try 300 or 400 for slower networks
```

**B. Check Network Quality**
```bash
# Test latency
ping -n 10 192.168.1.14

# Acceptable: < 50ms
# Warning: 50-100ms (may cause stuttering)
# Poor: > 100ms (adjust chunk duration)
```

**C. Reduce CPU Load**
```python
# In config.py, consider switching to smaller model
MODEL_PATH = 'yolov8n-oiv7.engine'  # Instead of yolov8x
```

**D. Enable Echo Cancellation**
```javascript
// In voiceComm.js, verify settings (already enabled)
audio: {
    echoCancellation: true,
    noiseSuppression: true,
    autoGainControl: true,
}
```

### Issue 4: "Server Crashes or Hangs"

**Symptoms:**
- Server becomes unresponsive during voice call
- High memory usage
- Connection timeouts

**Root Causes:**
1. Audio queue overflow
2. Memory leak in audio buffering
3. Too many concurrent voice sessions

**Solutions:**

**A. Check Audio Queue Size**
```python
# In camera_registry.py, queue is limited to 50 chunks
# At 200ms per chunk = 10 seconds max buffer

# If issues persist, reduce limit:
if len(self.audio_chunks_queue) > 30:  # Reduce from 50
    self.audio_chunks_queue.pop(0)
```

**B. Monitor Memory Usage**
```bash
# Check dashboard at /admin/dashboard
# Monitor Memory section
# Voice sessions should use < 1MB each
```

**C. Implement Voice Session Timeout**
```python
# Already implemented in camera_registry.py
# Sessions auto-close after 10 seconds of inactivity
# Adjust if needed in stop_voice_session()
```

### Issue 5: "Voice Call Works in Chrome but Not Firefox/Safari"

**Symptoms:**
- Feature works in one browser but fails in others
- Different error messages across browsers

**Root Causes:**
1. MediaRecorder API differences
2. Codec support varies by browser
3. Web Audio API implementations differ

**Solutions:**

**A. Check Codec Support**
```javascript
// In voiceComm.js, getSupportedMimeType() tries:
1. audio/webm;codecs=opus (Chrome, Edge, Firefox)
2. audio/webm (fallback)
3. audio/ogg;codecs=opus (Firefox alternative)
4. audio/mp4 (Safari)
```

**B. Test on Voice Test Page**
- System requirements section shows codec support
- Try different browsers and note which codecs work

**C. Firefox-Specific Fix**
```javascript
// If Firefox shows "NotSupportedError", try:
const options = {
    mimeType: 'audio/ogg;codecs=opus',
    audioBitsPerSecond: 32000
};
```

**D. Safari Workarounds**
```javascript
// Safari requires user interaction before audio
// Voice receiver initialization delayed until:
// 1. User clicks button, or
// 2. Page receives first user gesture
```

## Testing Procedures

### Quick Test (2 minutes)
1. Open `/admin/voice-test` in browser
2. Check all system requirements are green
3. Click "Register Client Session"
4. Click "Start Voice Receiver"
5. Click "Start Microphone" (grant permission)
6. Speak into microphone
7. Verify "Chunks sent" counter increases
8. Verify "Chunks received" counter increases
9. Verify audio plays back

### Full Integration Test (5 minutes)
1. Open client page (main index) on device/browser A
2. Open dashboard page on device/browser B
3. Verify client shows "Voice receiver active" in console
4. On dashboard, find camera in list
5. Click "Call" button on camera card
6. Grant microphone permission
7. Speak test message
8. Verify voice indicator appears on client
9. Verify audio plays on client
10. Click "Hang Up" on dashboard
11. Verify voice indicator disappears on client

### Network Test (10 minutes)
1. Test on same machine (localhost) - should work
2. Test on same WiFi network - should work
3. Test on different networks (VPN/mobile hotspot)
4. Measure latency and adjust chunk duration
5. Test with network throttling (Chrome DevTools)

## Diagnostic Endpoints

### Check Session Registration
```bash
GET https://192.168.1.14:5000/admin/cameras/list

# Response should include your camera with:
{
  "camera_id": "...",
  "voice_session_active": true/false,
  "last_audio_chunk_time": timestamp
}
```

### Check Audio Queue
```bash
GET https://192.168.1.14:5000/client/voice/chunks?last_sequence=-1

# Response:
{
  "success": true,
  "voice_session_active": true,
  "chunks": [
    {"data": "base64...", "sequence": 0, "timestamp": ...},
    ...
  ],
  "chunk_count": N
}
```

### Server Health
```bash
GET https://192.168.1.14:5000/admin/metrics

# Check:
# - CPU usage (should be < 80%)
# - Memory usage (should be < 90%)
# - GPU usage (if enabled)
```

## Configuration Reference

### config.py Settings
```python
# Voice communication is always enabled
# No specific config flags needed

# But ensure these are set:
USE_SSL = True  # Required for microphone access
HOST = '192.168.1.14'  # Your server IP
PORT = 5000
```

### Timing Configuration
```javascript
// voiceComm.js
chunkDuration = 200  // ms between chunks

// voiceReceiver.js
pollInterval = 100  // ms between server polls

// Adjust for network:
// - Fast LAN: 100/200 (default)
// - WiFi: 150/300
// - Slow network: 200/400
```

## Browser Console Commands

### Dashboard (Sender)
```javascript
// Check voice comm status
voiceComm.getStatus()

// Manually start voice session
voiceComm.startVoiceSession(cameraId, cameraName)

// Stop voice session
voiceComm.stopVoiceSession()

// Check if recording
voiceComm.isRecording
```

### Client (Receiver)
```javascript
// Check receiver status
voiceReceiver.isActive
voiceReceiver.isPlaying

// Manually start receiver
voiceReceiver.start()

// Stop receiver
voiceReceiver.stop()

// Check last sequence
voiceReceiver.lastSequence
```

## Known Limitations

1. **One-way communication**: Dashboard → Client only (no client-to-dashboard)
2. **No recording**: Audio is not saved on server
3. **Memory limit**: Maximum 50 chunks (10 seconds) buffered per camera
4. **Browser requirements**: Modern browser with MediaRecorder and Web Audio API
5. **HTTPS required**: Browsers block microphone access on HTTP
6. **No encryption**: Audio transmitted as base64 over HTTPS (transport encryption only)

## Performance Characteristics

### Latency
- **Best case**: 300-500ms (fast LAN)
- **Typical**: 500-1000ms (WiFi)
- **Acceptable**: < 2 seconds
- **Poor**: > 2 seconds

### Bandwidth
- **Per connection**: ~20-40 Kbps (Opus codec)
- **10 concurrent calls**: ~400 Kbps
- **Network overhead**: HTTPS + JSON adds ~20%

### Resource Usage
- **Dashboard memory**: ~5MB + 1MB per active call
- **Client memory**: ~3MB (receiver active)
- **Server memory**: <1MB per active voice session
- **CPU**: <5% per call (audio processing minimal)

## Security Considerations

1. **Microphone access**: Always requires user permission
2. **HTTPS required**: Prevents MITM attacks on audio
3. **No authentication**: Currently anyone can call any camera
4. **No rate limiting**: Can be abused for DoS
5. **Audio not encrypted**: Base64 encoding is not encryption

## Future Improvements

1. Add authentication/authorization for voice calls
2. Implement two-way communication
3. Add audio recording/playback on server
4. Support multiple codecs (AAC, MP3)
5. Add call quality indicators
6. Implement WebRTC for lower latency
7. Add push notifications instead of polling
8. Implement rate limiting
9. Add E2E encryption for audio
10. Support conference calls (multiple cameras)

## Support

If issues persist after following this guide:

1. Check `/admin/voice-test` page for diagnostic info
2. Review browser console for JavaScript errors
3. Check server logs for Python exceptions
4. Verify network connectivity and HTTPS
5. Test with different browsers
6. Ensure microphone works in other applications

For additional help, check:
- Documentation.org - Full system documentation
- DEVELOPER_HANDBOOK.org - API reference
- Changelog.org - Recent changes and fixes
