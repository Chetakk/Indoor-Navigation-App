# Queue Size = 1: Absolute Latest Information Only

## Configuration

All queues have been set to **size 1** for maximum responsiveness and absolute latest information.

### Audio Queue
**File**: [audio.js:13](app/static/js/modules/audio.js#L13)
```javascript
MAX_QUEUE_SIZE: 1  // Only 1 item - absolute latest info only!
```

### Detection Display Queue
**File**: [ui.js:22-23](app/static/js/modules/ui.js#L22-L23)
```javascript
// Circular queue for detection results (keep last 1 - absolute latest only!)
const MAX_DETECTION_ITEMS = 1;
```

## How It Works

### Audio Announcements
```
Frame 1: "person ahead"        → Queue: ["person ahead"]
Frame 2: "chair on left"        → Queue: ["chair on left"]      // "person ahead" removed
Frame 3: "table very close"     → Queue: ["table very close"]   // "chair on left" removed
```

**Result**: Only the **single latest** announcement plays, no backlog possible!

### Detection Display Panel
```
Frame 1: Shows "person"         → Panel: [person]
Frame 2: Shows "chair"          → Panel: [chair]                // person removed
Frame 3: Shows "table"          → Panel: [table]                // chair removed
```

**Result**: Panel shows only the **single latest** object class detected!

## Benefits

### 🚀 Maximum Responsiveness
- **Zero lag** - no waiting for old announcements
- **Instant updates** - always current frame info
- **Real-time** - what you hear matches what's happening NOW

### 💾 Minimal Memory
- Audio queue: Max 1 item = ~100 bytes
- Detection display: Max 1 item = ~500 bytes
- **Total overhead: < 1KB!**

### ⚡ Performance
- No sorting needed (only 1 item)
- No iteration needed (only 1 item)
- **Fastest possible processing!**

### 🎯 Blind Navigation Optimized
- Latest info = most relevant for navigation
- No confusion from outdated announcements
- Clear, immediate feedback

## Behavior Examples

### Scenario 1: Rapid Scene Changes
```
Walking through doorway:
- Frame 1: "door ahead"         → Speaks: "door ahead"
- Frame 2: "chair on left"      → Speaks: "chair on left" (door dropped)
- Frame 3: "table very close"   → Speaks: "table very close" (chair dropped)
```
**Perfect!** Each announcement is current and relevant.

### Scenario 2: Same Object Updates
```
Approaching person:
- Frame 1: "person far ahead"       → Speaks: "person far ahead"
- Frame 2: "person medium ahead"    → Speaks: "person medium ahead" (old dropped)
- Frame 3: "person very close"      → Speaks: "person very close" (old dropped)
```
**Perfect!** Always know current distance, no outdated info.

### Scenario 3: Detection Panel
```
Multiple objects in scene:
- Frame 1: Detects [person, chair, table]   → Shows: last one (e.g., "table")
- Frame 2: Detects [person, door]           → Shows: last one (e.g., "door")
- Frame 3: Detects [chair]                  → Shows: "chair"
```
**Note**: With size 1, panel shows only ONE object class at a time (the last processed).

## Trade-offs

### ✅ Advantages
1. **Zero lag** - impossible to build backlog
2. **Always current** - info matches NOW
3. **Maximum performance** - minimal overhead
4. **Simple logic** - just overwrite
5. **Predictable** - always 1 item max

### ⚠️ Considerations
1. **Rapid changes** - if scene changes faster than speech, you may miss some announcements
2. **Multiple objects** - panel shows only 1 class at a time
3. **No history** - can't see what was detected before

## When to Use Queue Size 1

### ✅ Perfect For:
- **Blind navigation** - need latest info NOW
- **Dynamic scenes** - frequent changes
- **Slow devices** - minimal overhead
- **Real-time response** - no delay tolerance
- **Indoor navigation** - quick turns, doorways
- **Crowded areas** - constantly changing

### 🤔 Consider Larger Queue (3-5) If:
- Multiple objects need announcing
- Want brief history of detections
- Scene changes are slower
- Can tolerate slight delay

## Configuration Options

### Quick Change
If you need to adjust queue sizes:

#### Audio Queue
Edit [audio.js:13](app/static/js/modules/audio.js#L13):
```javascript
MAX_QUEUE_SIZE: 1  // Change to 3, 5, etc. if needed
```

#### Detection Display
Edit [ui.js:23](app/static/js/modules/ui.js#L23):
```javascript
const MAX_DETECTION_ITEMS = 1;  // Change to 3, 5, etc. if needed
```

### Recommended Sizes by Use Case

| Use Case | Audio Queue | Display Queue | Reasoning |
|----------|-------------|---------------|-----------|
| **Indoor Navigation (Default)** | **1** | **1** | Maximum responsiveness |
| Outdoor Open Spaces | 3 | 5 | More time between changes |
| Stationary Object Inspection | 5 | 10 | Build context |
| Demo/Testing | 3 | 10 | Show multiple detections |

## Testing

### Verify Queue Size 1
```javascript
// In browser console after detection starts:

// Check audio queue
console.log('Audio queue size:', audioState.queue.length);
// Should always show: 0 or 1

// Check detection queue (need to access internal state)
// Watch console for "Detection queue full - removed oldest" messages
// Should see this for EVERY new detection
```

### Monitor Behavior
1. Start detection in busy scene
2. Watch console logs
3. Should see continuous "removed oldest" messages
4. Audio should speak only latest info
5. Panel should show only 1 object class

## Summary

**Queue Size = 1** means:
- ✅ **Audio**: Only 1 announcement queued max
- ✅ **Display**: Only 1 object class shown max
- ✅ **Result**: Absolute latest information only
- ✅ **Performance**: Maximum speed, zero lag
- ✅ **Perfect for**: Real-time blind indoor navigation

**The system now responds instantly with the most current information!** 🚀

---

**Current Configuration**:
- Audio Queue: **1** item max
- Detection Display: **1** item max
- Confidence Threshold: **30%** minimum
- Detection Boxes: **Toggle ON/OFF**

**Everything optimized for real-time navigation!** ⚡
