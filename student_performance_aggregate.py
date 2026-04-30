"""
Shared aggregation for “student performance” tables (staff + admin console).

Returns one row per student with attempt counts and malpractice averages.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Q

from exams.models import ExamAttempt

User = get_user_model()


def get_student_performance_rows():
    """List of dicts with keys: student, attempt_count, avg_malpractice, flagged_count, user (User instance)."""
    perf = (
        ExamAttempt.objects.filter(status__in=['submitted', 'flagged', 'terminated', 'completed'])
        .values('student')
        .annotate(
            attempt_count=Count('id'),
            avg_malpractice=Avg('malpractice_score'),
            flagged_count=Count('id', filter=Q(status='flagged')),
        )
        .order_by('-avg_malpractice')
    )
    student_ids = [p['student'] for p in perf]
    users = {u.id: u for u in User.objects.filter(id__in=student_ids, is_superuser=False)}
    rows = []
    for p in perf:
        u = users.get(p['student'])
        if u is not None:
            rows.append({**p, 'user': u})
    return rows
