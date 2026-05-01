from django.contrib import admin
from .models import StaffProfile


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_id', 'department', 'designation')
    search_fields = ('user__username', 'employee_id', 'department', 'designation')
    list_filter = ('department', 'designation')
