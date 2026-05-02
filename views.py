from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Q
from exams.models import Exam, ExamAttempt
from exams.views import _get_ended_exam_ids
from accounts.forms_profile import ProfileUpdateForm

"""
Student-facing views: dashboard, profile management, and result history.
"""


@login_required
def dashboard_view(request):
    if request.user.user_type != 'student':
        raise PermissionDenied("You don't have permission to access this page.")
    
    current_time = timezone.now()
    # Exclude exams the student has already completed (submitted, flagged, terminated)
    completed_exam_ids = ExamAttempt.objects.filter(
        student=request.user,
        status__in=['submitted', 'flagged', 'terminated']
    ).values_list('exam_id', flat=True)
    ended_ids = _get_ended_exam_ids(current_time)
    live_base = Exam.objects.filter(
        status__in=['scheduled', 'active']
    ).exclude(status='completed').exclude(id__in=completed_exam_ids).exclude(id__in=ended_ids)
    live_exams = live_base.filter(
        Q(start_time__isnull=True) | Q(start_time__lte=current_time)
    )
    upcoming_exams = live_base.filter(
        Q(start_time__isnull=False) & Q(start_time__gt=current_time)
    )
    exams = (list(live_exams) + list(upcoming_exams))[:5]
    attempts_qs = ExamAttempt.objects.filter(student=request.user).select_related('exam')
    attempts = attempts_qs[:5]

    context = {
        'user': request.user,
        'exams': exams,
        'attempts': attempts,
        'available_exam_count': live_base.count(),
        'attempt_count': attempts_qs.count(),
    }
    return render(request, 'student/dashboard.html', context)


@login_required
def results_view(request):
    """Show a list of the student's completed exam attempts and malpractice scores."""
    if request.user.user_type != 'student':
        raise PermissionDenied("You don't have permission to access this page.")
    
    attempts = ExamAttempt.objects.filter(
        student=request.user,
        status__in=['submitted', 'flagged', 'terminated', 'completed']
    ).select_related('exam').order_by('-ended_at')[:50]
    
    context = {
        'attempts': attempts,
    }
    return render(request, 'student/results.html', context)


@login_required
def profile_edit_view(request):
    """Allow the student to edit their own profile information."""
    if request.user.user_type != 'student':
        raise PermissionDenied("You don't have permission to access this page.")
    
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your profile has been updated successfully.')
            return redirect('student:profile')
    else:
        form = ProfileUpdateForm(instance=request.user)
    
    return render(request, 'student/profile_edit.html', {'form': form})


@login_required
def result_detail_view(request, attempt_id):
    """Display detailed result and malpractice events for a single attempt."""
    if request.user.user_type != 'student':
        raise PermissionDenied()
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    if attempt.status not in ('submitted', 'flagged', 'terminated', 'completed'):
        messages.info(request, 'This exam attempt is not completed yet.')
        return redirect('student:results')
    try:
        session = attempt.session
        events = session.events.all()[:50]
    except Exception:
        session = None
        events = []
    context = {'attempt': attempt, 'session': session, 'events': events}
    return render(request, 'student/result_detail.html', context)
