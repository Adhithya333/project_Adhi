from django.db import models
from django.conf import settings

"""
Additional profile information for staff users.
"""


class StaffProfile(models.Model):
    """Per-staff profile fields (employee ID, department, designation)."""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='staff_profile')
    employee_id = models.CharField(max_length=50, unique=True)
    department = models.CharField(max_length=100, blank=True)
    designation = models.CharField(max_length=100, blank=True)
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"
