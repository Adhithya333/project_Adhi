from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from exams.models import Exam, ExamAttempt
from exams.services.student_performance_aggregate import get_student_performance_rows
from exams.views import _get_ended_exam_ids
from malpractice.models import MalpracticeEvent
from accounts.forms_user import StaffUserCreateForm, StaffUserEditForm

"""
Staff- and admin-facing views: dashboards, user management, and student analytics.
"""

User = get_user_model()


def _can_access_staff_pages(user):
    """Return True for users allowed to access staff-facing pages."""
    return bool(user and (user.is_superuser or user.user_type == 'staff'))


def _exam_can_live_monitor(exam):
    """
    Return True when an exam should show the live monitor action.

    Live monitoring is useful for active or upcoming exams, and should be hidden
    for completed/past exams.
    """
    now = timezone.now()
    if exam.status == 'completed':
        return False
    end_time = exam.end_time
    if end_time is None and exam.start_time:
        end_time = exam.start_time + timedelta(minutes=exam.duration_minutes)
    if end_time and end_time < now:
        return False
    return True


def _get_manageable_user_types(request):
    """
    Return which user types the current request user is allowed to manage.

    Superusers can manage both students and staff; regular staff do not
    manage users directly (only view students via other views).
    """
    if request.user.is_superuser:
        return ['student', 'staff']
    return []


@login_required
def dashboard_view(request):
    if not _can_access_staff_pages(request.user):
        raise PermissionDenied("You don't have permission to access this page.")
    
    all_exams = Exam.objects.all()
    current_time = timezone.now()
    ended_ids = _get_ended_exam_ids(current_time)
    # Align with exams exam_list (staff): Live & Upcoming — not raw status='active'
    # (time-ended exams often remain scheduled/active in DB until manually completed)
    live_and_upcoming = Exam.objects.filter(
        status__in=['scheduled', 'active']
    ).exclude(status='completed').exclude(id__in=ended_ids)
    active_count = live_and_upcoming.count()

    exams = all_exams.exclude(status='completed').order_by('-created_at')[:5]
    recent_exam_rows = [
        {'exam': exam, 'can_live_monitor': _exam_can_live_monitor(exam)}
        for exam in exams
    ]
    flagged = ExamAttempt.objects.filter(status='flagged').count()
    total_events = MalpracticeEvent.objects.count()
    
    context = {
        'user': request.user,
        'exams': exams,
        'recent_exam_rows': recent_exam_rows,
        'exam_count': all_exams.count(),
        'active_count': active_count,
        'flagged_count': flagged,
        'total_events': total_events,
    }
    return render(request, 'staff/dashboard.html', context)


@login_required
def user_list_view(request):
    """List users (admin only). Staff manages students via student_list."""
    allowed = _get_manageable_user_types(request)
    if not allowed:
        raise PermissionDenied("You don't have permission to manage users.")
    users = User.objects.filter(user_type__in=allowed, is_superuser=False).order_by('-date_joined')
    context = {'users': users}
    return render(request, 'staff/user_list.html', context)


@login_required
def user_create_view(request):
    """Create a user (admin only). Staff cannot create users."""
    allowed = _get_manageable_user_types(request)
    if not allowed:
        raise PermissionDenied("You don't have permission to create users.")
    if request.method == 'POST':
        form = StaffUserCreateForm(request.POST, allowed_user_types=allowed)
        if form.is_valid():
            form.save()
            messages.success(request, 'User account created successfully.')
            return redirect('staff:user_list')
    else:
        form = StaffUserCreateForm(allowed_user_types=allowed)
    context = {'form': form, 'title': 'Create User'}
    return render(request, 'staff/user_form.html', context)


@login_required
def user_edit_view(request, user_id):
    """Edit a user (admin only). Staff cannot edit users."""
    allowed = _get_manageable_user_types(request)
    if not allowed:
        raise PermissionDenied("You don't have permission to edit users.")
    user_obj = get_object_or_404(User, pk=user_id, user_type__in=allowed, is_superuser=False)
    if request.method == 'POST':
        form = StaffUserEditForm(request.POST, instance=user_obj, allowed_user_types=allowed)
        if form.is_valid():
            form.save()
            messages.success(request, 'User account updated successfully.')
            return redirect('staff:user_list')
    else:
        form = StaffUserEditForm(instance=user_obj, allowed_user_types=allowed)
    context = {'form': form, 'user_obj': user_obj, 'title': 'Edit User'}
    return render(request, 'staff/user_form.html', context)


@login_required
def student_list_view(request):
    """Staff: List all students."""
    if not _can_access_staff_pages(request.user):
        raise PermissionDenied("You don't have permission to access this page.")

    students = User.objects.filter(user_type='student', is_superuser=False).order_by('username')
    context = {'students': students}
    return render(request, 'staff/student_list.html', context)


@login_required
def student_performance_view(request):
    """Staff: View student performance (attempts, malpractice) across all exams."""
    if not _can_access_staff_pages(request.user):
        raise PermissionDenied("You don't have permission to access this page.")
    
    context = {'performances': get_student_performance_rows()}
    return render(request, 'staff/student_performance.html', context)


@login_required
def student_detail_view(request, student_id):
    """Staff: View a student's detail and attempt history across all exams."""
    if not _can_access_staff_pages(request.user):
        raise PermissionDenied("You don't have permission to access this page.")
    student = get_object_or_404(User, pk=student_id, user_type='student', is_superuser=False)
    attempts = ExamAttempt.objects.filter(
        student=student
    ).select_related('exam').order_by('-started_at')
    context = {
        'student': student,
        'attempts': attempts,
        'allowed_statuses': ['submitted', 'flagged', 'terminated', 'completed'],
    }
    return render(request, 'staff/student_detail.html', context)
