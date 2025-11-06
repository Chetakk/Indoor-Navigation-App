# TensorRT Setup Guide

This guide explains how to convert YOLOv8 models to TensorRT for 2-4x faster inference on NVIDIA GPUs.

## Prerequisites

### 1. NVIDIA GPU
- CUDA-capable GPU (GTX 1060 or newer recommended)
- Check GPU: `nvidia-smi`

### 2. CUDA Toolkit
Install CUDA 11.8 or 12.1:
- Download from: https://developer.nvidia.com/cuda-downloads
- Verify installation: `nvcc --version`

### 3. PyTorch with CUDA
```bash
# For CUDA 11.8
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# For CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

# Verify CUDA is available
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### 4. TensorRT (Optional but Recommended)
```bash
# Install via pip (easier)
pip install tensorrt

# Or download from NVIDIA (for latest version)
# https://developer.nvidia.com/tensorrt
```

## Model Conversion

### Step 1: Convert PyTorch to TensorRT

Convert your trained model to TensorRT engine format:

```bash
# For nano model (fastest conversion, good for testing)
python convert_to_tensorrt.py --model yolov8n-oiv7.pt

# For large model (best accuracy, slower conversion)
python convert_to_tensorrt.py --model yolov8x-oiv7.pt

# With FP16 half precision (2x faster, recommended for RTX GPUs)
python convert_to_tensorrt.py --model yolov8n-oiv7.pt --half

# Custom image size (must match inference size)
python convert_to_tensorrt.py --model yolov8n-oiv7.pt --imgsz 640
```

This will create a `.engine` file in the same directory as your `.pt` file.

**Note:** First-time conversion takes 5-15 minutes depending on model size. The engine file is optimized for your specific GPU and cannot be transferred to other machines.

### Step 2: Update Configuration

#### Option A: Environment Variable (Recommended)
```bash
# Windows (PowerShell)
$env:MODEL_PATH="yolov8n-oiv7.engine"
$env:FORCE_CPU="false"

# Windows (CMD)
set MODEL_PATH=yolov8n-oiv7.engine
set FORCE_CPU=false

# Linux/Mac
export MODEL_PATH=yolov8n-oiv7.engine
export FORCE_CPU=false
```

#### Option B: Edit config.py
```python
# In app/config.py
MODEL_PATH = 'yolov8n-oiv7.engine'
FORCE_CPU = False
```

#### Option C: Modify __init__.py
```python
# In app/__init__.py
detector = get_detector(
    model_path='yolov8n-oiv7.engine',
    force_cpu=False  # Enable GPU
)
```

### Step 3: Run Flask Application
```bash
python run.py
```

Check logs for confirmation:
```
Loading YOLO model from yolov8n-oiv7.engine (format: .engine)...
GPU Detected: NVIDIA GeForce RTX 3080
Using TensorRT engine for optimized GPU inference
Model loaded successfully on cuda
```

## Benchmarking

Run the benchmark script to compare performance:

```bash
python benchmark_inference.py
```

Expected results:
- **PyTorch (.pt) on CPU:** 80-160ms per image
- **PyTorch (.pt) on GPU:** 30-70ms per image
- **TensorRT (.engine) FP32:** 15-40ms per image
- **TensorRT (.engine) FP16:** 10-25ms per image

## Troubleshooting

### "CUDA not available"
```bash
# Check PyTorch CUDA installation
python -c "import torch; print(torch.cuda.is_available())"

# Reinstall PyTorch with CUDA
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

### "TensorRT export failed"
```bash
# Install TensorRT
pip install tensorrt

# Or use ONNX as intermediate step
pip install onnx onnxruntime-gpu
```

### "GPU hanging/freezing"
- Reduce batch size in detection code
- Lower `max_det` parameter
- Check GPU memory: `nvidia-smi`
- Update NVIDIA drivers

### "Engine file doesn't work on different machine"
TensorRT engines are GPU-specific and cannot be transferred. You must reconvert the model on each machine.

## Performance Tips

1. **Use FP16 for RTX GPUs:** 2x faster with minimal accuracy loss
   ```bash
   python convert_to_tensorrt.py --model yolov8n-oiv7.pt --half
   ```

2. **Match image sizes:** Engine is optimized for specific input size (default 640x640)

3. **Warm-up inference:** First inference is slower due to GPU initialization

4. **Monitor GPU usage:** Use `nvidia-smi` to check utilization

5. **Choose right model:**
   - `yolov8n`: Fastest, good for real-time (5ms - 15ms)
   - `yolov8s`: Balanced (10ms - 20ms)
   - `yolov8m`: More accurate (15ms - 30ms)
   - `yolov8x`: Most accurate (25ms - 50ms)

## Model Comparison

| Model | Size | Params | PyTorch GPU | TensorRT FP16 | Accuracy |
|-------|------|--------|-------------|---------------|----------|
| YOLOv8n | 6 MB | 3.2M | 30-50ms | 10-20ms | Good |
| YOLOv8s | 22 MB | 11.2M | 40-60ms | 15-25ms | Better |
| YOLOv8m | 52 MB | 25.9M | 50-80ms | 20-35ms | Great |
| YOLOv8x | 136 MB | 68.2M | 70-120ms | 30-50ms | Best |

## Next Steps

1. Convert your model to TensorRT
2. Benchmark to measure speedup
3. Update configuration to use `.engine` file
4. Deploy to production

For multi-worker setup (handling concurrent requests), see FLASK_WORKERS.md.
