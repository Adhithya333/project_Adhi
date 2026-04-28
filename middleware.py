"""
Middleware to activate the institution's timezone for each request.
Ensures all datetime display uses EXAM_TIMEZONE (e.g. Asia/Kolkata for IST).
"""
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class TimezoneMiddleware(MiddlewareMixin):
    """Activate EXAM_TIMEZONE for each request so datetimes display correctly."""

    def process_request(self, request):
        from django.conf import settings
        tz_name = getattr(settings, 'EXAM_TIMEZONE', 'Asia/Kolkata')
        try:
            from zoneinfo import ZoneInfo
            tz = ZoneInfo(tz_name)
        except ImportError:
            try:
                import pytz
                tz = pytz.timezone(tz_name)
            except ImportError:
                tz = timezone.get_default_timezone()
        timezone.activate(tz)
