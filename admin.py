from django.contrib import admin
from .models import ExamSession, MalpracticeEvent


@admin.register(ExamSession)
class ExamSessionAdmin(admin.ModelAdmin):
    list_display = ['exam_attempt', 'last_heartbeat', 'multiple_faces_count', 'no_face_count', 'tab_switch_count']


@admin.register(MalpracticeEvent)
class MalpracticeEventAdmin(admin.ModelAdmin):
    list_display = ['session', 'event_type', 'severity', 'timestamp']
    list_filter = ['event_type', 'severity']
