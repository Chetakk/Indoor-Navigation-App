"""
Download YOLOv8 models trained on Open Images v7 dataset.

This script downloads official YOLOv8-OIV7 models from Ultralytics.
"""

from ultralytics import YOLO
import sys


def download_model(model_name):
    """
    Download a YOLOv8 model.

    Args:
        model_name: Model identifier (e.g., 'yolov8n-oiv7.pt')
    """
    print(f"\n{'='*60}")
    print(f"Downloading {model_name}")
    print(f"{'='*60}")

    try:
        # Loading with Ultralytics will auto-download if not found
        print(f"Downloading from Ultralytics...")
        model = YOLO(model_name)
        print(f"\nSuccess! Model downloaded and loaded.")
        print(f"Classes: {len(model.names)}")
        print(f"Model info: {model.model}")

    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def main():
    print("YOLOv8 Open Images v7 Model Downloader")
    print("="*60)

    models = {
        'n': 'yolov8n-oiv7.pt',  # Nano: 6 MB, fastest
        's': 'yolov8s-oiv7.pt',  # Small: 22 MB
        'm': 'yolov8m-oiv7.pt',  # Medium: 52 MB
        'l': 'yolov8l-oiv7.pt',  # Large: 88 MB
        'x': 'yolov8x-oiv7.pt',  # Extra-large: 136 MB, most accurate
    }

    print("\nAvailable models:")
    for key, model_name in models.items():
        print(f"  {key}) {model_name}")

    choice = input("\nSelect model to download (n/s/m/l/x) or 'all': ").strip().lower()

    if choice == 'all':
        for model_name in models.values():
            download_model(model_name)
    elif choice in models:
        download_model(models[choice])
    else:
        print("Invalid choice!")
        sys.exit(1)


if __name__ == '__main__':
    main()
