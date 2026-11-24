#!/usr/bin/env bash
# Local mirror of .github/workflows/ci.yml — run before pushing.
set -euo pipefail
cd "$(dirname "$0")/.."
PY_BIN="${PY_BIN:-.venv/bin/python}"
export SECRET_KEY="${SECRET_KEY:-ci-only-secret-key-0123456789abcdefghijklmnopqrstuvwxyz}"
export ALLOWED_HOSTS="localhost,127.0.0.1,testserver"
export CSRF_TRUSTED_ORIGINS="http://localhost,http://127.0.0.1"

echo "==> ruff"
.venv/bin/ruff check .

echo "==> bandit"
.venv/bin/bandit -r students college_ums platform_admin scripts -q -ll || true

echo "==> pip-audit (Django 4.2 advisories accepted until the 5.2 LTS upgrade)"
.venv/bin/pip-audit -r requirements.txt --progress-spinner off \
  --ignore-vuln PYSEC-2026-3717 --ignore-vuln PYSEC-2026-198 --ignore-vuln PYSEC-2026-199 --ignore-vuln PYSEC-2026-201 --ignore-vuln PYSEC-2026-2090 --ignore-vuln PYSEC-2026-2091 --ignore-vuln PYSEC-2026-2092 --ignore-vuln PYSEC-2026-4035

echo "==> migrations"
DEBUG=True $PY_BIN manage.py makemigrations --check --dry-run

echo "==> django check (dev)"
DEBUG=True $PY_BIN manage.py check

echo "==> collectstatic + production template engine"
DEBUG=False SECURE_SSL_REDIRECT=False $PY_BIN manage.py collectstatic --noinput >/dev/null
DEBUG=False SECURE_SSL_REDIRECT=False $PY_BIN - <<'PY'
import django, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "college_ums.settings")
django.setup()
from django.template import engines
engines["django"]
print("template engine ok in production settings")
PY
DEBUG=False SECURE_SSL_REDIRECT=False $PY_BIN manage.py test students.tests.test_ops students.tests.test_smoke_pages students.tests.test_pwa

echo "==> full test suite (dev settings)"
DEBUG=True $PY_BIN manage.py test
echo "CI mirror finished OK"
