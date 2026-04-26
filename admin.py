from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User
from django.contrib import messages
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, redirect
from django.utils.html import format_html


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'user_type', 'first_name', 'last_name', 'is_staff', 'is_active', 'promote_actions')
    list_filter = ('user_type', 'is_staff', 'is_active', 'is_superuser')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'phone_number', 'profile_picture')}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Additional Info', {'fields': ('user_type', 'phone_number', 'profile_picture')}),
    )
    actions = ['promote_to_staff']

    def promote_to_staff(self, request, queryset):
        updated = queryset.update(user_type='staff', is_staff=True, is_active=True)
        self.message_user(request, f"{updated} user(s) promoted to staff and activated.", level=messages.SUCCESS)
    promote_to_staff.short_description = "Promote selected users to Staff"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('promote-staff/<int:user_id>/', self.admin_site.admin_view(self.promote_to_staff_view), name='accounts_user_promote_staff'),
        ]
        return custom_urls + urls

    def promote_actions(self, obj):
        promote_staff_url = reverse('admin:accounts_user_promote_staff', args=[obj.pk])
        return format_html('<a class="button" href="{}">Staff</a>', promote_staff_url)
    promote_actions.short_description = 'Promote'

    def promote_to_staff_view(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        if request.method == 'POST':
            user.user_type = 'staff'
            user.is_staff = True
            user.is_active = True
            user.save()
            self.message_user(request, f"User '{user.username}' promoted to staff and activated.", level=messages.SUCCESS)
            return redirect(request.META.get('HTTP_REFERER', reverse('admin:accounts_user_changelist')))
        # GET: show confirmation page with POST form
        from django.template.response import TemplateResponse
        context = {
            **self.admin_site.each_context(request),
            'opts': self.model._meta,
            'user_obj': user,
            'title': 'Confirm promote to staff',
        }
        return TemplateResponse(request, 'admin/accounts/user/promote_confirm.html', context)
