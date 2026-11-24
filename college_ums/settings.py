import environ
import logging
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

# SECRET_KEY is mandatory: there is no insecure fallback.
# Generate one with:
#   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
try:
    SECRET_KEY = env('SECRET_KEY')
except ImproperlyConfigured as exc:
    raise ImproperlyConfigured(
        "SECRET_KEY is not set. Add SECRET_KEY=<random 50+ chars> to your .env file "
        "(see .env.example). Refusing to start with a default key."
    ) from exc

DEBUG = env.bool('DEBUG', default=False)

if not DEBUG and SECRET_KEY.startswith('django-insecure'):
    raise ImproperlyConfigured(
        "SECRET_KEY looks like a development key (starts with 'django-insecure'). "
        "Set a unique SECRET_KEY before running with DEBUG=False."
    )

# Comma-separated per deployment, e.g. ALLOWED_HOSTS=ums.college.edu,www.ums.college.edu
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'students',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'students.middleware.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'students.middleware.WebsiteVisitMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'college_ums.urls'

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
                'students.context_processors.college_settings',
            ],
        },
    },
]

WSGI_APPLICATION = 'college_ums.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': env('DB_ENGINE', default='django.db.backends.sqlite3'),
        'NAME': env('DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
        'USER': env('DB_USER', default=''),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': env('DB_HOST', default=''),
        'PORT': env('DB_PORT', default=''),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    }
}

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/login/'

# Twilio WhatsApp
TWILIO_ACCOUNT_SID = env('TWILIO_ACCOUNT_SID', default='')
TWILIO_AUTH_TOKEN = env('TWILIO_AUTH_TOKEN', default='')
TWILIO_WHATSAPP_FROM = env('TWILIO_WHATSAPP_FROM', default='whatsapp:+14155238886')

# ── College branding (per-deployment, never hardcode in templates) ──
PORTAL_URL = env('PORTAL_URL', default='http://127.0.0.1:8000')
COLLEGE_NAME = env('COLLEGE_NAME', default='College UMS')
# Static path (e.g. images/college_logo.jpg) or absolute https URL. Blank = icon fallback.
COLLEGE_LOGO = env('COLLEGE_LOGO', default='images/college_logo.jpg')
PRIMARY_COLOR = env('PRIMARY_COLOR', default='#000080')
COLLEGE_EMAIL = env('COLLEGE_EMAIL', default='')
COLLEGE_PHONE = env('COLLEGE_PHONE', default='')
# Optional public-page details; blank values are hidden in templates.
COLLEGE_ADDRESS = env('COLLEGE_ADDRESS', default='')
COLLEGE_WEBSITE = env('COLLEGE_WEBSITE', default='')
COLLEGE_AFFILIATION = env('COLLEGE_AFFILIATION', default='')
COLLEGE_ESTABLISHED = env('COLLEGE_ESTABLISHED', default='')
COLLEGE_PRINCIPAL_NAME = env('COLLEGE_PRINCIPAL_NAME', default='')

# File upload
CSV_MAX_UPLOAD_MB = env.int('CSV_MAX_UPLOAD_MB', default=5)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# Set-password / reset links expire after this many hours.
PASSWORD_RESET_TIMEOUT = env.int('PASSWORD_TOKEN_TIMEOUT_HOURS', default=48) * 60 * 60

# ── Trusted origins (set per deployment, e.g. https://ums.college.edu) ──
CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

# ── Login brute-force protection ──────────────────────────────────────
LOGIN_MAX_ATTEMPTS = env.int('LOGIN_MAX_ATTEMPTS', default=5)
LOGIN_LOCKOUT_SECONDS = env.int('LOGIN_LOCKOUT_MINUTES', default=15) * 60

# ── Proxy trust (only enable behind Caddy/nginx; XFF is spoofable) ─────
TRUST_PROXY_HEADERS = env.bool('TRUST_PROXY_HEADERS', default=False)

# ── Security headers applied by students.middleware.SecurityHeadersMiddleware
SECURITY_CSP = env('SECURITY_CSP', default=(
    "default-src 'self'; "
    "img-src 'self' data: https:; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "script-src 'self' 'unsafe-inline'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
))
SECURITY_PERMISSIONS_POLICY = env('SECURITY_PERMISSIONS_POLICY', default=(
    "geolocation=(), microphone=(), camera=(), payment=()"
))

# ── Error tracking (optional; no key = disabled) ──────────────────────
SENTRY_DSN = env('SENTRY_DSN', default='')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
    except ImportError:  # optional dependency not installed
        logger.warning("SENTRY_DSN set but sentry-sdk is not installed.")
    else:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=env.float('SENTRY_TRACES_RATE', default=0.0),
            send_default_pii=False,
            environment=env('SENTRY_ENV', default='production'),
        )

# ── Production hardening (toggle via DEBUG) ───────────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    # Keep the container health probe on plain HTTP (see Dockerfile HEALTHCHECK).
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 30)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

logger = logging.getLogger(__name__)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "root": {
        "handlers": ["console"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
}
