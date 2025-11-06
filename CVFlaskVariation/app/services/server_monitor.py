"""
Server monitoring service for collecting system metrics and health information.
"""
import psutil
import time
import torch
from datetime import datetime
from typing import Dict, Any, Callable
from functools import wraps
from app.services.yolo_detector import get_detector


def cache_metric(cache_duration: float = 3.0):
    """
    Decorator to cache metric results for a specified duration.

    Args:
        cache_duration: Cache duration in seconds (default: 3 seconds)
    """
    def decorator(func: Callable):
        cache = {'result': None, 'timestamp': 0}

        @wraps(func)
        def wrapper(*args, **kwargs):
            current_time = time.time()
            if current_time - cache['timestamp'] > cache_duration:
                cache['result'] = func(*args, **kwargs)
                cache['timestamp'] = current_time
            return cache['result']

        return wrapper
    return decorator


class ServerMonitor:
    """Monitors server health, performance metrics, and system resources."""

    def __init__(self):
        self.start_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.total_inference_time = 0.0
        self.inference_count = 0

    def get_uptime(self) -> float:
        """Get server uptime in seconds."""
        return time.time() - self.start_time

    def get_uptime_formatted(self) -> str:
        """Get formatted uptime string."""
        uptime = self.get_uptime()
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        parts.append(f"{seconds}s")

        return " ".join(parts)

    @cache_metric(cache_duration=3.0)
    def get_cpu_metrics(self) -> Dict[str, Any]:
        """Get CPU usage metrics."""
        return {
            'percent': psutil.cpu_percent(interval=0.1),
            'count': psutil.cpu_count(),
            'frequency': psutil.cpu_freq().current if psutil.cpu_freq() else 0
        }

    @cache_metric(cache_duration=3.0)
    def get_memory_metrics(self) -> Dict[str, Any]:
        """Get system memory metrics."""
        memory = psutil.virtual_memory()
        return {
            'total_gb': round(memory.total / (1024**3), 2),
            'used_gb': round(memory.used / (1024**3), 2),
            'available_gb': round(memory.available / (1024**3), 2),
            'percent': memory.percent
        }

    @cache_metric(cache_duration=3.0)
    def get_gpu_metrics(self) -> Dict[str, Any]:
        """Get GPU metrics if available."""
        if not torch.cuda.is_available():
            return {
                'available': False,
                'name': None,
                'memory_total_gb': 0,
                'memory_allocated_gb': 0,
                'memory_cached_gb': 0,
                'utilization_percent': 0
            }

        try:
            gpu_name = torch.cuda.get_device_name(0)
            memory_allocated = torch.cuda.memory_allocated(0) / (1024**3)
            memory_cached = torch.cuda.memory_reserved(0) / (1024**3)
            memory_total = torch.cuda.get_device_properties(0).total_memory / (1024**3)

            # Calculate utilization based on allocated memory
            utilization = (memory_allocated / memory_total * 100) if memory_total > 0 else 0

            return {
                'available': True,
                'name': gpu_name,
                'memory_total_gb': round(memory_total, 2),
                'memory_allocated_gb': round(memory_allocated, 2),
                'memory_cached_gb': round(memory_cached, 2),
                'utilization_percent': round(utilization, 1)
            }
        except Exception as e:
            return {
                'available': True,
                'error': str(e),
                'memory_total_gb': 0,
                'memory_allocated_gb': 0,
                'memory_cached_gb': 0,
                'utilization_percent': 0
            }

    @cache_metric(cache_duration=5.0)
    def get_disk_metrics(self) -> Dict[str, Any]:
        """Get disk usage metrics."""
        try:
            disk = psutil.disk_usage('/')
            return {
                'total_gb': round(disk.total / (1024**3), 2),
                'used_gb': round(disk.used / (1024**3), 2),
                'free_gb': round(disk.free / (1024**3), 2),
                'percent': disk.percent
            }
        except Exception as e:
            return {
                'error': str(e),
                'total_gb': 0,
                'used_gb': 0,
                'free_gb': 0,
                'percent': 0
            }

    def get_model_status(self) -> Dict[str, Any]:
        """Get model loading status and information."""
        try:
            detector = get_detector()
            return {
                'loaded': detector is not None,
                'classes': len(detector.class_names) if detector else 0,
                'device': str(detector.device) if detector else 'unknown',
                'model_type': 'YOLOv8'
            }
        except Exception as e:
            return {
                'loaded': False,
                'error': str(e),
                'classes': 0,
                'device': 'unknown',
                'model_type': 'YOLOv8'
            }

    @cache_metric(cache_duration=3.0)
    def get_network_metrics(self) -> Dict[str, Any]:
        """Get network I/O metrics."""
        try:
            net_io = psutil.net_io_counters()
            return {
                'bytes_sent_mb': round(net_io.bytes_sent / (1024**2), 2),
                'bytes_recv_mb': round(net_io.bytes_recv / (1024**2), 2),
                'packets_sent': net_io.packets_sent,
                'packets_recv': net_io.packets_recv
            }
        except Exception as e:
            return {
                'error': str(e),
                'bytes_sent_mb': 0,
                'bytes_recv_mb': 0,
                'packets_sent': 0,
                'packets_recv': 0
            }

    @cache_metric(cache_duration=3.0)
    def get_process_metrics(self) -> Dict[str, Any]:
        """Get current process metrics."""
        try:
            process = psutil.Process()
            return {
                'cpu_percent': process.cpu_percent(interval=0.1),
                'memory_mb': round(process.memory_info().rss / (1024**2), 2),
                'threads': process.num_threads(),
                'open_files': len(process.open_files())
            }
        except Exception as e:
            return {
                'error': str(e),
                'cpu_percent': 0,
                'memory_mb': 0,
                'threads': 0,
                'open_files': 0
            }

    def record_request(self):
        """Record a new request."""
        self.request_count += 1

    def record_error(self):
        """Record an error."""
        self.error_count += 1

    def record_inference(self, inference_time: float):
        """Record inference time."""
        self.total_inference_time += inference_time
        self.inference_count += 1

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics."""
        avg_inference_time = (
            self.total_inference_time / self.inference_count
            if self.inference_count > 0
            else 0
        )

        error_rate = (
            (self.error_count / self.request_count * 100)
            if self.request_count > 0
            else 0
        )

        return {
            'total_requests': self.request_count,
            'total_errors': self.error_count,
            'error_rate_percent': round(error_rate, 2),
            'total_inferences': self.inference_count,
            'avg_inference_time_ms': round(avg_inference_time * 1000, 2),
            'uptime_seconds': round(self.get_uptime(), 2),
            'uptime_formatted': self.get_uptime_formatted()
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status."""
        cpu = self.get_cpu_metrics()
        memory = self.get_memory_metrics()
        gpu = self.get_gpu_metrics()
        model = self.get_model_status()

        # Determine health status
        is_healthy = (
            cpu['percent'] < 90 and
            memory['percent'] < 90 and
            model['loaded'] and
            (not gpu['available'] or gpu['utilization_percent'] < 95)
        )

        warnings = []
        if cpu['percent'] >= 90:
            warnings.append('High CPU usage')
        if memory['percent'] >= 90:
            warnings.append('High memory usage')
        if gpu['available'] and gpu['utilization_percent'] >= 95:
            warnings.append('High GPU utilization')
        if not model['loaded']:
            warnings.append('Model not loaded')

        return {
            'status': 'healthy' if is_healthy else 'warning',
            'timestamp': datetime.now().isoformat(),
            'warnings': warnings
        }

    @cache_metric(cache_duration=3.0)
    def get_all_metrics(self) -> Dict[str, Any]:
        """Get all metrics in a single call."""
        return {
            'health': self.get_health_status(),
            'cpu': self.get_cpu_metrics(),
            'memory': self.get_memory_metrics(),
            'gpu': self.get_gpu_metrics(),
            'disk': self.get_disk_metrics(),
            'network': self.get_network_metrics(),
            'process': self.get_process_metrics(),
            'model': self.get_model_status(),
            'performance': self.get_performance_stats()
        }


# Global server monitor instance
_monitor = None

def get_monitor() -> ServerMonitor:
    """Get the global server monitor instance."""
    global _monitor
    if _monitor is None:
        _monitor = ServerMonitor()
    return _monitor
