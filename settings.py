"""
Django settings for exam_malpractice project.
"""

import os
from pathlib import Path

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
_SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-change-this-in-production-12345')
if _SECRET_KEY == 'django-insecure-change-this-in-production-12345':
    import sys
    _debug_val = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')
    if not _debug_val:
        raise SystemExit(
            'SECURITY: Set DJANGO_SECRET_KEY in production. '
            'Do not use the default fallback when DEBUG=False.'
        )
SECRET_KEY = _SECRET_KEY

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',') if h.strip()]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'student',
    'staff',
    'admin_dashboard',
    'accounts',
    'exams',
    'malpractice',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'exam_malpractice.middleware.TimezoneMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'exam_malpractice.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'exam_malpractice.context_processors.exam_timezone',
            ],
        },
    },
]

WSGI_APPLICATION = 'exam_malpractice.wsgi.application'


# Database
# https://docs.djangoproject.com/en/4.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

# Timezone for display and exam times. Default Asia/Kolkata (IST).
# datetime-local form input is interpreted in this zone.
EXAM_TIMEZONE = os.environ.get('EXAM_TIMEZONE', 'Asia/Kolkata')
TIME_ZONE = EXAM_TIMEZONE

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.2/howto/static-files/

STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (leading slash so snapshot URLs work on live monitoring)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Bulk question import (PDF / image OCR). Max upload size in bytes (default 5 MB).
QUESTION_UPLOAD_MAX_FILE_SIZE = int(os.environ.get('QUESTION_UPLOAD_MAX_FILE_SIZE', str(5 * 1024 * 1024)))
# Optional: full path to tesseract executable on Windows or non-standard installs.
TESSERACT_CMD = os.environ.get('TESSERACT_CMD', '')

# Default primary key field type
# https://docs.djangoproject.com/en/4.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Login URLs
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

# Security Headers & Production Optimization
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {
    'DEFAULT_SRC': ("'self'",),
    'SCRIPT_SRC': ("'self'", "'unsafe-inline'", 'cdnjs.cloudflare.com', 'fonts.googleapis.com'),
    'STYLE_SRC': ("'self'", "'unsafe-inline'", 'fonts.googleapis.com', 'cdnjs.cloudflare.com'),
    'FONT_SRC': ("'self'", 'fonts.gstatic.com', 'cdnjs.cloudflare.com'),
    'CONNECT_SRC': ("'self'",),
    'IMG_SRC': ("'self'", 'data:', 'https:'),
    'FRAME_ANCESTORS': ("'none'",),
}
X_FRAME_OPTIONS = 'DENY'

# Session Security (use HTTPS in production)
_USE_HTTPS = os.environ.get('USE_HTTPS', 'false').lower() in ('true', '1', 'yes')
SESSION_COOKIE_SECURE = _USE_HTTPS
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SECURE = _USE_HTTPS
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = 'Strict'

# Cache Configuration (for better performance)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'unique-snowflake',
    }
}

# Email Configuration (for notifications)
# Set EMAIL_BACKEND in env for production (e.g. django.core.mail.backends.smtp.EmailBackend)
EMAIL_BACKEND = os.environ.get(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend'
)
