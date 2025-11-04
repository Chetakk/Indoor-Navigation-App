# detector_utils.py - Object detection utilities
import cv2
import numpy as np
import math
from kivy.logger import Logger

class DetectionUtils:
    """Utility functions for object detection"""
    
    @staticmethod
    def preprocess_image(image, target_size=(416, 416)):
        """Preprocess image for detection"""
        try:
            # Resize image
            resized = cv2.resize(image, target_size)
            
            # Normalize pixel values
            normalized = resized.astype(np.float32) / 255.0
            
            # Add batch dimension
            batched = np.expand_dims(normalized, axis=0)
            
            return batched
        except Exception as e:
            Logger.error(f"Image preprocessing error: {e}")
            return None
    
    @staticmethod
    def apply_nms(boxes, scores, score_threshold=0.5, nms_threshold=0.4):
        """Apply Non-Maximum Suppression"""
        try:
            # Convert to format expected by cv2.dnn.NMSBoxes
            boxes_list = boxes.tolist()
            scores_list = scores.tolist()
            
            # Apply NMS
            indices = cv2.dnn.NMSBoxes(
                boxes_list, 
                scores_list, 
                score_threshold, 
                nms_threshold
            )
            
            if len(indices) > 0:
                return indices.flatten()
            else:
                return []
                
        except Exception as e:
            Logger.error(f"NMS error: {e}")
            return []
    
    @staticmethod
    def get_object_direction(bbox, image_width, image_height):
        """Calculate object direction based on bounding box position"""
        x1, y1, x2, y2 = bbox
        
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        
        # Normalize coordinates
        norm_x = center_x / image_width
        norm_y = center_y / image_height
        
        # Determine horizontal direction
        if norm_x < 0.2:
            horizontal = "far left"
        elif norm_x < 0.35:
            horizontal = "left"
        elif norm_x < 0.45:
            horizontal = "slightly left"
        elif norm_x < 0.55:
            horizontal = "center"
        elif norm_x < 0.65:
            horizontal = "slightly right"
        elif norm_x < 0.8:
            horizontal = "right"
        else:
            horizontal = "far right"
        
        # Determine vertical direction
        if norm_y < 0.3:
            vertical = "above"
        elif norm_y < 0.7:
            vertical = "level"
        else:
            vertical = "below"
        
        # Combine directions
        if horizontal == "center":
            if vertical == "above":
                direction = "ahead and above"
            elif vertical == "below":
                direction = "ahead and below"
            else:
                direction = "directly ahead"
        else:
            if vertical == "above":
                direction = f"{horizontal} and above"
            elif vertical == "below":
                direction = f"{horizontal} and below"
            else:
                direction = horizontal
        
        return {
            'direction': direction,
            'horizontal': horizontal,
            'vertical': vertical,
            'coordinates': {'x': norm_x, 'y': norm_y}
        }
    
    @staticmethod
    def estimate_distance(bbox, image_width, image_height, class_name=None):
        """Estimate object distance based on bounding box size"""
        x1, y1, x2, y2 = bbox
        width = x2 - x1
        height = y2 - y1
        area = width * height
        
        image_area = image_width * image_height
        object_ratio = area / image_area
        
        # Distance categories based on object size ratio
        if object_ratio > 0.3:
            distance = "very close"
            category = "immediate"
        elif object_ratio > 0.15:
            distance = "close"
            category = "near"
        elif object_ratio > 0.05:
            distance = "medium distance"
            category = "medium"
        elif object_ratio > 0.01:
            distance = "far"
            category = "far"
        else:
            distance = "very far"
            category = "distant"
        
        return {
            'distance': distance,
            'category': category,
            'ratio': object_ratio,
            'area': area
        }
    
    @staticmethod
    def rotate_image(image, angle):
        """Rotate image by specified angle"""
        if angle == 0:
            return image
        
        try:
            height, width = image.shape[:2]
            center = (width // 2, height // 2)
            
            # Get rotation matrix
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            
            # Calculate new image dimensions
            cos = np.abs(rotation_matrix[0, 0])
            sin = np.abs(rotation_matrix[0, 1])
            
            new_width = int((height * sin) + (width * cos))
            new_height = int((height * cos) + (width * sin))
            
            # Adjust rotation matrix for new center
            rotation_matrix[0, 2] += (new_width / 2) - center[0]
            rotation_matrix[1, 2] += (new_height / 2) - center[1]
            
            # Perform rotation
            rotated = cv2.warpAffine(image, rotation_matrix, (new_width, new_height))
            return rotated
            
        except Exception as e:
            Logger.error(f"Image rotation error: {e}")
            return image
    
    @staticmethod
    def draw_detection_boxes(image, detections):
        """Draw detection boxes and labels on image"""
        try:
            for detection in detections:
                bbox = detection['bbox']
                class_name = detection['class_name']
                confidence = detection['confidence']
                
                x1, y1, x2, y2 = map(int, bbox)
                
                # Color based on confidence
                if confidence > 0.8:
                    color = (0, 255, 0)  # Green for high confidence
                elif confidence > 0.6:
                    color = (0, 255, 255)  # Yellow for medium confidence
                else:
                    color = (0, 0, 255)  # Red for low confidence
                
                # Draw bounding box
                cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
                
                # Draw label
                label = f"{class_name} {int(confidence * 100)}%"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[0]
                
                # Label background
                cv2.rectangle(
                    image, 
                    (x1, y1 - label_size[1] - 10), 
                    (x1 + label_size[0], y1), 
                    color, 
                    -1
                )
                
                # Label text
                cv2.putText(
                    image, 
                    label, 
                    (x1, y1 - 5), 
                    cv2.FONT_HERSHEY_SIMPLEX, 
                    0.7, 
                    (255, 255, 255), 
                    2
                )
            
            return image
            
        except Exception as e:
            Logger.error(f"Drawing detection boxes error: {e}")
            return image

class PerformanceMonitor:
    """Monitor app performance"""
    
    def __init__(self):
        self.frame_times = []
        self.max_samples = 30
        
    def add_frame_time(self, frame_time):
        """Add frame processing time"""
        self.frame_times.append(frame_time)
        if len(self.frame_times) > self.max_samples:
            self.frame_times.pop(0)
    
    def get_avg_fps(self):
        """Get average FPS"""
        if not self.frame_times:
            return 0
        
        avg_time = sum(self.frame_times) / len(self.frame_times)
        return 1.0 / avg_time if avg_time > 0 else 0
    
    def get_min_max_fps(self):
        """Get min and max FPS"""
        if not self.frame_times:
            return 0, 0
        
        min_fps = 1.0 / max(self.frame_times) if max(self.frame_times) > 0 else 0
        max_fps = 1.0 / min(self.frame_times) if min(self.frame_times) > 0 else 0
        
        return min_fps, max_fps
