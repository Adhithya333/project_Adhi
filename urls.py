from django.urls import path
from . import views

"""
URL routes for staff dashboards, user management, and student performance views.
"""

app_name = 'staff'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('users/', views.user_list_view, name='user_list'),
    path('users/create/', views.user_create_view, name='user_create'),
    path('users/<int:user_id>/edit/', views.user_edit_view, name='user_edit'),
    path('students/', views.student_list_view, name='student_list'),
    path('students/performance/', views.student_performance_view, name='student_performance'),
    path('students/<int:student_id>/', views.student_detail_view, name='student_detail'),
]
