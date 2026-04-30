from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from .models import Exam, Question


def _make_aware_in_exam_tz(val):
    """Interpret naive datetime as institution's local time; return timezone-aware."""
    if not val or not timezone.is_naive(val):
        return val
    tz_name = getattr(settings, 'EXAM_TIMEZONE', 'UTC')
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
    except ImportError:
        tz = timezone.get_current_timezone()
    return timezone.make_aware(val, tz)


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['title', 'description', 'duration_minutes', 'start_time', 'end_time', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Exam Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Exam instructions...'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 5, 'max': 300}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_start_time(self):
        val = self.cleaned_data.get('start_time')
        return _make_aware_in_exam_tz(val)

    def clean_end_time(self):
        val = self.cleaned_data.get('end_time')
        return _make_aware_in_exam_tz(val)


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = [
            'question_text', 'question_type', 'option_a', 'option_b', 'option_c', 'option_d',
            'correct_answer', 'marks', 'negative_marks', 'order'
        ]
        widgets = {
            'question_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'question_type': forms.Select(attrs={'class': 'form-control'}),
            'option_a': forms.TextInput(attrs={'class': 'form-control'}),
            'option_b': forms.TextInput(attrs={'class': 'form-control'}),
            'option_c': forms.TextInput(attrs={'class': 'form-control'}),
            'option_d': forms.TextInput(attrs={'class': 'form-control'}),
            'correct_answer': forms.Select(
                choices=[
                    ('', '-- Select --'),
                    ('A', 'A'),
                    ('B', 'B'),
                    ('C', 'C'),
                    ('D', 'D'),
                ],
                attrs={'class': 'form-control'}
            ),
            'marks': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'negative_marks': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.25}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }


def _validate_question_upload_size(uploaded_file):
    """Reject oversized uploads for bulk import (PDF / image)."""
    max_bytes = int(getattr(settings, 'QUESTION_UPLOAD_MAX_FILE_SIZE', 5 * 1024 * 1024))
    if uploaded_file.size > max_bytes:
        mb = max_bytes / (1024 * 1024)
        raise ValidationError(f'File too large. Maximum size is {mb:.1f} MB.')


class QuestionDocumentUploadForm(forms.Form):
    """
    Staff-only: upload a PDF or image to extract MCQs (separate from QuestionForm manual entry).
    """

    document = forms.FileField(
        label='Question document',
        help_text='PDF, PNG, or JPEG. Max size is set in QUESTION_UPLOAD_MAX_FILE_SIZE (default 5 MB).',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'png', 'jpg', 'jpeg']),
            _validate_question_upload_size,
        ],
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.pdf,.png,.jpg,.jpeg,image/*'}),
    )
