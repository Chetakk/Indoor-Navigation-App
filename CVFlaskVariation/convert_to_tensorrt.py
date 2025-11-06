"""
Convert YOLOv8 models to TensorRT format for faster inference on NVIDIA GPUs.

This script exports .pt models to TensorRT .engine files which provide
2-4x speedup on NVIDIA GPUs.

Usage:
    python convert_to_tensorrt.py --model yolov8n-oiv7.pt
    python convert_to_tensorrt.py --model yolov8x-oiv7.pt --imgsz 640 --half
"""

import argparse
import sys
from pathlib import Path
from ultralytics import YOLO


def convert_to_tensorrt(model_path, imgsz=640, half=False, workspace=4):
    """
    Convert YOLOv8 PyTorch model to TensorRT engine.

    Args:
        model_path: Path to .pt model file
        imgsz: Input image size (default 640)
        half: Use FP16 precision for 2x speedup (default False)
        workspace: GPU memory workspace in GB (default 4)

    Returns:
        Path to generated .engine file
    """
    print(f"\n{'='*60}")
    print(f"Converting YOLOv8 model to TensorRT")
    print(f"{'='*60}")
    print(f"Model: {model_path}")
    print(f"Image size: {imgsz}")
    print(f"Half precision (FP16): {half}")
    print(f"Workspace: {workspace}GB")
    print(f"{'='*60}\n")

    # Check if model exists
    model_file = Path(model_path)
    if not model_file.exists():
        print(f"ERROR: Model file not found: {model_path}")
        sys.exit(1)

    # Load model
    print("Loading PyTorch model...")
    try:
        model = YOLO(model_path)
    except Exception as e:
        print(f"ERROR loading model: {e}")
        sys.exit(1)

    # Export to TensorRT
    print("\nExporting to TensorRT (this may take several minutes)...")
    print("Note: First run will take longer as TensorRT builds optimized engine\n")

    try:
        # Ultralytics handles ONNX -> TensorRT conversion internally
        engine_path = model.export(
            format='engine',        # Export to TensorRT
            imgsz=imgsz,           # Input size
            half=half,             # FP16 precision
            workspace=workspace,    # GPU memory (GB)
            verbose=True,          # Show progress
            device=0               # GPU device 0
        )

        print(f"\n{'='*60}")
        print(f"SUCCESS! TensorRT engine created:")
        print(f"{engine_path}")
        print(f"{'='*60}\n")

        # Verify engine file
        engine_file = Path(engine_path)
        if engine_file.exists():
            size_mb = engine_file.stat().st_size / (1024 * 1024)
            print(f"Engine file size: {size_mb:.2f} MB")
            print(f"\nTo use this engine, update your detector:")
            print(f"  detector = YOLODetector(model_path='{engine_path}', force_cpu=False)")
            print(f"\nOr set environment variable:")
            print(f"  MODEL_PATH={engine_path}")

        return engine_path

    except Exception as e:
        print(f"\nERROR during TensorRT export: {e}")
        print("\nTroubleshooting:")
        print("1. Ensure NVIDIA GPU is available")
        print("2. Install CUDA Toolkit (11.8 or 12.1)")
        print("3. Install TensorRT: pip install tensorrt")
        print("4. Check PyTorch CUDA: python -c 'import torch; print(torch.cuda.is_available())'")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='Convert YOLOv8 models to TensorRT format',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '--model',
        type=str,
        required=True,
        help='Path to YOLOv8 .pt model file'
    )

    parser.add_argument(
        '--imgsz',
        type=int,
        default=640,
        help='Input image size (must match inference size)'
    )

    parser.add_argument(
        '--half',
        action='store_true',
        help='Use FP16 half precision for 2x speedup (recommended for RTX GPUs)'
    )

    parser.add_argument(
        '--workspace',
        type=int,
        default=4,
        help='GPU memory workspace in GB (increase for larger models)'
    )

    args = parser.parse_args()

    # Convert model
    convert_to_tensorrt(
        model_path=args.model,
        imgsz=args.imgsz,
        half=args.half,
        workspace=args.workspace
    )


if __name__ == '__main__':
    main()
