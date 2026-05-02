from django.urls import path
from . import views

"""
URL routes for student dashboards, profile management, and results pages.
"""

app_name = 'student'

urlpatterns = [
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('results/', views.results_view, name='results'),
    path('profile/', views.profile_edit_view, name='profile'),
    path('results/<int:attempt_id>/', views.result_detail_view, name='result_detail'),
]
