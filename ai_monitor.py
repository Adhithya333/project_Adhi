"""
Django integration for exam monitoring.
Uses malpractice.exam_monitor (MediaPipe Face Mesh + YOLO) for all AI detection.
Browser captures webcam frames; server runs detection on each frame.
"""

import os
import threading

import cv2
import numpy as np
import mediapipe as mp

from malpractice.exam_monitor import ExamMonitor, _LandmarkWrapper

# Per-attempt monitors for frame processing (attempt_id -> monitor instance)
_frame_monitors = {}
_monitors_lock = threading.Lock()


class DjangoExamMonitor(ExamMonitor):
    """
    Your ExamMonitor with Django integration.
    Overrides trigger_warning and trigger_phone_warning to save to DB instead of beep/log.
    """

    def __init__(self, attempt_id):
        super().__init__()
        self.attempt_id = attempt_id

    def _save_event_to_db(self, event_type, frame, details=None):
        try:
            from django.core.files.base import ContentFile
            from malpractice.models import ExamSession, MalpracticeEvent
            from exams.models import ExamAttempt
            from datetime import datetime

            attempt = ExamAttempt.objects.filter(pk=self.attempt_id, status='in_progress').first()
            if not attempt:
                return

            session, _ = ExamSession.objects.get_or_create(exam_attempt=attempt)

            if event_type == 'phone_usage':
                session.phone_usage_count += 1
                severity = 'high'
            elif event_type == 'multiple_faces':
                session.multiple_faces_count += 1
                severity = 'high'
            elif event_type == 'no_face':
                session.no_face_count += 1
                severity = 'medium'
            else:
                # looking_away: do NOT increment here - heartbeat already updates looking_away_count
                severity = 'low'
            session.save()

            event = MalpracticeEvent.objects.create(
                session=session,
                event_type=event_type,
                severity=severity,
                details=details or {}
            )

            if frame is not None:
                self.screenshot_count += 1
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                prefix = event_type + "_"
                filename = f"{prefix}{timestamp}_{self.screenshot_count}.jpg"
                _, buffer = cv2.imencode('.jpg', frame)
                content = ContentFile(buffer.tobytes())
                event.screenshot.save(filename, content, save=True)
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(
                "Failed to save malpractice event to DB: %s", e, exc_info=True
            )

    def trigger_warning(self):
        pass  # We save in process_frame with screenshot

    def trigger_phone_warning(self):
        pass  # We save in process_frame with screenshot


def get_or_create_monitor(attempt_id):
    """Get or create a monitor for the given attempt."""
    with _monitors_lock:
        if attempt_id not in _frame_monitors:
            _frame_monitors[attempt_id] = DjangoExamMonitor(attempt_id)
        return _frame_monitors[attempt_id]


def process_frame(attempt_id, image_bytes):
    """
    Process one frame: runs exam_monitor detection (face, eyes, phone).
    Returns dict with face_direction, eye_direction, face_count, phone_detected, looking_away.
    """
    monitor = get_or_create_monitor(attempt_id)
    frame = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return {"face_count": 0, "looking_away": False, "face_direction": "NO FACE", "eye_direction": "NO FACE", "phone_detected": False}

    frame = cv2.flip(frame, 1)

    # YOUR detect_phone logic
    phone_detected, phone_boxes = monitor.detect_phone(frame)
    monitor.phone_detected = phone_detected
    monitor.update_phone_timer(phone_detected)
    monitor.check_phone_warning()

    # Count one phone incident per continuous phone-visibility episode.
    # This avoids inflated counts when the phone stays visible across many frames.
    if monitor.phone_warning_active and phone_detected:
        if not getattr(monitor, '_phone_event_saved', False):
            monitor._save_event_to_db('phone_usage', frame, {"source": "ai_monitor"})
            monitor._phone_event_saved = True
    else:
        monitor._phone_event_saved = False

    # Face and eye detection (MediaPipe Face Mesh) - num_faces=2 to detect multiple faces
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    result = monitor.face_landmarker.detect(mp_image)

    face_count = 0
    landmarks = None
    if result.face_landmarks and len(result.face_landmarks) > 0:
        face_count = len(result.face_landmarks)
        landmarks = _LandmarkWrapper(result.face_landmarks[0])

    if landmarks:
        frame_height, frame_width = frame.shape[:2]
        face_direction = monitor.get_face_direction(landmarks, frame_width, frame_height)
        eye_direction = monitor.get_eye_direction(landmarks, frame_width, frame_height)
        monitor.current_face_direction = face_direction
        monitor.current_eye_direction = eye_direction
        monitor.update_timer(face_direction, eye_direction)
        monitor.check_warning()
        elapsed_time = monitor.get_elapsed_time()

        if monitor.warning_active:
            if not getattr(monitor, '_screenshot_saved', False):
                monitor._save_event_to_db(
                    'looking_away',
                    frame,
                    {"face": face_direction, "eyes": eye_direction}
                )
                monitor._screenshot_saved = True
        else:
            monitor._screenshot_saved = False
        if face_count <= 1:
            monitor._multi_face_screenshot_saved = False

        looking_away = monitor.warning_active

        if face_count > 1 and not getattr(monitor, '_multi_face_screenshot_saved', False):
            monitor._save_event_to_db('multiple_faces', frame, {"count": face_count})
            monitor._multi_face_screenshot_saved = True
    else:
        if not getattr(monitor, '_no_face_screenshot_saved', False):
            monitor._save_event_to_db('no_face', frame, {"source": "ai_monitor"})
            monitor._no_face_screenshot_saved = True
        face_direction = "NO FACE"
        eye_direction = "NO FACE"
        monitor.face_away_start_time = None
        monitor.eyes_away_start_time = None
        monitor.warning_active = False
        monitor._screenshot_saved = False
        monitor._multi_face_screenshot_saved = False
        looking_away = False
        face_count = 0
        elapsed_time = 0
    return {
        "face_count": face_count,
        "looking_away": looking_away,
        "face_direction": face_direction,
        "eye_direction": eye_direction,
        "phone_detected": monitor.phone_detected,
        "elapsed_time": elapsed_time,
        "warning_active": monitor.warning_active,
        "phone_warning_active": monitor.phone_warning_active,
    }


def stop_monitor(attempt_id):
    """Remove monitor for attempt (e.g. when exam submitted)."""
    with _monitors_lock:
        if attempt_id in _frame_monitors:
            _frame_monitors.pop(attempt_id)
            return True
    return False


def start_monitor(attempt_id):
    """No-op for frame-based flow - monitor created on first frame."""
    return True


def is_monitor_running(attempt_id):
    with _monitors_lock:
        return attempt_id in _frame_monitors
