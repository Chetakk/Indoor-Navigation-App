# Confidence Filtering Implementation

## Problem
The system was announcing predictions with **0% confidence** - completely unreliable detections that were causing false alerts.

## Solution
Added **30% minimum confidence threshold** throughout the detection pipeline to filter out low-confidence predictions.

## Changes Made

### 1. Backend Filtering (Python)
**File**: `app/routes/detection.py:152-157`

```python
# Filter by confidence threshold FIRST (before dedup)
raw_detections_before_filtering = len(raw_detections)
raw_detections = filter_detections_by_confidence(raw_detections, min_confidence=0.3)
confidence_filtered = raw_detections_before_filtering - len(raw_detections)
if confidence_filtered > 0:
    logger.info(f"🎯 Confidence filtering removed {confidence_filtered} low-confidence detections (< 30%)")
```

**Benefits**:
- Filters out junk predictions before they reach the tracking system
- Reduces network payload
- Prevents low-confidence objects from getting track IDs

### 2. Frontend Filtering (JavaScript)
**File**: `app/static/js/modules/detection.js:17-39`

```javascript
// Minimum confidence threshold - ignore predictions below this
let MIN_CONFIDENCE_THRESHOLD = 0.3; // 30% minimum confidence

export function setConfidenceThreshold(threshold) {
    if (threshold >= 0 && threshold <= 1) {
        MIN_CONFIDENCE_THRESHOLD = threshold;
        console.log(`Confidence threshold set to ${(threshold * 100).toFixed(0)}%`);
    }
}

export function getConfidenceThreshold() {
    return MIN_CONFIDENCE_THRESHOLD;
}
```

**Applied in 3 key functions**:

#### a) Collision Warnings (`checkCollisionWarnings`)
```javascript
detections.forEach(detection => {
    // Skip low confidence detections
    if (detection.confidence < MIN_CONFIDENCE_THRESHOLD) {
        console.log(`Skipping low confidence collision check: ${detection.class_name} (${(detection.confidence * 100).toFixed(1)}%)`);
        return;
    }
    // ... collision logic
});
```

#### b) Tracking Events (`announceTrackingEvents`)
```javascript
detections.forEach(detection => {
    // Skip low confidence detections
    if (detection.confidence < MIN_CONFIDENCE_THRESHOLD) {
        console.log(`Skipping low confidence tracking: ${detection.class_name} (${(detection.confidence * 100).toFixed(1)}%)`);
        return;
    }
    // ... tracking logic
});
```

#### c) Detection Announcements (`announceDetections`)
```javascript
detections.forEach((detection, index) => {
    // Skip low confidence detections
    if (detection.confidence < MIN_CONFIDENCE_THRESHOLD) {
        console.log(`Skipping low confidence announcement: ${detection.class_name} (${(detection.confidence * 100).toFixed(1)}%)`);
        return;
    }
    // ... announcement logic
});
```

## Configuration

### Default Threshold
- **30% confidence** (0.3)
- Balanced between false positives and missing real objects

### Adjusting the Threshold

#### Backend (Python)
Edit `app/routes/detection.py:154`:
```python
raw_detections = filter_detections_by_confidence(raw_detections, min_confidence=0.3)
#                                                                              ↑
#                                                                       Change this value
```

#### Frontend (JavaScript)
Using the exported function:
```javascript
import { setConfidenceThreshold } from './modules/detection.js';

// Set to 50% threshold
setConfidenceThreshold(0.5);

// Or in browser console
window.setConfidenceThreshold(0.4); // 40% threshold
```

Or edit `app/static/js/modules/detection.js:18`:
```javascript
let MIN_CONFIDENCE_THRESHOLD = 0.3; // Change this value
```

## Recommended Thresholds

| Threshold | Use Case | Trade-offs |
|-----------|----------|------------|
| **0.2 (20%)** | Maximum sensitivity | Many false positives |
| **0.3 (30%)** | **Balanced (DEFAULT)** | Good accuracy, few false alarms |
| **0.4 (40%)** | High accuracy | May miss some objects |
| **0.5 (50%)** | Very high confidence | Only very certain detections |
| **0.7 (70%)** | Critical systems | May miss many real objects |

## Impact

### Before Filtering
```
Detection: person (confidence: 0%)     ❌ Announced
Detection: chair (confidence: 5%)      ❌ Announced
Detection: car (confidence: 15%)       ❌ Announced
Detection: person (confidence: 85%)    ✅ Announced
```

### After Filtering (30% threshold)
```
Detection: person (confidence: 0%)     🚫 FILTERED OUT
Detection: chair (confidence: 5%)      🚫 FILTERED OUT
Detection: car (confidence: 15%)       🚫 FILTERED OUT
Detection: person (confidence: 85%)    ✅ Announced
```

## Logging

The system logs filtered detections for debugging:

### Backend Logs
```
🎯 Confidence filtering removed 3 low-confidence detections (< 30%)
```

### Frontend Console Logs
```
Skipping low confidence collision check: person (0.0%)
Skipping low confidence tracking: chair (5.2%)
Skipping low confidence announcement: car (15.8%)
```

## Testing

### Check Current Threshold
```javascript
// In browser console
console.log('Current threshold:', window.getConfidenceThreshold());
```

### Test Different Thresholds
```javascript
// More lenient (accept more detections)
window.setConfidenceThreshold(0.2);

// More strict (only high confidence)
window.setConfidenceThreshold(0.5);

// Reset to default
window.setConfidenceThreshold(0.3);
```

### Monitor Filtered Detections
Open browser console and watch for "Skipping low confidence" messages to see what's being filtered.

## Related Files

- **Backend**:
  - `app/routes/detection.py` - Main detection endpoint with filtering
  - `app/utils/filtering.py` - `filter_detections_by_confidence()` function

- **Frontend**:
  - `app/static/js/modules/detection.js` - All detection announcements
  - `app/static/js/modules/audio.js` - Audio queue (unaffected by confidence)

## Summary

✅ **Backend**: Filters at 30% before tracking
✅ **Frontend**: Double-checks at 30% before announcements
✅ **Configurable**: Easy to adjust threshold
✅ **Logged**: See what's being filtered
✅ **Defensive**: Two layers of filtering ensure no junk gets through

No more 0% confidence announcements! 🎯
