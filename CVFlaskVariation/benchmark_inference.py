"""
Benchmark YOLOv8 inference speed across different formats and devices.

Compares:
- PyTorch (.pt) on CPU
- PyTorch (.pt) on GPU
- TensorRT (.engine) on GPU

Usage:
    python benchmark_inference.py
    python benchmark_inference.py --model yolov8x-oiv7.pt --iterations 100
"""

import argparse
import time
import sys
import numpy as np
import cv2
from pathlib import Path
from ultralytics import YOLO
import torch


def create_dummy_image(size=(640, 640)):
    """Create a random test image."""
    return np.random.randint(0, 255, (*size, 3), dtype=np.uint8)


def benchmark_model(model_path, device='cpu', iterations=50, warmup=5):
    """
    Benchmark inference speed for a model.

    Args:
        model_path: Path to model file
        device: 'cpu' or 'cuda'
        iterations: Number of inference runs
        warmup: Number of warmup runs (excluded from timing)

    Returns:
        dict with timing statistics
    """
    print(f"\n{'='*60}")
    print(f"Benchmarking: {model_path}")
    print(f"Device: {device}")
    print(f"{'='*60}")

    # Check if model exists
    if not Path(model_path).exists():
        print(f"ERROR: Model not found: {model_path}")
        return None

    try:
        # Load model
        print("Loading model...")
        model = YOLO(model_path)
        model.to(device)

        # Create test image
        test_image = create_dummy_image()

        # Warmup runs
        print(f"Running {warmup} warmup iterations...")
        for i in range(warmup):
            _ = model(test_image, device=device, verbose=False)
            if device == 'cuda':
                torch.cuda.synchronize()  # Wait for GPU to finish

        # Benchmark runs
        print(f"Running {iterations} timed iterations...")
        times = []

        for i in range(iterations):
            start = time.perf_counter()
            _ = model(test_image, device=device, verbose=False)

            if device == 'cuda':
                torch.cuda.synchronize()  # Wait for GPU to finish

            end = time.perf_counter()
            elapsed_ms = (end - start) * 1000
            times.append(elapsed_ms)

            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{iterations} iterations completed...")

        # Calculate statistics
        times = np.array(times)
        stats = {
            'model': model_path,
            'device': device,
            'iterations': iterations,
            'mean_ms': np.mean(times),
            'std_ms': np.std(times),
            'min_ms': np.min(times),
            'max_ms': np.max(times),
            'median_ms': np.median(times),
            'p95_ms': np.percentile(times, 95),
            'p99_ms': np.percentile(times, 99),
        }

        # Print results
        print(f"\n{'='*60}")
        print(f"Results for {Path(model_path).name} on {device.upper()}")
        print(f"{'='*60}")
        print(f"Mean:     {stats['mean_ms']:.2f} ms")
        print(f"Median:   {stats['median_ms']:.2f} ms")
        print(f"Std Dev:  {stats['std_ms']:.2f} ms")
        print(f"Min:      {stats['min_ms']:.2f} ms")
        print(f"Max:      {stats['max_ms']:.2f} ms")
        print(f"95th %:   {stats['p95_ms']:.2f} ms")
        print(f"99th %:   {stats['p99_ms']:.2f} ms")
        print(f"{'='*60}\n")

        return stats

    except Exception as e:
        print(f"ERROR: {e}")
        return None


def compare_models(base_model='yolov8n-oiv7.pt', iterations=50):
    """
    Compare all available model formats.

    Args:
        base_model: Base PyTorch model name
        iterations: Number of benchmark iterations
    """
    results = []

    # Test PyTorch on CPU
    print("\n*** Testing PyTorch model on CPU ***")
    if Path(base_model).exists():
        stats = benchmark_model(base_model, device='cpu', iterations=iterations)
        if stats:
            results.append(stats)
    else:
        print(f"Model not found: {base_model}")

    # Test PyTorch on GPU
    if torch.cuda.is_available():
        print("\n*** Testing PyTorch model on GPU ***")
        if Path(base_model).exists():
            stats = benchmark_model(base_model, device='cuda', iterations=iterations)
            if stats:
                results.append(stats)
    else:
        print("\nGPU not available - skipping GPU benchmarks")
        return results

    # Test TensorRT engine
    engine_path = str(Path(base_model).with_suffix('.engine'))
    if Path(engine_path).exists():
        print("\n*** Testing TensorRT engine on GPU ***")
        stats = benchmark_model(engine_path, device='cuda', iterations=iterations)
        if stats:
            results.append(stats)
    else:
        print(f"\nTensorRT engine not found: {engine_path}")
        print("Run convert_to_tensorrt.py to create it")

    # Print comparison
    if len(results) > 1:
        print("\n" + "="*60)
        print("COMPARISON SUMMARY")
        print("="*60)

        baseline = results[0]['mean_ms']

        for i, stats in enumerate(results):
            speedup = baseline / stats['mean_ms']
            model_name = Path(stats['model']).suffix
            device_str = stats['device'].upper()

            print(f"\n{i+1}. {model_name} on {device_str}:")
            print(f"   Mean: {stats['mean_ms']:.2f} ms")
            print(f"   Speedup: {speedup:.2f}x faster than baseline")

            if i == 0:
                print(f"   (baseline)")

        print("\n" + "="*60)

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Benchmark YOLOv8 inference speed',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        '--model',
        type=str,
        default='yolov8n-oiv7.pt',
        help='Base model to benchmark'
    )

    parser.add_argument(
        '--iterations',
        type=int,
        default=50,
        help='Number of benchmark iterations'
    )

    parser.add_argument(
        '--warmup',
        type=int,
        default=5,
        help='Number of warmup iterations'
    )

    parser.add_argument(
        '--device',
        type=str,
        choices=['cpu', 'cuda', 'auto'],
        default='auto',
        help='Device to use (auto tests all available)'
    )

    args = parser.parse_args()

    print("="*60)
    print("YOLOv8 Inference Benchmark")
    print("="*60)
    print(f"Model: {args.model}")
    print(f"Iterations: {args.iterations}")
    print(f"Device: {args.device}")

    # Check GPU
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
        print(f"CUDA Version: {torch.version.cuda}")
    else:
        print("GPU: Not available")

    print("="*60)

    if args.device == 'auto':
        # Compare all available formats
        compare_models(args.model, args.iterations)
    else:
        # Benchmark single configuration
        benchmark_model(args.model, device=args.device, iterations=args.iterations, warmup=args.warmup)


if __name__ == '__main__':
    main()
