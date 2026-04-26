from django.urls import path

from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('exams/', views.admin_exams_view, name='admin_exams'),
    path('exams/<int:pk>/questions/', views.admin_exam_questions_view, name='admin_exam_questions'),
    path('exams/<int:pk>/delete/', views.admin_exam_delete_view, name='admin_exam_delete'),
    path('performance/', views.admin_student_performance_view, name='admin_student_performance'),
    path('users/<int:user_id>/toggle-active/', views.user_toggle_active_view, name='user_toggle_active'),
]
