"""
URL configuration for exam_malpractice project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('admin-console/', include('admin_dashboard.urls')),
    path('', include('accounts.urls')),
    path('student/', include('student.urls')),
    path('staff/', include('staff.urls')),
    path('exams/', include('exams.urls')),
    path('malpractice/', include('malpractice.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers (use views that render 404.html / 500.html)
handler404 = 'accounts.views.page_not_found_view'
handler500 = 'accounts.views.server_error_view'
