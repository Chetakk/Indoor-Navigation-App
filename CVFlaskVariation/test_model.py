"""
Test script to isolate YOLO model hanging issue
"""
import cv2
import numpy as np
from ultralytics import YOLO
import torch

print("=" * 70)
print("Testing YOLO Model Inference")
print("=" * 70)

# Check device
device = 'cpu'  # Start with CPU
print(f"\n1. Device: {device}")
print(f"   CUDA Available: {torch.cuda.is_available()}")

# Load model
print(f"\n2. Loading model...")
model = YOLO('yolov8x-oiv7.pt')
print(f"   ✅ Model loaded")

# Create test image
print(f"\n3. Creating test image...")
test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
print(f"   Shape: {test_image.shape}")
print(f"   Dtype: {test_image.dtype}")

# Test inference
print(f"\n4. Running inference...")
print(f"   Calling model()...")
results = model(test_image, verbose=False)
print(f"   ✅ Inference complete!")

# Check results
print(f"\n5. Results:")
print(f"   Number of result objects: {len(results)}")
if len(results) > 0:
    print(f"   Boxes: {results[0].boxes}")
    if results[0].boxes is not None:
        print(f"   Number of detections: {len(results[0].boxes)}")

print(f"\n" + "=" * 70)
print("✅ Test completed successfully!")
print("=" * 70)
