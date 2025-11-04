# Developer Guide - Modular JavaScript Architecture

## Quick Start

### Running the Application
1. Start the Flask server: `python run.py`
2. Open browser to `https://192.168.1.14:5000`
3. Click "Start Camera & Detection"
4. Audio announcements will guide you

### File Locations
```
app/
├── static/
│   └── js/
│       ├── main.js              # Entry point
│       └── modules/
│           ├── audio.js         # Audio & TTS
│           ├── camera.js        # Camera control
│           ├── detection.js     # Object detection
│           ├── gyroscope.js     # Sensors
│           ├── pathfinding.js   # Navigation
│           ├── tracking.js      # Object tracking
│           └── ui.js            # UI rendering
└── templates/
    └── index.html               # HTML (loads main.js)
```

## Common Tasks

### Adding a New Audio Announcement

**File**: `app/static/js/modules/audio.js`

```javascript
import { speak, queueAnnouncement } from './modules/audio.js';

// Immediate announcement (interrupts if high priority)
speak('Warning: obstacle ahead', 'high');

// Queued announcement (waits its turn)
queueAnnouncement('Person detected on your left', 'normal');
```

**Priority Levels**:
- `critical`: Interrupts everything, clears queue (max volume/speed)
- `high`: Interrupts current speech (max volume)
- `normal`: Queues if busy (normal volume)
- `low`: Queues if busy (reduced volume)

**Queue Behavior**:
- Max 10 items in queue
- When full, removes **lowest priority** items
- Prevents old announcements after scene changes

### Adding a New Detection Feature

**File**: `app/static/js/modules/detection.js`

```javascript
import { speak } from './audio.js';
import { trackedObjects } from './tracking.js';

export function myNewDetectionFeature(detections) {
    detections.forEach(detection => {
        // Your logic here
        const message = `New feature: ${detection.class_name}`;
        speak(message, 'normal');
    });
}
```

Then import in `main.js`:
```javascript
import { myNewDetectionFeature } from './modules/detection.js';
window.myNewDetectionFeature = myNewDetectionFeature; // For onclick
```

### Modifying UI Display

**File**: `app/static/js/modules/ui.js`

```javascript
export function updateCustomStat(value) {
    const element = document.getElementById('customStat');
    if (element) {
        element.textContent = value;
    }
}
```

### Adding Gyroscope Features

**File**: `app/static/js/modules/gyroscope.js`

```javascript
import { gyroscopeData, getCurrentOrientation } from './modules/gyroscope.js';

// Get current rotation data
const orientation = getCurrentOrientation();
if (orientation) {
    console.log('Rotation:', orientation.gyroscope_rotation);
    console.log('Angular velocity:', orientation.angular_velocity_z);
}

// Access raw gyroscope data
console.log('Gyroscope X:', gyroscopeData.x);
console.log('Gyroscope Y:', gyroscopeData.y);
console.log('Gyroscope Z:', gyroscopeData.z);
```

### Modifying Camera Behavior

**File**: `app/static/js/modules/camera.js`

```javascript
export function setCustomCameraOption(option) {
    // Modify camera constraints
    const constraints = {
        video: {
            facingMode: 'environment',
            width: { ideal: 1280 },
            height: { ideal: 720 },
            // Add your custom option
            [option]: value
        }
    };
    // Apply constraints...
}
```

## Module Communication Patterns

### Pattern 1: Direct Import
```javascript
// In detection.js
import { speak } from './audio.js';

export function announceObject(obj) {
    speak(`Detected ${obj.name}`, 'normal');
}
```

### Pattern 2: State Access
```javascript
// In ui.js
import { trackedObjects } from './tracking.js';

export function displayTrackedCount() {
    return trackedObjects.size;
}
```

### Pattern 3: Global Window (for HTML onclick)
```javascript
// In main.js
import { toggleAudio } from './modules/audio.js';

window.toggleAudio = toggleAudio; // Now onclick="toggleAudio()" works
```

### Pattern 4: Shared State Management
```javascript
// In tracking.js - Export state
export let trackedObjects = new Map();

export function addTrackedObject(id, data) {
    trackedObjects.set(id, data);
}

// In detection.js - Import and use
import { trackedObjects, addTrackedObject } from './tracking.js';

if (!trackedObjects.has(id)) {
    addTrackedObject(id, newData);
}
```

## Best Practices

### ✅ Do This

1. **Keep modules focused**
   ```javascript
   // Good: audio.js only handles audio
   export function speak(text, priority) { ... }
   ```

2. **Use clear exports**
   ```javascript
   // Good: Export what others need
   export function publicFunction() { ... }
   function privateHelper() { ... } // Not exported
   ```

3. **Import only what you need**
   ```javascript
   // Good: Specific imports
   import { speak, toggleAudio } from './audio.js';
   ```

4. **Document with JSDoc**
   ```javascript
   /**
    * Announce object detection with direction
    * @param {Object} detection - Detection object
    * @param {string} detection.class_name - Object class
    * @param {number} detection.confidence - Confidence score
    */
   export function announceDetection(detection) { ... }
   ```

### ❌ Avoid This

1. **Don't create circular dependencies**
   ```javascript
   // Bad: audio.js imports detection.js and vice versa
   // Solution: Extract shared code to new module
   ```

2. **Don't mutate imported state directly**
   ```javascript
   // Bad
   import { audioQueue } from './audio.js';
   audioQueue.push(item); // Direct mutation

   // Good
   import { queueAnnouncement } from './audio.js';
   queueAnnouncement(text, priority); // Use function
   ```

3. **Don't use global variables**
   ```javascript
   // Bad: Global state
   let myGlobalVar = 123;

   // Good: Module-scoped state
   export let myModuleState = 123;
   ```

## Debugging Tips

### Check Module Loading
```javascript
// In main.js
console.log('Audio module loaded:', !!window.toggleAudio);
console.log('Camera module loaded:', !!window.startCamera);
```

### Monitor Audio Queue
```javascript
// In audio.js - Add debug logs
export function getQueueStatus() {
    return {
        size: audioState.queue.length,
        maxSize: audioState.MAX_QUEUE_SIZE,
        isPlaying: audioState.isPlaying,
        items: audioState.queue.map(q => q.text)
    };
}
```

### Track Detection Flow
```javascript
// In detection.js - Add timing logs
export function announceDetections(detections) {
    console.time('announceDetections');
    // ... your code ...
    console.timeEnd('announceDetections');
}
```

### Monitor Gyroscope Data
```javascript
// In gyroscope.js
export function debugGyroscope() {
    return {
        initialized: gyroscopeData.initialized,
        calibrated: gyroscopeData.calibrated,
        rotation_z: gyroscopeData.rotation_z,
        angular_velocity_z: gyroscopeData.z
    };
}
```

## Testing

### Unit Test Example (Jest/Mocha)
```javascript
// audio.test.js
import { speak, queueAnnouncement, audioState } from '../modules/audio.js';

describe('Audio Module', () => {
    test('should limit queue to 10 items', () => {
        // Queue 15 items
        for (let i = 0; i < 15; i++) {
            queueAnnouncement(`Test ${i}`, 'low');
        }

        // Should only have 10
        expect(audioState.queue.length).toBeLessThanOrEqual(10);
    });

    test('should prioritize critical messages', () => {
        queueAnnouncement('Low priority', 'low');
        queueAnnouncement('CRITICAL!', 'critical');

        // Critical should be first
        expect(audioState.queue[0].priority).toBe('critical');
    });
});
```

### Integration Test
```javascript
// detection.test.js
import { checkCollisionWarnings } from '../modules/detection.js';
import { speak } from '../modules/audio.js';

jest.mock('../modules/audio.js');

test('should announce collision warnings', () => {
    const detections = [{
        class_name: 'person',
        collision: { collision_risk: true }
    }];

    checkCollisionWarnings(detections);
    expect(speak).toHaveBeenCalledWith(
        expect.stringContaining('collision'),
        'critical'
    );
});
```

## Performance Optimization

### Lazy Load Modules
```javascript
// main.js - Load pathfinding only when needed
document.getElementById('enablePathfinding').addEventListener('click', async () => {
    const { togglePathfinding } = await import('./modules/pathfinding.js');
    togglePathfinding();
});
```

### Debounce Frequent Calls
```javascript
// ui.js - Debounce stats updates
let updateTimeout;
export function debouncedUpdateStats(detections) {
    clearTimeout(updateTimeout);
    updateTimeout = setTimeout(() => {
        updateStats(detections);
    }, 100); // Update max every 100ms
}
```

### Optimize Audio Queue
```javascript
// audio.js - Clear old items by timestamp
function cleanOldQueueItems() {
    const now = Date.now();
    audioState.queue = audioState.queue.filter(
        item => (now - item.timestamp) < 5000 // Keep only last 5 seconds
    );
}
```

## Troubleshooting

### Module Not Loading
**Problem**: `Uncaught TypeError: Cannot read property 'speak' of undefined`

**Solution**: Check import path
```javascript
// Wrong
import { speak } from './audio.js'; // Missing 'modules/'

// Correct
import { speak } from './modules/audio.js';
```

### Function Not Found (onclick)
**Problem**: `Uncaught ReferenceError: toggleAudio is not defined`

**Solution**: Ensure global exposure in main.js
```javascript
// In main.js
import { toggleAudio } from './modules/audio.js';
window.toggleAudio = toggleAudio; // Make globally available
```

### CORS Issues
**Problem**: `Access to script at 'file://...' from origin 'null' has been blocked`

**Solution**: Must run through web server (Flask/HTTP), not file://

### Queue Not Limiting
**Problem**: Audio queue grows beyond 10 items

**Solution**: Check MAX_QUEUE_SIZE is being used
```javascript
// In audio.js
if (audioState.queue.length >= audioState.MAX_QUEUE_SIZE) {
    // Remove lowest priority item
}
```

## Adding New Modules

### Step 1: Create Module File
```javascript
// app/static/js/modules/mynewmodule.js

// State (module-scoped)
let myState = {
    // ...
};

// Private functions
function helperFunction() {
    // ...
}

// Public exports
export function publicFunction() {
    // ...
}

export { myState }; // Export state if needed
```

### Step 2: Import in main.js
```javascript
// main.js
import { publicFunction } from './modules/mynewmodule.js';

// Make globally available if needed for HTML onclick
window.publicFunction = publicFunction;
```

### Step 3: Use in Other Modules
```javascript
// modules/detection.js
import { publicFunction } from './mynewmodule.js';

export function useNewFeature() {
    publicFunction();
}
```

## Resources

- [ES6 Modules MDN](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules)
- [SpeechSynthesis API](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis)
- [Gyroscope API](https://developer.mozilla.org/en-US/docs/Web/API/Gyroscope)
- [Canvas API](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API)
- [MediaDevices API](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices)

## Support

For issues or questions:
1. Check [REFACTORING_SUMMARY.md](./REFACTORING_SUMMARY.md) for overview
2. Check [MODULE_DEPENDENCIES.md](./MODULE_DEPENDENCIES.md) for architecture
3. Review module-specific JSDoc comments
4. Test with browser DevTools console
