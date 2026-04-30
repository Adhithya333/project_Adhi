import io
import json
import re
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.urls import reverse
from PIL import Image
from .models import ExamSession, MalpracticeEvent
from exams.models import ExamAttempt, Exam

"""
Views for AI-based malpractice monitoring and reporting.

These endpoints receive webcam frames and browser events from students,
update malpractice counters/events, and expose staff dashboards/APIs
for live monitoring and post-exam reports.
"""


def get_student_display_name(user):
    """Return a friendly display name (full name if set, otherwise a cleaned username)."""
    full = (user.get_full_name() or '').strip()
    if full:
        return full
    username = user.username or ''
    # Format for display: replace _ with space, add space before digits, title case
    s = username.replace('_', ' ')
    s = re.sub(r'(\d+)', r' \1', s).strip()
    return s.title() if s else username

@login_required
@require_POST
def start_monitoring(request, attempt_id):
    """Start AI monitor for the student's exam attempt. Called when student enters exam room."""
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    if attempt.status != 'in_progress':
        return JsonResponse({'success': False, 'error': 'Exam not in progress'}, status=400)
    from malpractice.services.ai_monitor import start_monitor, is_monitor_running
    if is_monitor_running(attempt_id):
        return JsonResponse({'success': True, 'status': 'already_running'})
    if start_monitor(attempt_id):
        return JsonResponse({'success': True, 'status': 'started'})
    return JsonResponse({'success': False, 'error': 'Could not start monitor'}, status=500)


@login_required
@require_POST
def analyze_frame(request, attempt_id):
    """Receive a frame from the student's browser and run AI detection (malpractice.exam_monitor)."""
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    if attempt.status != 'in_progress':
        return JsonResponse({'success': False, 'error': 'Exam not in progress'}, status=400)

    frame_file = request.FILES.get('frame')
    if not frame_file or frame_file.size == 0:
        return JsonResponse({'success': False, 'error': 'No frame provided'}, status=400)

    try:
        from malpractice.services.ai_monitor import process_frame
        image_bytes = frame_file.read()
        result = process_frame(attempt_id, image_bytes)
        return JsonResponse({'success': True, **result})
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception('Frame analysis failed')
        return JsonResponse({'success': False, 'error': 'Analysis failed. Please try again.'}, status=500)


@login_required
@require_POST
def stop_monitoring(request, attempt_id):
    """Stop AI monitor for the student's exam attempt. Called when student leaves or submits."""
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    if attempt.status != 'in_progress':
        return JsonResponse({'success': False, 'error': 'Exam not in progress'}, status=400)
    from malpractice.services.ai_monitor import stop_monitor
    stopped = stop_monitor(attempt_id)
    return JsonResponse({'success': True, 'stopped': stopped})


@login_required
@require_POST
def malpractice_heartbeat(request):
    """
    Receive malpractice metrics from student's browser during exam.
    Called every 5-10 seconds from the exam room JavaScript.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)
    
    attempt_id = data.get('attempt_id')
    if not attempt_id:
        return JsonResponse({'success': False, 'error': 'attempt_id required'}, status=400)
    
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    session, _ = ExamSession.objects.get_or_create(exam_attempt=attempt)
    
    # Update counters
    face_count = data.get('face_count', 0)
    looking_away = data.get('looking_away', False)
    
    session.last_heartbeat = timezone.now()
    session.face_detected_count += 1 if face_count > 0 else 0
    session.no_face_count += 1 if face_count == 0 else 0
    session.multiple_faces_count += 1 if face_count > 1 else 0
    session.looking_away_count += 1 if looking_away else 0
    session.save()

    score = attempt.calculate_malpractice_score()
    return JsonResponse({
        'success': True,
        'malpractice_score': round(score, 1),
        'counts': {
            'multiple_faces': session.multiple_faces_count,
            'no_face': session.no_face_count,
            'tab_switch': session.tab_switch_count,
            'looking_away': session.looking_away_count,
            'phone_usage': getattr(session, 'phone_usage_count', 0),
        },
    })


@login_required
@require_POST
def malpractice_event(request):
    """Log a single malpractice event (tab switch, copy/paste, etc.). Accepts JSON or multipart with optional snapshot for evidence."""
    attempt_id = None
    event_type = None
    details = {}
    snapshot_file = request.FILES.get('snapshot')

    if request.content_type and 'multipart/form-data' in request.content_type:
        attempt_id = request.POST.get('attempt_id')
        event_type = request.POST.get('event_type')
        try:
            import json as _json
            d = request.POST.get('details', '{}')
            details = _json.loads(d) if d else {}
        except Exception:
            details = {}
    else:
        try:
            data = json.loads(request.body)
            attempt_id = data.get('attempt_id')
            event_type = data.get('event_type')
            details = data.get('details', {}) or {}
        except json.JSONDecodeError:
            return JsonResponse({'success': False, 'error': 'Invalid JSON'}, status=400)

    if not attempt_id or not event_type:
        return JsonResponse({'success': False, 'error': 'attempt_id and event_type required'}, status=400)

    valid_types = ['tab_switch', 'copy_paste', 'fullscreen_exit', 'multiple_faces', 'no_face', 'looking_away', 'phone_usage']
    if event_type not in valid_types:
        return JsonResponse({'success': False, 'error': 'Invalid event_type'}, status=400)

    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    if attempt.status != 'in_progress':
        return JsonResponse({'success': False, 'error': 'Exam not in progress'}, status=400)
    session, _ = ExamSession.objects.get_or_create(exam_attempt=attempt)

    if event_type == 'tab_switch':
        session.tab_switch_count += 1
        severity = 'medium'
    elif event_type == 'multiple_faces':
        session.multiple_faces_count += 1
        severity = 'high'
    elif event_type == 'no_face':
        session.no_face_count += 1
        severity = 'medium'
    elif event_type == 'looking_away':
        session.looking_away_count += 1
        severity = 'low'
    elif event_type == 'phone_usage':
        session.phone_usage_count += 1
        severity = 'high'
    elif event_type == 'copy_paste':
        severity = 'high'
    else:
        severity = 'low'
    session.save()

    event = MalpracticeEvent.objects.create(
        session=session,
        event_type=event_type,
        severity=severity,
        details=details
    )
    if snapshot_file and snapshot_file.size > 0:
        ct = getattr(snapshot_file, 'content_type', '') or ''
        if ct.startswith('image/'):
            from django.core.files.base import ContentFile
            content = ContentFile(snapshot_file.read())
            content.name = f'{event_type}_{attempt_id}_{event.pk}.jpg'
            event.screenshot.save(content.name, content, save=True)

    return JsonResponse({'success': True})


@login_required
@require_POST
def malpractice_snapshot(request, attempt_id):
    """Student uploads a camera snapshot for staff to view."""
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id, student=request.user)
    if attempt.status != 'in_progress':
        return JsonResponse({'success': False, 'error': 'Exam not in progress'}, status=400)
    
    image_file = request.FILES.get('snapshot')
    if not image_file or image_file.size == 0:
        return JsonResponse({'success': False, 'error': 'No image provided'}, status=400)
    ct = getattr(image_file, 'content_type', '') or ''
    if ct and not ct.startswith('image/'):
        return JsonResponse({'success': False, 'error': 'Invalid image'}, status=400)
    
    session, _ = ExamSession.objects.get_or_create(exam_attempt=attempt)
    # Overwrite previous snapshot (works when field is null or has existing file)
    if session.last_snapshot:
        session.last_snapshot.delete(save=False)
    content = ContentFile(image_file.read())
    content.name = f'snapshot_{attempt_id}.jpg'
    session.last_snapshot.save(content.name, content, save=True)
    return JsonResponse({'success': True})


# Thumbnail size for live monitoring (smaller = less lag/freeze on staff view)
SNAPSHOT_THUMB_MAX_SIZE = 320
SNAPSHOT_THUMB_QUALITY = 50


@login_required
@require_GET
def snapshot_image(request, attempt_id):
    """Serve the latest camera snapshot for an attempt (staff only).
    Use ?size=thumb for a smaller image (live monitoring grid) to reduce lag."""
    if not _is_staff(request.user):
        raise PermissionDenied()
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id)
    try:
        session = attempt.session
    except ExamSession.DoesNotExist:
        raise Http404('No session')
    if not session.last_snapshot:
        raise Http404('No snapshot')
    use_thumb = request.GET.get('size') == 'thumb'
    try:
        with session.last_snapshot.open('rb') as f:
            data = f.read()
        if use_thumb:
            img = Image.open(io.BytesIO(data)).convert('RGB')
            w, h = img.size
            if w > SNAPSHOT_THUMB_MAX_SIZE or h > SNAPSHOT_THUMB_MAX_SIZE:
                ratio = min(SNAPSHOT_THUMB_MAX_SIZE / w, SNAPSHOT_THUMB_MAX_SIZE / h)
                new_w, new_h = int(w * ratio), int(h * ratio)
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=SNAPSHOT_THUMB_QUALITY, optimize=True)
            response = HttpResponse(buf.getvalue(), content_type='image/jpeg')
        else:
            response = HttpResponse(data, content_type='image/jpeg')
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
    except (ValueError, OSError):
        raise Http404('Snapshot unavailable')


@login_required
def malpractice_reports(request):
    """List all malpractice reports - for staff."""
    if not _is_staff(request.user):
        raise PermissionDenied()
    
    attempts = ExamAttempt.objects.filter(
        status__in=['submitted', 'flagged', 'terminated', 'completed']
    ).select_related('exam', 'student').order_by('-ended_at')[:100]
    
    context = {'attempts': attempts}
    return render(request, 'malpractice/reports.html', context)


@login_required
def malpractice_report_detail(request, attempt_id):
    """Detailed malpractice report for a single attempt."""
    if not _is_staff(request.user):
        raise PermissionDenied()
    
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id)
    try:
        session = attempt.session
        events = session.events.all()[:50]
    except ExamSession.DoesNotExist:
        session = None
        events = []
    
    context = {'attempt': attempt, 'session': session, 'events': events}
    return render(request, 'malpractice/report_detail.html', context)


@login_required
def live_monitoring(request, exam_id):
    """Live monitoring dashboard for staff."""
    if not _is_staff(request.user):
        raise PermissionDenied()

    exam = get_object_or_404(Exam, pk=exam_id)
    attempts = ExamAttempt.objects.filter(
        exam=exam,
        status='in_progress'
    ).select_related('student')

    attempt_tokens = [{'attempt': a, 'display_name': get_student_display_name(a.student)} for a in attempts]

    context = {
        'exam': exam,
        'attempts': attempts,
        'attempt_tokens': attempt_tokens,
    }
    return render(request, 'malpractice/live_monitoring.html', context)


@login_required
@require_GET
def live_monitoring_api(request, exam_id):
    """API for live monitoring - returns attempt stats (AI detection runs on server)."""
    if not _is_staff(request.user):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    exam = get_object_or_404(Exam, pk=exam_id)
    attempts = ExamAttempt.objects.filter(exam=exam, status='in_progress').select_related('student').select_related('session')

    data = []
    for a in attempts:
        try:
            s = a.session
            if s.last_snapshot:
                snapshot_url = request.build_absolute_uri(
                    reverse('malpractice:snapshot_image', args=[a.id])
                ) + '?size=thumb'
            else:
                snapshot_url = None
            data.append({
                'attempt_id': a.id,
                'student': a.student.username,
                'student_name': get_student_display_name(a.student),
                'multiple_faces': s.multiple_faces_count,
                'no_face': s.no_face_count,
                'tab_switch': s.tab_switch_count,
                'looking_away': s.looking_away_count,
                'phone_usage': getattr(s, 'phone_usage_count', 0),
                'last_heartbeat': s.last_heartbeat.isoformat() if s.last_heartbeat else None,
                'snapshot_url': snapshot_url,
            })
        except ExamSession.DoesNotExist:
            data.append({
                'attempt_id': a.id,
                'student': a.student.username,
                'student_name': get_student_display_name(a.student),
                'multiple_faces': 0,
                'no_face': 0,
                'tab_switch': 0,
                'looking_away': 0,
                'phone_usage': 0,
                'last_heartbeat': None,
                'snapshot_url': None,
            })

    return JsonResponse({'attempts': data})


def _is_staff(user):
    return bool(user and (user.is_superuser or getattr(user, 'user_type', None) == 'staff'))


@login_required
def exam_monitor_view(request):
    """Info page for AI camera monitor - shows all in-progress rooms (active, scheduled, all exams)."""
    if not _is_staff(request.user):
        raise PermissionDenied()
    in_progress = ExamAttempt.objects.filter(
        status='in_progress'
    ).select_related('exam', 'student').order_by('-started_at')
    rooms = [
        {
            'attempt': a,
            'live_monitor_url': reverse('malpractice:live_monitoring', kwargs={'exam_id': a.exam_id}),
        }
        for a in in_progress
    ]
    return render(request, 'malpractice/exam_monitor_info.html', {
        'rooms': rooms,
        'title': 'All Active Rooms',
    })


@login_required
def exam_monitor_exam_view(request, exam_id):
    """AI camera monitor info for a specific exam (active, scheduled, or any status)."""
    if not _is_staff(request.user):
        raise PermissionDenied()
    exam = get_object_or_404(Exam, pk=exam_id)
    # Staff can view all exams
    in_progress = ExamAttempt.objects.filter(
        exam=exam,
        status='in_progress'
    ).select_related('student').order_by('-started_at')
    rooms = [
        {
            'attempt': a,
            'live_monitor_url': reverse('malpractice:live_monitoring', kwargs={'exam_id': a.exam_id}),
        }
        for a in in_progress
    ]
    return render(request, 'malpractice/exam_monitor_info.html', {
        'rooms': rooms,
        'exam': exam,
        'title': f'AI Monitor - {exam.title}',
    })


@login_required
def exam_monitor_room_view(request, attempt_id):
    """Show AI Camera Monitor info for a specific exam room (active, scheduled, or any status)."""
    if not _is_staff(request.user):
        raise PermissionDenied()
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id)
    return render(request, 'malpractice/exam_monitor_info.html', {
        'rooms': [{
            'attempt': attempt,
            'live_monitor_url': reverse('malpractice:live_monitoring', kwargs={'exam_id': attempt.exam_id}),
        }],
        'exam': attempt.exam,
        'selected_attempt_id': attempt_id,
        'title': f'AI Monitor - {attempt.exam.title}',
    })


