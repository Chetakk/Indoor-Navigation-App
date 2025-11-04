# Module Dependencies Map

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      index.html                         │
│                                                         │
│              <script type="module"                      │
│               src="/static/js/main.js">                 │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│                     main.js                             │
│  • App initialization                                   │
│  • Global function exposure                             │
│  • Event listeners                                      │
│  • Voice commands                                       │
└─────────┬───────────────────────────────────────────────┘
          │
          │ imports
          │
          ▼
┌─────────────────────────────────────────────────────────┐
│                    MODULES                              │
│                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   audio.js   │  │  camera.js   │  │ gyroscope.js │  │
│  │              │  │              │  │              │  │
│  │ • TTS        │  │ • Video      │  │ • Sensors    │  │
│  │ • Queue      │  │ • Stream     │  │ • Rotation   │  │
│  │ • Priority   │  │ • Capture    │  │ • Calibrate  │  │
│  └──────────────┘  └──────┬───────┘  └──────────────┘  │
│                           │                             │
│  ┌──────────────┐  ┌──────▼───────┐  ┌──────────────┐  │
│  │detection.js  │  │    ui.js     │  │ tracking.js  │  │
│  │              │  │              │  │              │  │
│  │ • Collision  │  │ • Canvas     │  │ • Track IDs  │  │
│  │ • Distance   │  │ • Stats      │  │ • Colors     │  │
│  │ • Direction  │  │ • Drawing    │  │ • Lifecycle  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                         │
│  ┌──────────────┐                                       │
│  │pathfinding.js│                                       │
│  │              │                                       │
│  │ • Navigation │                                       │
│  │ • Goals      │                                       │
│  │ • Path calc  │                                       │
│  └──────────────┘                                       │
└─────────────────────────────────────────────────────────┘
```

## Module Dependency Graph

### main.js (Entry Point)
```
main.js
├── imports audio.js
├── imports camera.js
├── imports gyroscope.js
├── imports detection.js
├── imports tracking.js
├── imports pathfinding.js
└── imports ui.js
```

### camera.js (Camera Module)
```
camera.js
├── imports audio.js (speak, audioState)
├── imports gyroscope.js (getCurrentOrientation)
├── imports detection.js (checkCollisionWarnings, announceDetections)
├── imports tracking.js (trackedObjects)
├── imports pathfinding.js (pathfindingEnabled)
└── imports ui.js (updateRealtimeStats, drawDetections)
```

### detection.js (Detection Module)
```
detection.js
├── imports audio.js (speak, queueAnnouncement)
└── imports tracking.js (trackedObjects, trackFirstSeen)
```

### ui.js (UI Module)
```
ui.js
├── imports tracking.js (getTrackColor, trackFirstSeen)
├── imports pathfinding.js (navigationPath, navigationGoal)
└── imports gyroscope.js (gyroscopeData)
```

### Standalone Modules
- **audio.js**: No dependencies (base module)
- **gyroscope.js**: No dependencies (base module)
- **tracking.js**: No dependencies (base module)
- **pathfinding.js**: No dependencies (base module)

## Import/Export Details

### audio.js
**Exports:**
```javascript
export const audioState = { ... }
export function toggleAudio()
export function speak(text, priority)
export function queueAnnouncement(text, priority)
export function testAudio()
```

### gyroscope.js
**Exports:**
```javascript
export const gyroscopeData = { ... }
export async function initializeOrientation()
export function getCurrentOrientation()
export function calibrateGyroscope()
export async function requestOrientationPermission()
export function calculateGyroscopeRotation()
```

### camera.js
**Exports:**
```javascript
export let stream = null
export let detectionActive = false
export function startCamera()
export function stopDetection()
export function startRealtimeAnalysis()
export function getCameraState()
```

### detection.js
**Exports:**
```javascript
export function checkCollisionWarnings(detections)
export function announceTrackingEvents(detections)
export function announceDetections(detections)
export function estimateDistance(bbox, className, w, h)
export function getObjectDirection(bbox, w, h)
export function setCanvas(canvasElement, ctxElement)
export function setTrackingEnabled(enabled)
export function clearTrackingData()
```

### tracking.js
**Exports:**
```javascript
export let trackingEnabled = true
export let trackedObjects = new Map()
export let trackColors = {}
export let trackFirstSeen = new Map()
export let trackLastMovement = new Map()
export function getTrackColor(trackId)
export function setTrackingEnabled(enabled)
export function clearTrackingData()
```

### pathfinding.js
**Exports:**
```javascript
export let navigationPath = null
export let navigationGoal = null
export let pathfindingEnabled = false
export function setNavigationGoal(event)
export function togglePathfinding()
export function calculateNavigationPath(detections)
export function getPathfindingState()
```

### ui.js
**Exports:**
```javascript
export function updateStats(detections)
export function updateFPS()
export function updateRealtimeStats()
export function toggleHeader()
export function drawDetections(detections)
export function updateRealtimeDetections(detections)
export function addOrientationStatusIndicator()
export function setCanvasAndVideo(c, ctx, v)
export function setDetectionActive(active)
export function incrementFrameCount()
```

## Data Flow

### Detection Pipeline
```
1. Camera captures frame
   ↓
2. Send to backend with gyroscope data
   ↓
3. Backend processes with YOLO
   ↓
4. Frontend receives detections
   ↓
5. Check collision warnings → Audio announcements
   ↓
6. Announce tracking events → Audio queue
   ↓
7. Update UI → Draw on canvas
   ↓
8. Update statistics display
```

### Audio Queue Flow
```
1. Detection event occurs
   ↓
2. Generate announcement text
   ↓
3. Queue with priority (critical/high/normal/low)
   ↓
4. Check queue size (max 10 items)
   ↓
5. Remove lowest priority if full
   ↓
6. Process queue by priority
   ↓
7. Speak with appropriate rate/volume
   ↓
8. On completion, process next in queue
```

### Gyroscope Integration
```
1. Initialize gyroscope sensor
   ↓
2. Read angular velocities (rad/s)
   ↓
3. Integrate to get rotation angles
   ↓
4. Calibrate baseline position
   ↓
5. Calculate relative rotation
   ↓
6. Send with frame to backend
   ↓
7. Backend adjusts detection coordinates
   ↓
8. Display rotation on UI indicator
```

## Global Window Bindings

These functions are exposed globally for HTML onclick handlers:

```javascript
window.startCamera = startCamera
window.toggleAudio = toggleAudio
window.testAudio = testAudio
window.testStats = testStats
window.testConnection = testConnection
window.toggleHeader = toggleHeader
window.showOrientationDebug = showOrientationDebug
window.testGyroscope = testGyroscope
window.requestOrientationPermission = requestOrientationPermission
window.togglePathfinding = togglePathfinding
window.setNavigationGoal = setNavigationGoal
window.announceDetections = announceDetections
```

## Key Design Decisions

1. **Base Modules First**: audio, gyroscope, tracking, pathfinding have no dependencies
2. **Layered Architecture**: detection depends on audio/tracking, ui depends on tracking/pathfinding
3. **Central Orchestrator**: camera.js coordinates between all modules during detection
4. **Global Exposure**: main.js exposes necessary functions to window for HTML onclick
5. **State Management**: Each module manages its own state, exports getters/setters
6. **Event-Driven**: Modules communicate through function calls, not events (simpler)
7. **Priority Queue**: Audio module ensures critical warnings always heard first
8. **Queue Limit**: Max 10 audio items prevents backlog from scene changes

## Performance Considerations

- **ES6 Modules**: Browser native, no bundler needed
- **Lazy Loading**: Could add dynamic imports for non-critical modules
- **Memory**: Queue limit prevents unbounded growth
- **FPS**: Drawing optimized with canvas-specific module
- **Gyroscope**: 60Hz sampling rate for smooth rotation tracking
