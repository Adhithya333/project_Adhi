from django.contrib.auth.models import AbstractUser
from django.db import models

"""
Custom authentication models for the project.

This module defines the `User` model that extends Django's built-in
`AbstractUser` to add role information and profile fields used across
student, staff, and coordinator flows.
"""


class User(AbstractUser):
    """
    Application user with a `user_type` flag and basic contact/profile fields.

    The `user_type` field is used to distinguish between students and staff
    throughout the application (dashboards, permissions, and navigation).
    """
    USER_TYPE_CHOICES = (
        ('student', 'Student'),
        ('staff', 'Staff'),
    )
    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES)
    phone_number = models.CharField(max_length=15, blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.username} ({self.get_user_type_display()})"

