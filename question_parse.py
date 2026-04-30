"""
Parse plain text into MCQ-shaped dicts for bulk import.

Expected layout (flexible spacing; case-insensitive answer line):

  Q1. Question text (may continue on following lines until options)
  A. Option 1
  B. Option 2
  C. Option 3
  D. Option 4
  Answer: A

OCR/PDF output may insert extra blank lines; this parser tolerates that.
"""

from __future__ import annotations

import re
from typing import Any


_Q_START = re.compile(r'^\s*Q\s*(\d+)\s*[.)]\s*(.*)\s*$', re.IGNORECASE)
_OPT_A = re.compile(r'^\s*A\s*[.)]\s*(.+)\s*$', re.IGNORECASE)
_OPT_B = re.compile(r'^\s*B\s*[.)]\s*(.+)\s*$', re.IGNORECASE)
_OPT_C = re.compile(r'^\s*C\s*[.)]\s*(.+)\s*$', re.IGNORECASE)
_OPT_D = re.compile(r'^\s*D\s*[.)]\s*(.+)\s*$', re.IGNORECASE)
_ANSWER = re.compile(r'^\s*Answer\s*:\s*([ABCD])\s*$', re.IGNORECASE)


def _collapse_ws(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '').strip())


def parse_mcq_text_to_dicts(text: str) -> list[dict[str, Any]]:
    """
    Return a list of dicts with keys: question_text, option_a..d, correct_answer, errors (list[str]).
    Each item may include `errors` when required fields are missing (still returned for preview).
    """
    raw = (text or '').replace('\r\n', '\n').replace('\r', '\n')
    lines = raw.split('\n')
    blocks: list[list[str]] = []
    current: list[str] | None = None

    for line in lines:
        m = _Q_START.match(line)
        if m:
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            current.append(line)
    if current is not None:
        blocks.append(current)

    out: list[dict[str, Any]] = []
    for block in blocks:
        item = _parse_block(block)
        out.append(item)
    return out


def _parse_block(block_lines: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    if not block_lines:
        return {
            'question_text': '',
            'option_a': '',
            'option_b': '',
            'option_c': '',
            'option_d': '',
            'correct_answer': '',
            'errors': ['Empty block'],
        }

    first = block_lines[0]
    m0 = _Q_START.match(first)
    q_parts: list[str] = []
    if m0:
        rest = (m0.group(2) or '').strip()
        if rest:
            q_parts.append(rest)
    else:
        errors.append('Block does not start with a Qn. marker.')

    opt_a = opt_b = opt_c = opt_d = ''
    correct = ''
    stage = 'question'  # question | options | done

    for line in block_lines[1:]:
        if stage == 'question':
            if _OPT_A.match(line):
                opt_a = _OPT_A.match(line).group(1).strip()
                stage = 'options'
                continue
            if line.strip():
                q_parts.append(line.strip())
            continue

        if stage == 'options':
            ma = _OPT_A.match(line)
            mb = _OPT_B.match(line)
            mc = _OPT_C.match(line)
            md = _OPT_D.match(line)
            mans = _ANSWER.match(line)
            if ma:
                opt_a = ma.group(1).strip()
            elif mb:
                opt_b = mb.group(1).strip()
            elif mc:
                opt_c = mc.group(1).strip()
            elif md:
                opt_d = md.group(1).strip()
            elif mans:
                correct = mans.group(1).upper()
                stage = 'done'
            elif line.strip():
                errors.append(f'Unexpected line in options: {line.strip()[:80]}')
            continue

        if stage == 'done':
            if line.strip() and _ANSWER.match(line):
                pass
            elif line.strip():
                errors.append(f'Ignored trailing line: {line.strip()[:80]}')

    q_text = _collapse_ws('\n'.join(q_parts))
    opt_a, opt_b, opt_c, opt_d = map(_collapse_ws, (opt_a, opt_b, opt_c, opt_d))
    correct = (correct or '').strip().upper()

    if not q_text:
        errors.append('Missing question text.')
    for label, val in (('A', opt_a), ('B', opt_b), ('C', opt_c), ('D', opt_d)):
        if not val:
            errors.append(f'Missing option {label}.')
    if correct not in ('A', 'B', 'C', 'D'):
        errors.append('Missing or invalid Answer (expected A, B, C, or D).')

    return {
        'question_text': q_text,
        'option_a': opt_a,
        'option_b': opt_b,
        'option_c': opt_c,
        'option_d': opt_d,
        'correct_answer': correct if correct in ('A', 'B', 'C', 'D') else '',
        'errors': errors,
    }


def is_parse_item_valid(item: dict[str, Any]) -> bool:
    return not item.get('errors')
