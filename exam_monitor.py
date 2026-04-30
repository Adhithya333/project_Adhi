"""
Real-time AI-based Exam Monitoring System
Detects face direction, eye gaze, and mobile phones to monitor student attention during exams.
"""

import cv2
import numpy as np
import time
import os
from datetime import datetime

try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

# Import MediaPipe Tasks (FaceLandmarker - replacement for deprecated solutions.face_mesh)
import mediapipe as mp
from mediapipe.tasks import python as mp_tasks
from mediapipe.tasks.python import vision

# Import YOLO for phone detection
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("Warning: ultralytics not installed. Phone detection will be disabled.")
    print("Install it with: pip install ultralytics")

# Path to face landmarker model (same 478 landmarks: 468 face + 10 iris)
_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"


def _get_model_path():
    """Return path to face_landmarker.task (project root or malpractice/)."""
    base = os.path.dirname(os.path.abspath(__file__))
    for path in [os.path.join(base, "..", "face_landmarker.task"), os.path.join(base, "face_landmarker.task")]:
        if os.path.exists(path):
            return path
    target = os.path.join(base, "..", "face_landmarker.task")
    raise FileNotFoundError(
        f"face_landmarker.task not found. Download from {_MODEL_URL} and save to: {os.path.abspath(target)}"
    )

# Face Mesh landmarks indices (MediaPipe uses 468 landmarks)
NOSE_TIP = 4
LEFT_CHEEK = 234
RIGHT_CHEEK = 454
LEFT_EYE_INNER = 33
LEFT_EYE_OUTER = 263
RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 133

# Iris landmarks for eye gaze detection
LEFT_IRIS = [474, 475, 476, 477]
RIGHT_IRIS = [469, 470, 471, 472]

# Thresholds for detection
FACE_TURN_THRESHOLD = 0.02
EYE_GAZE_THRESHOLD = 0.015
WARNING_TIME_SECONDS = 15
PHONE_DETECTION_CONFIDENCE = 0.25


class _LandmarkWrapper:
    """Adapter so FaceLandmarker result (list of landmarks) works with get_face_direction/get_eye_direction."""

    def __init__(self, landmark_list):
        self.landmark = landmark_list


class ExamMonitor:
    """Main class for exam monitoring system."""

    def __init__(self):
        """Initialize the exam monitoring system."""
        opts = vision.FaceLandmarkerOptions(
            base_options=mp_tasks.BaseOptions(model_asset_path=_get_model_path()),
            num_faces=2,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            running_mode=vision.RunningMode.IMAGE,
        )
        self.face_landmarker = vision.FaceLandmarker.create_from_options(opts)

        self.phone_model = None
        self.phone_detected = False
        self.phone_detection_start_time = None
        self.phone_warning_active = False

        if YOLO_AVAILABLE:
            try:
                self.phone_model = YOLO('yolov8n.pt')
            except Exception as e:
                print(f"Warning: Could not load phone detection model: {e}")
                self.phone_model = None

        self.face_away_start_time = None
        self.eyes_away_start_time = None
        self.current_face_direction = "CENTER"
        self.current_eye_direction = "CENTER"
        self.warning_active = False

        self.logs_dir = "logs"
        if not os.path.exists(self.logs_dir):
            os.makedirs(self.logs_dir)

        self.screenshot_count = 0

    def _get_landmarks_from_frame(self, rgb_frame):
        """Get face landmarks from RGB frame. Used by Django for frame-by-frame processing."""
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        result = self.face_landmarker.detect(mp_image)
        if result.face_landmarks and len(result.face_landmarks) > 0:
            return _LandmarkWrapper(result.face_landmarks[0])
        return None

    def get_face_direction(self, landmarks, frame_width, frame_height):
        """Detect face direction (LEFT, RIGHT, or CENTER) using nose tip and cheek positions."""
        try:
            nose_tip = landmarks.landmark[NOSE_TIP]
            left_cheek = landmarks.landmark[LEFT_CHEEK]
            right_cheek = landmarks.landmark[RIGHT_CHEEK]

            nose_x = nose_tip.x * frame_width
            left_cheek_x = left_cheek.x * frame_width
            right_cheek_x = right_cheek.x * frame_width

            nose_to_left = abs(nose_x - left_cheek_x)
            nose_to_right = abs(nose_x - right_cheek_x)

            diff_ratio = (nose_to_left - nose_to_right) / frame_width

            if diff_ratio > FACE_TURN_THRESHOLD:
                return "LEFT"
            elif diff_ratio < -FACE_TURN_THRESHOLD:
                return "RIGHT"
            else:
                return "CENTER"

        except Exception as e:
            print(f"Error in get_face_direction: {e}")
            return "CENTER"

    def get_eye_direction(self, landmarks, frame_width, frame_height):
        """Detect eye gaze direction (LEFT, RIGHT, or CENTER) using iris positions."""
        try:
            left_eye_inner = landmarks.landmark[LEFT_EYE_INNER]
            left_eye_outer = landmarks.landmark[LEFT_EYE_OUTER]
            right_eye_inner = landmarks.landmark[RIGHT_EYE_INNER]
            right_eye_outer = landmarks.landmark[RIGHT_EYE_OUTER]

            left_iris_center = np.mean([
                [landmarks.landmark[i].x * frame_width, landmarks.landmark[i].y * frame_height]
                for i in LEFT_IRIS
            ], axis=0)

            right_iris_center = np.mean([
                [landmarks.landmark[i].x * frame_width, landmarks.landmark[i].y * frame_height]
                for i in RIGHT_IRIS
            ], axis=0)

            left_eye_center_x = (left_eye_inner.x + left_eye_outer.x) / 2 * frame_width
            right_eye_center_x = (right_eye_inner.x + right_eye_outer.x) / 2 * frame_width

            left_iris_offset = left_iris_center[0] - left_eye_center_x
            right_iris_offset = right_iris_center[0] - right_eye_center_x

            avg_offset = (left_iris_offset + right_iris_offset) / 2

            eye_width = abs(left_eye_outer.x - left_eye_inner.x) * frame_width
            normalized_offset = avg_offset / eye_width if eye_width > 0 else 0

            if normalized_offset > EYE_GAZE_THRESHOLD:
                return "RIGHT"
            elif normalized_offset < -EYE_GAZE_THRESHOLD:
                return "LEFT"
            else:
                return "CENTER"

        except Exception as e:
            print(f"Error in get_eye_direction: {e}")
            return "CENTER"

    def update_timer(self, face_direction, eye_direction):
        """Update timer based on current face and eye directions."""
        current_time = time.time()

        if face_direction in ["LEFT", "RIGHT"]:
            if self.face_away_start_time is None:
                self.face_away_start_time = current_time
        else:
            if self.face_away_start_time is not None:
                self.face_away_start_time = None

        if eye_direction in ["LEFT", "RIGHT"]:
            if self.eyes_away_start_time is None:
                self.eyes_away_start_time = current_time
        else:
            if self.eyes_away_start_time is not None:
                self.eyes_away_start_time = None

    def get_elapsed_time(self):
        """Get elapsed time since face/eyes started looking away."""
        current_time = time.time()
        max_elapsed = 0

        if self.face_away_start_time is not None:
            elapsed = current_time - self.face_away_start_time
            max_elapsed = max(max_elapsed, elapsed)

        if self.eyes_away_start_time is not None:
            elapsed = current_time - self.eyes_away_start_time
            max_elapsed = max(max_elapsed, elapsed)

        return max_elapsed

    def check_warning(self):
        """Check if warning should be triggered based on elapsed time."""
        elapsed = self.get_elapsed_time()
        should_warn = elapsed >= WARNING_TIME_SECONDS

        if should_warn and not self.warning_active:
            self.trigger_warning()

        self.warning_active = should_warn
        return should_warn

    def trigger_warning(self):
        """Trigger warning actions: beep, log, and screenshot."""
        try:
            if HAS_WINSOUND:
                winsound.Beep(1000, 500)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] WARNING: Student looking away - Face: {self.current_face_direction}, Eyes: {self.current_eye_direction}\n"

            log_file = os.path.join(self.logs_dir, "warnings.log")
            with open(log_file, "a") as f:
                f.write(log_message)

        except Exception as e:
            print(f"Error triggering warning: {e}")

    def detect_phone(self, frame):
        """Detect mobile phones in the frame using YOLO."""
        if not YOLO_AVAILABLE or self.phone_model is None:
            return False, []

        try:
            results = self.phone_model(frame, verbose=False, conf=PHONE_DETECTION_CONFIDENCE)

            phone_detected = False
            phone_boxes = []

            for result in results:
                boxes = result.boxes
                for box in boxes:
                    class_id = int(box.cls[0])
                    conf = float(box.conf[0])

                    if class_id == 67:
                        phone_detected = True
                        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                        phone_boxes.append((int(x1), int(y1), int(x2), int(y2), conf))

            return phone_detected, phone_boxes

        except Exception as e:
            print(f"Error in phone detection: {e}")
            import traceback
            traceback.print_exc()
            return False, []

    def update_phone_timer(self, phone_detected):
        """Update timer for phone detection."""
        current_time = time.time()

        if phone_detected:
            if self.phone_detection_start_time is None:
                self.phone_detection_start_time = current_time
        else:
            if self.phone_detection_start_time is not None:
                self.phone_detection_start_time = None

    def check_phone_warning(self):
        """Check if phone warning should be triggered."""
        if self.phone_detection_start_time is None:
            self.phone_warning_active = False
            return False

        elapsed = time.time() - self.phone_detection_start_time

        should_warn = elapsed > 0.5

        if should_warn and not self.phone_warning_active:
            self.trigger_phone_warning()

        self.phone_warning_active = should_warn
        return should_warn

    def trigger_phone_warning(self):
        """Trigger phone detection warning actions."""
        try:
            if HAS_WINSOUND:
                winsound.Beep(1500, 500)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_message = f"[{timestamp}] WARNING: Mobile phone detected in classroom!\n"

            log_file = os.path.join(self.logs_dir, "warnings.log")
            with open(log_file, "a") as f:
                f.write(log_message)

        except Exception as e:
            print(f"Error triggering phone warning: {e}")

    def save_screenshot(self, frame, phone_detected=False):
        """Save screenshot when warning is triggered."""
        try:
            self.screenshot_count += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = "phone_" if phone_detected else "warning_"
            filename = os.path.join(self.logs_dir, f"{prefix}{timestamp}_{self.screenshot_count}.jpg")
            cv2.imwrite(filename, frame)
        except Exception as e:
            print(f"Error saving screenshot: {e}")

    def run(self):
        """Main loop to run the exam monitoring system (standalone desktop mode)."""
        cap = cv2.VideoCapture(0)

        if not cap.isOpened():
            print("Error: Could not open webcam")
            return

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        print("Exam Monitoring System Started")
        print("Features: Face detection, Eye gaze tracking, Phone detection")
        print("Press 'q' to quit")
        print("-" * 60)

        screenshot_saved = False
        self.phone_screenshot_saved = False

        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("Error: Could not read frame")
                    break

                frame = cv2.flip(frame, 1)

                phone_detected, phone_boxes = self.detect_phone(frame)
                self.phone_detected = phone_detected

                if phone_detected:
                    for x1, y1, x2, y2, conf in phone_boxes:
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 3)
                        label = f"Phone {conf:.2f}"
                        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
                        label_y = max(y1 - 10, label_size[1])
                        cv2.rectangle(frame, (x1, label_y - label_size[1] - 5),
                                     (x1 + label_size[0], label_y + 5), (0, 0, 255), -1)
                        cv2.putText(frame, label, (x1, label_y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                self.update_phone_timer(phone_detected)
                self.check_phone_warning()

                if self.phone_warning_active and phone_detected:
                    if not hasattr(self, 'phone_screenshot_saved') or not self.phone_screenshot_saved:
                        self.save_screenshot(frame, phone_detected=True)
                        self.phone_screenshot_saved = True
                else:
                    self.phone_screenshot_saved = False

                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                result = self.face_landmarker.detect(mp_image)

                if result.face_landmarks and len(result.face_landmarks) > 0:
                    face_landmarks = _LandmarkWrapper(result.face_landmarks[0])

                    frame_height, frame_width = frame.shape[:2]

                    face_direction = self.get_face_direction(face_landmarks, frame_width, frame_height)
                    eye_direction = self.get_eye_direction(face_landmarks, frame_width, frame_height)

                    self.current_face_direction = face_direction
                    self.current_eye_direction = eye_direction

                    self.update_timer(face_direction, eye_direction)
                    self.check_warning()

                    elapsed_time = self.get_elapsed_time()

                    if self.warning_active and not screenshot_saved:
                        self.save_screenshot(frame)
                        screenshot_saved = True
                    elif not self.warning_active:
                        screenshot_saved = False
                else:
                    face_direction = "NO FACE"
                    eye_direction = "NO FACE"
                    elapsed_time = 0
                    self.face_away_start_time = None
                    self.eyes_away_start_time = None
                    self.warning_active = False
                    screenshot_saved = False

                panel_height = 180
                overlay = frame.copy()
                cv2.rectangle(overlay, (10, 10), (400, panel_height), (0, 0, 0), -1)
                cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

                font = cv2.FONT_HERSHEY_SIMPLEX
                font_scale = 0.6
                thickness = 2
                y_offset = 35
                line_height = 30

                face_color = (0, 255, 0) if face_direction == "CENTER" else (0, 165, 255)
                cv2.putText(frame, f"Face Direction: {face_direction}", (20, y_offset), font, font_scale, face_color, thickness)
                eye_color = (0, 255, 0) if eye_direction == "CENTER" else (0, 165, 255)
                cv2.putText(frame, f"Eye Direction: {eye_direction}", (20, y_offset + line_height), font, font_scale, eye_color, thickness)
                phone_status = "DETECTED" if self.phone_detected else "NOT DETECTED"
                phone_color = (0, 0, 255) if self.phone_detected else (0, 255, 0)
                cv2.putText(frame, f"Phone: {phone_status}", (20, y_offset + line_height * 2), font, font_scale, phone_color, thickness)
                timer_color = (0, 255, 0) if elapsed_time < WARNING_TIME_SECONDS else (0, 0, 255)
                cv2.putText(frame, f"Timer: {elapsed_time:.1f}s / {WARNING_TIME_SECONDS}s", (20, y_offset + line_height * 3), font, font_scale, timer_color, thickness)
                if self.warning_active or self.phone_warning_active:
                    cv2.putText(frame, "WARNING ACTIVE", (20, y_offset + line_height * 4), font, font_scale, (0, 0, 255), thickness)

                if self.warning_active or self.phone_warning_active:
                    cv2.rectangle(frame, (0, 0), (frame.shape[1] - 1, frame.shape[0] - 1), (0, 0, 255), 10)

                cv2.imshow('Exam Monitoring System', frame)

                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        except Exception as e:
            print(f"Error in main loop: {e}")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            print("System shutdown complete")


def main():
    """Main entry point."""
    try:
        monitor = ExamMonitor()
        monitor.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
