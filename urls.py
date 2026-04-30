from django.urls import path
from . import views

"""
URL routes for AI malpractice monitoring, snapshots, and staff reports.
"""

app_name = 'malpractice'

urlpatterns = [
    # Endpoints used by the exam room JavaScript for AI monitoring.
    path('start/<int:attempt_id>/', views.start_monitoring, name='start_monitoring'),
    path('stop/<int:attempt_id>/', views.stop_monitoring, name='stop_monitoring'),
    path('analyze-frame/<int:attempt_id>/', views.analyze_frame, name='analyze_frame'),
    path('heartbeat/', views.malpractice_heartbeat, name='heartbeat'),
    path('event/', views.malpractice_event, name='event'),
    path('snapshot/<int:attempt_id>/', views.malpractice_snapshot, name='snapshot'),
    path('snapshot/<int:attempt_id>/image/', views.snapshot_image, name='snapshot_image'),
    # Staff-facing reports and live monitoring dashboards/APIs.
    path('reports/', views.malpractice_reports, name='reports'),
    path('reports/<int:attempt_id>/', views.malpractice_report_detail, name='report_detail'),
    path('live/<int:exam_id>/', views.live_monitoring, name='live_monitoring'),
    path('live/<int:exam_id>/api/', views.live_monitoring_api, name='live_monitoring_api'),
    path('exam-monitor/', views.exam_monitor_view, name='exam_monitor'),
    path('exam-monitor/exam/<int:exam_id>/', views.exam_monitor_exam_view, name='exam_monitor_exam'),
    path('exam-monitor/room/<int:attempt_id>/', views.exam_monitor_room_view, name='exam_monitor_room'),
]
