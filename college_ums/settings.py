import logging
import os
import sys
from pathlib import Path

import environ
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

# A copied .env.example (or a short/known key) is not a secret. In production this is
# fatal instead of a silent weakness; in DEBUG a warning is enough to keep dev easy.
_INSECURE_SECRET_KEYS = {
    "replace-with-a-random-50-plus-character-key",
    "replace-with-a-random-key",
    "changeme",
    "secret",
}
if not DEBUG:
    if len(SECRET_KEY) < 40:
        raise ImproperlyConfigured(
            "SECRET_KEY is too short (%d chars). Use 50+ random characters: "
            'python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"'
            % len(SECRET_KEY)
        )
    if SECRET_KEY.startswith("django-insecure") or SECRET_KEY in _INSECURE_SECRET_KEYS:
        raise ImproperlyConfigured(
            "SECRET_KEY is a placeholder/django-generated dev key. Generate a real one "
            "before running with DEBUG=False."
        )

# ── Environment profile ───────────────────────────────────────────────
# development | staging | production. Everything else stays env-driven; the
# profile only picks safe *defaults* that differ per environment, so a staging
# box can look like production without copying production's risk (HSTS preload,
# long-lived secure cookies, noindex, error tracking tag, tighter backups).
LANDING_PAGE_ENABLED = env.bool('LANDING_PAGE_ENABLED', default=True)
# Serve /media/ through Django with a login check (see students/views/media.py).
# Set False only if an object-storage layer already enforces access.
MEDIA_PROTECTED = env.bool('MEDIA_PROTECTED', default=True)
ENVIRONMENT = env('ENVIRONMENT', default='development' if DEBUG else 'production').lower()
# Shown on the System status page (and useful in support tickets).
RELEASE_VERSION = env('RELEASE_VERSION', default='1.0.0')
if ENVIRONMENT not in ('development', 'staging', 'production'):
    raise ImproperlyConfigured(
        f"ENVIRONMENT must be development, staging or production (got {ENVIRONMENT!r}).")
IS_STAGING = ENVIRONMENT == 'staging'
IS_PRODUCTION = ENVIRONMENT == 'production'

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
    'django.contrib.humanize',
    'students',
    'django_q',
    'platform_admin',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'students.middleware.SecurityHeadersMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'students.middleware.WebsiteVisitMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'platform_admin.middleware.SubscriptionStatusMiddleware',
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
                'students.context_processors.panel_flags',
            ],
        },
    },
]

# Cached template loader for production: parsing templates on every request is
# pure overhead. Tests and DEBUG runs keep the reloading loaders.
if not DEBUG:
    # Django refuses `APP_DIRS` together with an explicit `loaders` list, so
    # APP_DIRS must be switched off here (otherwise every prod page 500s with
    # "app_dirs must not be set when loaders is defined").
    template_config = TEMPLATES[0]
    template_config['APP_DIRS'] = False
    template_config['OPTIONS']['loaders'] = [
        ('django.template.loaders.cached.Loader', [
            'django.template.loaders.filesystem.Loader',
            'django.template.loaders.app_directories.Loader',
        ]),
    ]

WSGI_APPLICATION = 'college_ums.wsgi.application'

# Accept short names ("postgres", "postgresql", "sqlite") as well as full backend
# paths. The backup scripts use DB_ENGINE=postgres, and a stray export of that value
# used to break every management command with "isn't an available database backend".
_DB_ENGINE_ALIASES = {
    'postgres': 'django.db.backends.postgresql',
    'postgresql': 'django.db.backends.postgresql',
    'psql': 'django.db.backends.postgresql',
    'sqlite': 'django.db.backends.sqlite3',
    'sqlite3': 'django.db.backends.sqlite3',
    'mysql': 'django.db.backends.mysql',
}
_raw_db_engine = env('DB_ENGINE', default='django.db.backends.sqlite3').strip()
DB_ENGINE = _DB_ENGINE_ALIASES.get(_raw_db_engine.lower(), _raw_db_engine)

DATABASES = {
    'default': {
        'ENGINE': DB_ENGINE,
        'NAME': env('DB_NAME', default=str(BASE_DIR / 'db.sqlite3')),
        'USER': env('DB_USER', default=''),
        'PASSWORD': env('DB_PASSWORD', default=''),
        'HOST': env('DB_HOST', default=''),
        'PORT': env('DB_PORT', default=''),
        # Reuse connections between requests (default 0 opens one per request).
        'CONN_MAX_AGE': env.int('DB_CONN_MAX_AGE', default=60),
        'OPTIONS': {},
    }
}

if DATABASES['default']['ENGINE'].endswith('sqlite3'):
    # SQLite needs a write timeout; WAL mode is enabled in students/apps.py.
    DATABASES['default']['OPTIONS'] = {'timeout': env.int('SQLITE_TIMEOUT', default=20)}

# One deployment = one database. `manage.py test` gets a *second* throwaway database
# so the isolation suite can prove that College A's deployment never reads College B's
# rows (no code path opens the other alias; requests only ever use 'default').
if os.environ.get('DJANGO_TESTING') == '1' or 'test' in sys.argv:
    import tempfile

    _tmp = Path(tempfile.gettempdir())
    DATABASES['college_b'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': str(_tmp / 'ums_college_b.sqlite3'),
        'TEST': {'NAME': str(_tmp / 'test_ums_college_b.sqlite3')},
        'OPTIONS': {'timeout': 20},
    }

# bcrypt is ~4x cheaper than PBKDF2-SHA256 at Django's default iteration count,
# which matters when 100+ users log in at once. Fallback keeps PBKDF2 if the
# package is missing (hashes are verified with whatever algorithm wrote them).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
try:  # pragma: no cover - optional dependency
    import bcrypt  # noqa: F401
except ImportError:
    pass
else:
    BCRYPT_ROUNDS = env.int('BCRYPT_ROUNDS', default=12)
    PASSWORD_HASHERS = [
        "students.hashers.TunableBCryptSHA256PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2PasswordHasher",
        "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    ]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = env('LANGUAGE_CODE', default='en')
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
# Hindi + English in-app switch. Add more locales by dropping a .po into locale/.
LANGUAGES = [
    ('en', 'English'),
    ('hi', 'हिन्दी'),
]
LOCALE_PATHS = [BASE_DIR / 'locale']
LANGUAGE_COOKIE_AGE = 60 * 60 * 24 * 365
LANGUAGE_COOKIE_NAME = 'ums_language'
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

# `manage.py test` on a fresh clone has no staticfiles/ manifest yet; the manifest
# storage would then raise "Missing staticfiles manifest entry" for every page render.
# Tests use the plain storage; production/CI still build and serve the manifest.
# (CI runs collectstatic before the suite, so anything manifest-specific is caught there.)
RUNNING_TESTS = 'test' in sys.argv or env.bool('DJANGO_TESTING', default=False)
if RUNNING_TESTS:
    STORAGES['staticfiles'] = {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
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
TWILIO_SMS_FROM = env('TWILIO_SMS_FROM', default='')   # e.g. +919876543210; empty = SMS disabled

# ── College branding (per-deployment, never hardcode in templates) ──
PORTAL_URL = env('PORTAL_URL', default='http://127.0.0.1:8000')
COLLEGE_NAME = env('COLLEGE_NAME', default='College UMS')
# Static path (e.g. images/college_logo.jpg) or absolute https URL. Blank = icon fallback.
COLLEGE_LOGO = env('COLLEGE_LOGO', default='images/college_logo.jpg')
PRIMARY_COLOR = env('PRIMARY_COLOR', default='#000080')
COLLEGE_EMAIL = env('COLLEGE_EMAIL', default='')
# Where error digests and platform alerts go (defaults to superuser e-mails).
SUPPORT_EMAIL = env('SUPPORT_EMAIL', default='')
COLLEGE_PHONE = env('COLLEGE_PHONE', default='')
# Optional public-page details; blank values are hidden in templates.
COLLEGE_ADDRESS = env('COLLEGE_ADDRESS', default='')
COLLEGE_WEBSITE = env('COLLEGE_WEBSITE', default='')
# Optional shared folder for study material; blank means the button is hidden.
MATERIAL_SHARED_FOLDER_URL = env('MATERIAL_SHARED_FOLDER_URL', default='')
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
# ── Outbound services must time out, not hang ─────────────────────────
EMAIL_TIMEOUT = env.int('EMAIL_TIMEOUT', default=10)          # seconds
HTTP_TIMEOUT = env.int('HTTP_TIMEOUT', default=10)            # gateway/API calls

# ── Outbound e-mail (student credential mails, subscription reminders) ─
# Without these, Django falls back to SMTP localhost:25, which silently fails in a
# container — notifications looked implemented but could never leave the box.
if DEBUG:
    _default_email_backend = 'django.core.mail.backends.console.EmailBackend'
else:
    _default_email_backend = 'django.core.mail.backends.smtp.EmailBackend'
# An empty value in .env ('EMAIL_BACKEND=') must mean "use the default", not "no backend".
EMAIL_BACKEND = env('EMAIL_BACKEND', default='') or _default_email_backend
EMAIL_HOST = env('EMAIL_HOST', default='') or 'localhost'
EMAIL_PORT = env.int('EMAIL_PORT', default=587) or 587
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured('EMAIL_USE_TLS and EMAIL_USE_SSL cannot both be True')
_default_from = env('DEFAULT_FROM_EMAIL', default='')
if not _default_from:
    _host = (env('COLLEGE_DOMAIN', default='') or COLLEGE_WEBSITE
             or 'localhost')
    _host = _host.replace('https://', '').replace('http://', '').strip('/') or 'localhost'
    if _host.startswith('www.'):
        _host = _host[4:]
    _default_from = f"{COLLEGE_NAME or 'College UMS'} <no-reply@{_host}>"
DEFAULT_FROM_EMAIL = _default_from
SERVER_EMAIL = env('SERVER_EMAIL', default=DEFAULT_FROM_EMAIL)

# ── Background jobs (django-q2, ORM broker — no Redis required) ───────
Q_CLUSTER = {
    'name': 'ums',
    'workers': env.int('Q_WORKERS', default=2),
    'timeout': env.int('Q_TIMEOUT', default=120),      # hard kill per task
    'retry': env.int('Q_RETRY', default=180),          # must be > timeout
    'max_attempts': env.int('Q_MAX_ATTEMPTS', default=3),
    'save_limit': 200,
    'catch_up': False,
    'orm': 'default',
    'sync': env.bool('Q_SYNC', default=False),
    'label': 'College UMS tasks',
}
# Per-job retry attempts for outbound calls (inside the task, with backoff).
TASK_MAX_ATTEMPTS = env.int('TASK_MAX_ATTEMPTS', default=3)

# ── Platform / super admin ────────────────────────────────────────────
COLLEGE_SLUG = env('COLLEGE_SLUG', default='')
PLATFORM_ADMIN_GROUP = env('PLATFORM_ADMIN_GROUP', default='Platform Admin')
PLATFORM_METRICS_TOKEN = env('PLATFORM_METRICS_TOKEN', default='')
PLATFORM_BACKUP_DIR = env('PLATFORM_BACKUP_DIR', default='/var/backups/ums')
SUBSCRIPTION_REMINDER_DAYS = env.int('SUBSCRIPTION_REMINDER_DAYS', default=14)

# ── Privacy / data protection ─────────────────────────────────────────
PRIVACY_LAST_UPDATED = env('PRIVACY_LAST_UPDATED', default='2026-01-01')
DATA_RETENTION_YEARS = env.int('DATA_RETENTION_YEARS', default=7)
AUDIT_LOG_RETENTION_DAYS = env.int('AUDIT_LOG_RETENTION_DAYS', default=365 * 7)
VISIT_RETENTION_DAYS = env.int('VISIT_RETENTION_DAYS', default=180)
# Heavy reports are cached for this long; 0 disables caching.
REPORTS_CACHE_SECONDS = env.int('REPORTS_CACHE_SECONDS', default=120)
DASHBOARD_CACHE_SECONDS = env.int('DASHBOARD_CACHE_SECONDS', default=30)
VISIT_TRACK_STAFF = env.bool('VISIT_TRACK_STAFF', default=False)
# Extra redaction patterns for logs/error reports (comma separated regexes).
LOG_REDACT_EXTRA_PATTERNS = env.list('LOG_REDACT_EXTRA_PATTERNS', default=[])

logger = logging.getLogger(__name__)

# ERROR/CRITICAL records are also kept in the database (System status + digest).
ERROR_TRACKING_ENABLED = env.bool('ERROR_TRACKING_ENABLED', default=True)

# Where scripts/backup_db.sh writes dumps, and how old a backup may get before the
# System status page flags it. Keep BACKUP_DIR outside the repo in production.
BACKUP_DIR = env('BACKUP_DIR', default=str(BASE_DIR / 'backups'))
BACKUP_MAX_AGE_HOURS = env.int('BACKUP_MAX_AGE_HOURS', default=48)

SENTRY_DSN = env('SENTRY_DSN', default='')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration

        from students.privacy import scrub_breadcrumb, scrub_sentry_event
    except ImportError:  # optional dependency not installed
        logger.warning("SENTRY_DSN set but sentry-sdk is not installed.")
    else:
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=env.float('SENTRY_TRACES_RATE', default=0.0),
            # sentry-sdk >= 2.7x: explicit deny list instead of the deprecated
            # send_default_pii flag. Nothing about a student leaves the deployment.
            data_collection={
                "user_info": False,
                "cookies": False,
                "request_body": False,
                "query_string": False,
            },
            # Never ship request bodies/cookies or student PII to the error tracker.
            before_send=scrub_sentry_event,
            before_breadcrumb=scrub_breadcrumb,
            max_request_body_size='never',
            environment=env('SENTRY_ENV', default=ENVIRONMENT),
        )

# ── Production hardening (toggle via DEBUG) ───────────────────────────
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    # Keep the container health probe on plain HTTP (see Dockerfile HEALTHCHECK).
    SECURE_REDIRECT_EXEMPT = [r"^healthz/$", r"^readyz/$"]
    # Secure cookies are the default because production traffic is HTTPS end to end.
    # Overridable for staging boxes that are only reachable over plain HTTP; turning
    # them off under DEBUG=False makes `manage.py check --deploy` warn on purpose.
    SESSION_COOKIE_SECURE = env.bool('SESSION_COOKIE_SECURE', default=True)
    CSRF_COOKIE_SECURE = env.bool('CSRF_COOKIE_SECURE', default=True)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
    # Staging keeps HSTS short and skips preload so a staging domain can never
    # be burned into browser HSTS lists by accident.
    default_hsts = 60 * 60 * 24 if IS_STAGING else 60 * 60 * 24 * 30
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=default_hsts)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = not IS_STAGING
    SECURE_HSTS_PRELOAD = not IS_STAGING
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"

LOG_FORMAT = env("LOG_FORMAT", default="text").lower()
if LOG_FORMAT not in ("text", "json"):
    raise ImproperlyConfigured("LOG_FORMAT must be 'text' or 'json'.")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        # Order matters: redact first, then tag the record with the environment.
        "redact": {"()": "students.logging_filters.RedactSensitiveFilter"},
        "context": {"()": "students.log_formatter.ContextFilter",
                    "environment": ENVIRONMENT},
    },
    "formatters": {
        "json": {"()": "students.log_formatter.JsonFormatter"},
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact", "context"],
            "formatter": "json" if LOG_FORMAT == "json" else "plain",
        },
        # ERROR/CRITICAL -> students.ErrorEvent (System status page + daily digest).
        "errors_db": {
            "class": "students.error_tracking.DatabaseErrorHandler",
            "level": "ERROR",
            "filters": ["redact"],
        },
    },
    "root": {
        "handlers": ["console", "errors_db"],
        "level": env("LOG_LEVEL", default="INFO"),
    },
    "loggers": {
        # Django's own request log already carries status codes; keep it terse.
        "django.request": {"handlers": ["console", "errors_db"], "level": "WARNING",
                           "propagate": False},
        "django.security": {"handlers": ["console", "errors_db"], "level": "WARNING",
                            "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# Test runs must never read cached aggregates (locmem cache survives between tests).
if len(sys.argv) > 1 and sys.argv[1] == "test":
    DASHBOARD_CACHE_SECONDS = 0
    REPORTS_CACHE_SECONDS = 0
