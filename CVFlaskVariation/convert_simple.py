"""
Simple TensorRT conversion script with better error handling.
"""

from ultralytics import YOLO
import torch

print("="*60)
print("TensorRT Conversion - Simple Method")
print("="*60)

# Check CUDA
print(f"\nCUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"CUDA version: {torch.version.cuda}")
else:
    print("ERROR: CUDA not available!")
    exit(1)

# Load model
print("\nLoading model...")
model = YOLO('yolov8x-oiv7.pt')

# Export with verbose output and smaller workspace
print("\nExporting to TensorRT...")
print("This will take 3-5 minutes...")
print("-"*60)

try:
    # Use smaller workspace and enable verbose
    path = model.export(
        format='engine',
        device=0,
        half=False,  # Start with FP32
        workspace=2,  # Reduce from 4GB to 2GB
        verbose=True,
        simplify=True,  # Simplify ONNX graph
        batch=1,
    )
    print("-"*60)
    print(f"\nSUCCESS! Engine created: {path}")

except Exception as e:
    print(f"\nERROR during export: {e}")
    print("\nTrying alternative method...")

    # Try with even smaller workspace
    try:
        path = model.export(
            format='engine',
            device=0,
            half=False,
            workspace=1,  # 1GB
            verbose=True,
        )
        print(f"\nSUCCESS with reduced workspace: {path}")
    except Exception as e2:
        print(f"\nFailed again: {e2}")
        print("\nTroubleshooting steps:")
        print("1. Check TensorRT installation: pip list | grep tensorrt")
        print("2. Update TensorRT: pip install --upgrade tensorrt")
        print("3. Check CUDA compatibility")
        print("4. Try with smaller model: yolov8n.pt (not OIV7)")
