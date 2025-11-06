"""
Benchmark TensorRT engine performance.
"""

from ultralytics import YOLO
import torch
import time
import numpy as np

print("="*60)
print("TensorRT Benchmark")
print("="*60)

# Create dummy image
test_image = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)

# Test PyTorch GPU
print("\n1. PyTorch GPU (.pt on CUDA)")
print("-"*60)
model_pt = YOLO('yolov8n-oiv7.pt')

# Warmup
for _ in range(5):
    _ = model_pt(test_image, device='cuda', verbose=False)

# Benchmark
times_pt = []
for i in range(30):
    start = time.perf_counter()
    _ = model_pt(test_image, device='cuda', verbose=False)
    torch.cuda.synchronize()
    times_pt.append((time.perf_counter() - start) * 1000)

print(f"Mean: {np.mean(times_pt):.2f} ms")
print(f"Median: {np.median(times_pt):.2f} ms")
print(f"Min: {np.min(times_pt):.2f} ms")
print(f"Max: {np.max(times_pt):.2f} ms")

# Test TensorRT
print("\n2. TensorRT Engine (.engine on CUDA)")
print("-"*60)
model_trt = YOLO('yolov8n-oiv7.engine')

# Warmup
for _ in range(5):
    _ = model_trt(test_image, device='cuda', verbose=False)

# Benchmark
times_trt = []
for i in range(30):
    start = time.perf_counter()
    _ = model_trt(test_image, device='cuda', verbose=False)
    torch.cuda.synchronize()
    times_trt.append((time.perf_counter() - start) * 1000)

print(f"Mean: {np.mean(times_trt):.2f} ms")
print(f"Median: {np.median(times_trt):.2f} ms")
print(f"Min: {np.min(times_trt):.2f} ms")
print(f"Max: {np.max(times_trt):.2f} ms")

# Comparison
print("\n" + "="*60)
print("COMPARISON")
print("="*60)
speedup = np.mean(times_pt) / np.mean(times_trt)
print(f"PyTorch GPU:  {np.mean(times_pt):.2f} ms")
print(f"TensorRT:     {np.mean(times_trt):.2f} ms")
print(f"Speedup:      {speedup:.2f}x faster")
print(f"Improvement:  {((speedup - 1) * 100):.1f}% faster")
