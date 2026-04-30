from django.db import models
from django.utils import timezone

"""
Models that store live AI monitoring data and individual malpractice incidents.

`ExamSession` aggregates per-attempt counters, while `MalpracticeEvent`
captures detailed, timestamped events (often with evidence snapshots).
"""


class ExamSession(models.Model):
    """Live exam session linked to an `ExamAttempt`, tracking AI counters."""
    exam_attempt = models.OneToOneField(
        'exams.ExamAttempt',
        on_delete=models.CASCADE,
        related_name='session'
    )
    last_heartbeat = models.DateTimeField(auto_now=True)
    face_detected_count = models.PositiveIntegerField(default=0)
    no_face_count = models.PositiveIntegerField(default=0)
    multiple_faces_count = models.PositiveIntegerField(default=0)
    tab_switch_count = models.PositiveIntegerField(default=0)
    looking_away_count = models.PositiveIntegerField(default=0)
    phone_usage_count = models.PositiveIntegerField(default=0)
    last_snapshot = models.ImageField(upload_to='live_snapshots/', blank=True, null=True)
    
    def __str__(self):
        return f"Session for {self.exam_attempt}"


class MalpracticeEvent(models.Model):
    """Single malpractice incident detected during an exam session."""
    EVENT_TYPE_CHOICES = (
        ('multiple_faces', 'Multiple Faces Detected'),
        ('no_face', 'No Face Detected'),
        ('looking_away', 'Looking Away from Screen'),
        ('tab_switch', 'Tab Switched'),
        ('copy_paste', 'Copy/Paste Attempted'),
        ('fullscreen_exit', 'Fullscreen Exited'),
        ('phone_usage', 'Phone/Mobile Detected'),
    )
    SEVERITY_CHOICES = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )
    
    session = models.ForeignKey(
        ExamSession,
        on_delete=models.CASCADE,
        related_name='events'
    )
    event_type = models.CharField(max_length=50, choices=EVENT_TYPE_CHOICES)
    screenshot = models.ImageField(upload_to='malpractice/', blank=True, null=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    details = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.timestamp}"
