"""Template context processors."""

def exam_timezone(request):
    """Add exam_tz to all templates for timezone-aware date display."""
    from django.conf import settings
    return {'exam_tz': getattr(settings, 'EXAM_TIMEZONE', 'Asia/Kolkata')}
