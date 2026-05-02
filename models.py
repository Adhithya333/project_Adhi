from django.db import models
from django.conf import settings

"""
Additional profile information for student users.
"""


class StudentProfile(models.Model):
    """Per-student academic profile fields (ID, course, year, semester)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='student_profile')
    student_id = models.CharField(max_length=50, unique=True)
    course = models.CharField(max_length=100, blank=True)
    year = models.IntegerField(default=1)
    semester = models.IntegerField(default=1)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.student_id}"
