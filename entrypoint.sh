#!/usr/bin/env bash
# Container entrypoint: fail fast, migrate, collect static, then serve.
set -euo pipefail

if [ -z "${SECRET_KEY:-}" ]; then
    echo "[entrypoint] ERROR: SECRET_KEY is not set. Pass it via the environment." >&2
    exit 1
fi

echo "[entrypoint] applying database migrations..."
python manage.py migrate --noinput

echo "[entrypoint] compiling translations (.po -> .mo, no gettext needed)..."
python manage.py compile_translations

echo "[entrypoint] collecting static files..."
python manage.py collectstatic --noinput

echo "[entrypoint] starting gunicorn on port ${PORT:-8000}..."
exec gunicorn college_ums.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-60}" \
    --access-logfile - \
    --error-logfile -
