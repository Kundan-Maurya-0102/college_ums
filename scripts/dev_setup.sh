#!/usr/bin/env bash
# One-command local setup for a fresh clone: venv, .env, DB, first admin.
#
#   ./scripts/dev_setup.sh                 # SQLite, DEBUG=True, creates admin
#   ./scripts/dev_setup.sh --seed-demo     # also loads the demo college (50 students)
#   ./scripts/dev_setup.sh --no-admin      # skip the interactive admin creation
#
# It never overwrites an existing .env — copy it aside first if you want a reset.
set -euo pipefail
cd "$(dirname "$0")/.."

PY_BIN="${PY_BIN:-python3}"
ADMIN=1
DEMO=0
for arg in "$@"; do
    case "$arg" in
        --no-admin) ADMIN=0 ;;
        --seed-demo) DEMO=1 ;;
        -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
        *) echo "unknown option: $arg" >&2; exit 2 ;;
    esac
done

if [ ! -d .venv ]; then
    echo "==> creating virtualenv (.venv)"
    "$PY_BIN" -m venv .venv
fi
echo "==> installing requirements"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

if [ -f .env ]; then
    echo "==> .env already exists, leaving it alone"
else
    echo "==> writing .env for local development"
    SECRET=$(.venv/bin/python -c "from django.core.management.utils import get_random_secret_key as k; print(k())")
    sed -e "s|^SECRET_KEY=.*|SECRET_KEY=${SECRET}|" \
        -e "s|^DEBUG=.*|DEBUG=True|" \
        -e "s|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=localhost,127.0.0.1|" \
        .env.example > .env
    chmod 600 .env
fi

echo "==> migrate"
.venv/bin/python manage.py migrate --noinput

echo "==> plans (Basic / Pro / Enterprise)"
.venv/bin/python manage.py seed_plans

echo "==> translations"
.venv/bin/python manage.py compile_translations

echo "==> static files (production uses the hashed manifest)"
.venv/bin/python manage.py collectstatic --noinput >/dev/null

if [ "$ADMIN" = "1" ]; then
    echo "==> first admin"
    .venv/bin/python manage.py create_college \
        --name "${COLLEGE_NAME:-Demo College}" --slug "${COLLEGE_SLUG:-demo-college}" \
        --admin-username "${ADMIN_USERNAME:-admin}" || true
    echo "    (password is printed above; change it after the first login)"
fi

if [ "$DEMO" = "1" ]; then
    echo "==> demo data"
    .venv/bin/python manage.py seed_demo --students 50 --teachers 8
fi

cat <<'EOF'

Ready. Start the server:
    .venv/bin/python manage.py runserver

Then open http://127.0.0.1:8000/login/  (admin: 'admin', password printed above)
Landing page:        http://127.0.0.1:8000/
Platform panel:      http://127.0.0.1:8000/platform/
Help / tour:         http://127.0.0.1:8000/help/
EOF
