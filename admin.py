from django.contrib import admin
from .models import StudentProfile


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_id', 'course', 'year', 'semester')
    search_fields = ('user__username', 'student_id', 'course')
    list_filter = ('year', 'semester', 'course')
