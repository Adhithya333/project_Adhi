"""
Persist parsed MCQs onto an Exam with basic duplicate detection.

Kept separate from views/forms so import logic stays testable and decoupled.
"""

from __future__ import annotations

import re
from typing import Any

from django.db import transaction
from django.db.models import Max

from ..models import Exam, Question


def _norm_question_text(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip().lower())


@transaction.atomic
def save_parsed_questions_for_exam(
    exam: Exam,
    items: list[dict[str, Any]],
    *,
    marks: int = 1,
    negative_marks: float = 0.0,
) -> dict[str, Any]:
    """
    Create Question rows for valid items. Skips duplicates (same normalized question_text
    as an existing question or another item earlier in this batch).

    Returns counts: created, skipped_duplicate, skipped_invalid.
    """
    existing = set(
        _norm_question_text(q.question_text) for q in exam.questions.all()
    )
    seen_batch: set[str] = set()

    max_order = exam.questions.aggregate(m=Max('order'))['m']
    next_order = (max_order if max_order is not None else 0) + 1

    created = 0
    skipped_duplicate = 0
    skipped_invalid = 0

    for item in items:
        errs = item.get('errors') or []
        if errs:
            skipped_invalid += 1
            continue
        qtext = item.get('question_text') or ''
        key = _norm_question_text(qtext)
        if not key:
            skipped_invalid += 1
            continue
        if key in existing or key in seen_batch:
            skipped_duplicate += 1
            continue

        Question.objects.create(
            exam=exam,
            question_text=qtext,
            question_type='mcq',
            option_a=(item.get('option_a') or '')[:500],
            option_b=(item.get('option_b') or '')[:500],
            option_c=(item.get('option_c') or '')[:500],
            option_d=(item.get('option_d') or '')[:500],
            correct_answer=(item.get('correct_answer') or '').upper()[:10],
            marks=marks,
            negative_marks=negative_marks,
            order=next_order,
        )
        next_order += 1
        seen_batch.add(key)
        existing.add(key)
        created += 1

    exam.total_marks = exam.compute_total_marks()
    exam.save(update_fields=['total_marks'])

    return {
        'created': created,
        'skipped_duplicate': skipped_duplicate,
        'skipped_invalid': skipped_invalid,
    }
