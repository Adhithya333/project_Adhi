from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.views.decorators.http import require_POST
from django.utils import timezone
from urllib.parse import urlencode
from exams.models import Exam, ExamAttempt, Question, StudentAnswer
from exams.services.student_performance_aggregate import get_student_performance_rows
from exams.views import _can_modify_questions, _get_ended_exam_ids
from malpractice.models import MalpracticeEvent, ExamSession

User = get_user_model()


def _require_superuser(user):
    if not user or not user.is_superuser:
        raise PermissionDenied('Administrator access only.')


@login_required
def dashboard_view(request):
    _require_superuser(request.user)

    current_time = timezone.now()
    ended_ids = _get_ended_exam_ids(current_time)
    live_and_upcoming = Exam.objects.filter(
        status__in=['scheduled', 'active']
    ).exclude(status='completed').exclude(id__in=ended_ids)

    all_exams = Exam.objects.all()
    attempts_finished = ExamAttempt.objects.filter(
        status__in=['submitted', 'flagged', 'terminated', 'completed']
    )
    review_attempts = (
        ExamAttempt.objects.filter(status__in=['flagged', 'terminated'])
        .select_related('student', 'exam')
        .order_by('-ended_at', '-started_at')[:12]
    )
    recent_exams = Exam.objects.select_related('created_by').order_by('-created_at')[:12]

    context = {
        'student_count': User.objects.filter(user_type='student', is_superuser=False).count(),
        'staff_count': User.objects.filter(user_type='staff', is_superuser=False).count(),
        'active_accounts': User.objects.filter(is_superuser=False, is_active=True).count(),
        'inactive_accounts': User.objects.filter(is_superuser=False, is_active=False).count(),
        'exam_count': all_exams.count(),
        'active_exams_count': live_and_upcoming.count(),
        'flagged_count': ExamAttempt.objects.filter(status='flagged').count(),
        'terminated_count': ExamAttempt.objects.filter(status='terminated').count(),
        'total_events': MalpracticeEvent.objects.count(),
        'question_count': Question.objects.count(),
        'attempt_count': ExamAttempt.objects.count(),
        'finished_attempt_count': attempts_finished.count(),
        'session_count': ExamSession.objects.count(),
        'answer_count': StudentAnswer.objects.count(),
        'recent_users': User.objects.filter(is_superuser=False).order_by('-date_joined')[:10],
        'recent_exams': recent_exams,
        'review_attempts': review_attempts,
        'ended_exam_ids': ended_ids,
    }
    return render(request, 'admin_dashboard/dashboard.html', context)


@login_required
def admin_exams_view(request):
    _require_superuser(request.user)
    current_time = timezone.now()
    ended_ids = _get_ended_exam_ids(current_time)
    q = (request.GET.get('q') or '').strip()
    status = (request.GET.get('status') or '').strip()
    exams_qs = (
        Exam.objects.select_related('created_by')
        .annotate(q_count=Count('questions'), att_count=Count('attempts'))
        .order_by('-created_at')
    )
    if q:
        exams_qs = exams_qs.filter(
            Q(title__icontains=q)
            | Q(description__icontains=q)
            | Q(created_by__username__icontains=q)
        )
    if status in {'draft', 'scheduled', 'active', 'completed'}:
        exams_qs = exams_qs.filter(status=status)
    page_obj = Paginator(exams_qs, 12).get_page(request.GET.get('page'))
    query_base = urlencode({k: v for k, v in {'q': q, 'status': status}.items() if v})
    return render(
        request,
        'admin_dashboard/exam_list.html',
        {
            'exams': page_obj.object_list,
            'page_obj': page_obj,
            'q': q,
            'status': status,
            'query_base': query_base,
            'ended_exam_ids': ended_ids,
        },
    )


@login_required
@require_POST
def admin_exam_delete_view(request, pk):
    _require_superuser(request.user)
    exam = get_object_or_404(Exam, pk=pk)
    if exam.attempts.exists():
        messages.error(
            request,
            'This exam cannot be deleted because attempt records exist. Archive it instead of deleting.',
        )
        return redirect('admin_dashboard:admin_exams')
    title = exam.title
    exam.delete()
    messages.success(request, f'Exam "{title}" and all related questions and attempts were deleted successfully.')
    return redirect('admin_dashboard:admin_exams')


@login_required
def admin_exam_questions_view(request, pk):
    _require_superuser(request.user)
    exam = get_object_or_404(Exam, pk=pk)
    questions = exam.questions.all()
    can_modify_questions = _can_modify_questions(exam)
    return render(
        request,
        'admin_dashboard/exam_questions.html',
        {
            'exam': exam,
            'questions': questions,
            'can_modify_questions': can_modify_questions,
        },
    )


@login_required
def admin_student_performance_view(request):
    _require_superuser(request.user)
    q = (request.GET.get('q') or '').strip().lower()
    performances = get_student_performance_rows()
    if q:
        performances = [
            p
            for p in performances
            if q in (p['user'].username or '').lower()
            or q in (p['user'].get_full_name() or '').lower()
        ]
    page_obj = Paginator(performances, 20).get_page(request.GET.get('page'))
    return render(
        request,
        'admin_dashboard/student_performance.html',
        {
            'performances': page_obj.object_list,
            'page_obj': page_obj,
            'q': request.GET.get('q', ''),
            'query_base': urlencode({'q': request.GET.get('q', '').strip()}) if request.GET.get('q') else '',
        },
    )


@login_required
@require_POST
def user_toggle_active_view(request, user_id):
    _require_superuser(request.user)
    target = get_object_or_404(User, pk=user_id, is_superuser=False)
    if target.id == request.user.id:
        messages.error(request, 'You cannot change your own account status from this screen.')
        return redirect('admin_dashboard:dashboard')
    target.is_active = not target.is_active
    target.save(update_fields=['is_active'])
    state = 'enabled' if target.is_active else 'disabled'
    messages.success(
        request,
        f'Account "{target.username}" has been {state}.',
    )
    return redirect('admin_dashboard:dashboard')
