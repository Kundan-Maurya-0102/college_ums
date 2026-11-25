#!/usr/bin/env bash
# Provision one College UMS deployment on a fresh server, in one command.
#
#   ./scripts/provision_server.sh gpgaya \
#       --name "Government Polytechnic Gaya" --domain ums.gpgaya.ac.in \
#       --repo /opt/src/college_ums --plan pro \
#       --restore /var/backups/ums/gpgaya-20260101-0230.sql.gz.enc
#
# What it does (idempotent — safe to re-run after a failure):
#   1. checks the tools it needs, stops early with a readable message
#   2. creates the deployment directory and a virtualenv
#   3. writes .env with generated SECRET_KEY / BACKUP_ENCRYPTION_KEY / metrics token
#      (never overwrites an existing .env)
#   4. installs requirements, migrates, seeds plans, compiles translations,
#      collects static files
#   5. optionally restores a backup BEFORE creating the college record
#   6. creates the college + first admin, then runs diagnose_college
#   7. prints the exact next steps (TLS proxy, service, cron)
#
# It does not touch the network, the system proxy or your firewall.
set -euo pipefail

BASE="${UMS_BASE:-/opt/ums}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REPO_SRC=""
NAME=""
DOMAIN=""
PLAN="basic"
RESTORE_FILE=""
ADMIN_USER="admin"
ADMIN_EMAIL=""
SKIP_CREATE=0
DEMO=0
SLUG=""

die() { echo "ERROR: $*" >&2; exit 1; }
log() { echo "[$(date -Is)] $*"; }
usage() {
  sed -n '2,25p' "$0" | sed 's/^# \{0,1\}//'
  exit "${1:-0}"
}

[[ $# -ge 1 ]] || usage 1
SLUG="$1"; shift
while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2 ;;
    --domain) DOMAIN="$2"; shift 2 ;;
    --plan) PLAN="$2"; shift 2 ;;
    --repo) REPO_SRC="$2"; shift 2 ;;
    --restore) RESTORE_FILE="$2"; shift 2 ;;
    --admin-username) ADMIN_USER="$2"; shift 2 ;;
    --admin-email) ADMIN_EMAIL="$2"; shift 2 ;;
    --skip-create-college) SKIP_CREATE=1; shift ;;
    --demo) DEMO=1; shift ;;
    -h|--help) usage 0 ;;
    *) die "unknown argument: $1 (try --help)" ;;
  esac
done

[[ -n "$SLUG" ]] || die "slug is required"
[[ -n "$NAME" ]] || NAME="$SLUG"
DEST="$BASE/$SLUG"

log "provisioning '$NAME' (slug=$SLUG) into $DEST"

# ── 1. tools ────────────────────────────────────────────────────────────
need() { command -v "$1" >/dev/null 2>&1 || die "$1 is required but not installed ($2)"; }
need "$PYTHON_BIN" "install python 3.12+"
need openssl "install openssl (used for secret generation)"
need git "install git (or pass a prepared --repo directory)"
PYVER="$("$PYTHON_BIN" -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
log "python $PYVER found"
"$PYTHON_BIN" - <<'PY' || die "python 3.10+ is required"
import sys
sys.exit(0 if sys.version_info >= (3, 10) else 1)
PY

# ── 2. directory + code ─────────────────────────────────────────────────
mkdir -p "$DEST"
if [[ ! -f "$DEST/manage.py" ]]; then
  if [[ -n "$REPO_SRC" && -d "$REPO_SRC" ]]; then
    log "copying code from $REPO_SRC"
    # Never carry another deployment's .env, secrets, database or uploads across.
    tar -C "$REPO_SRC" --exclude=.venv --exclude=.git --exclude=media \
        --exclude=staticfiles --exclude=db.sqlite3 --exclude=backups \
        --exclude=deployments --exclude=.env \
        -cf - . | tar -C "$DEST" -xf -
  else
    die "no code in $DEST and no --repo given"
  fi
else
  log "code already present in $DEST"
fi
cd "$DEST"

if [[ ! -d .venv ]]; then
  log "creating virtualenv"
  "$PYTHON_BIN" -m venv .venv
fi
log "installing dependencies"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r requirements.txt

# ── 3. .env ─────────────────────────────────────────────────────────────
if [[ -f .env ]]; then
  log ".env already exists — keeping it (delete it to start over)"
else
  log "writing .env with freshly generated secrets"
  SECRET="$(openssl rand -base64 48 | tr -d '\n')"
  BACKUP_KEY="$(openssl rand -base64 32)"
  METRICS="$(openssl rand -hex 24)"
  cp .env.example .env
  "$PYTHON_BIN" - "$SECRET" "$BACKUP_KEY" "$METRICS" "$NAME" "$SLUG" "$DOMAIN" <<'PY'
import re, sys
secret, backup_key, metrics, name, slug, domain = sys.argv[1:7]
text = open('.env', encoding='utf-8').read()

def set_key(text, key, value):
    pattern = re.compile(rf'^{re.escape(key)}=.*$', re.MULTILINE)
    line = f'{key}={value}'
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    return text.rstrip('\n') + '\n' + line + '\n'

settings = {
    'DEBUG': 'False',
    'ENVIRONMENT': 'production',
    'SECRET_KEY': secret,
    # 127.0.0.1/localhost stay allowed: the TLS proxy and health probes reach the
    # app on loopback with that Host header.
    'ALLOWED_HOSTS': ','.join(dict.fromkeys(
        [h for h in (domain,) if h] + ['localhost', '127.0.0.1'])),
    'CSRF_TRUSTED_ORIGINS': f'https://{domain}' if domain else 'http://localhost:8000',
    'COLLEGE_NAME': f'"{name}"',
    'COLLEGE_SLUG': slug,
    'COLLEGE_DOMAIN': domain or 'localhost',
    'BACKUP_ENCRYPTION_KEY': backup_key,
    'PLATFORM_METRICS_TOKEN': metrics,
    'BACKUP_DIR': f'{"/opt/ums/" + slug}/backups',
    'LOG_FORMAT': 'json',
}
for key, value in settings.items():
    text = set_key(text, key, value)
open('.env', 'w', encoding='utf-8').write(text)
print('  .env written')
PY
  chmod 600 .env
fi

# ── 4. database + assets ────────────────────────────────────────────────
log "applying migrations"
.venv/bin/python manage.py migrate --noinput
log "seeding plans"
.venv/bin/python manage.py seed_plans
log "compiling translations"
.venv/bin/python manage.py compile_translations
log "collecting static files"
.venv/bin/python manage.py collectstatic --noinput >/dev/null
mkdir -p media backups

# ── 5. optional restore (before any college record exists) ──────────────
if [[ -n "$RESTORE_FILE" ]]; then
  log "restoring $RESTORE_FILE"
  ./scripts/restore_db.sh --file "$RESTORE_FILE" --yes
  SKIP_CREATE=1   # the restored dump already carries the College row and users
fi

# ── 6. college + admin ──────────────────────────────────────────────────
if [[ "$SKIP_CREATE" != "1" ]]; then
  log "creating the college and its first admin"
  args=(--name "$NAME" --slug "$SLUG" --plan "$PLAN" --admin-username "$ADMIN_USER")
  [[ -n "$DOMAIN" ]] && args+=(--domain "$DOMAIN")
  [[ -n "$ADMIN_EMAIL" ]] && args+=(--admin-email "$ADMIN_EMAIL")
  .venv/bin/python manage.py create_college "${args[@]}"
fi

if [[ "$DEMO" == "1" ]]; then
  log "seeding demo data (staging only)"
  .venv/bin/python manage.py seed_demo --force
fi

# ── 7. health report ────────────────────────────────────────────────────
log "diagnosing the deployment"
set +e
.venv/bin/python manage.py diagnose_college "${DOMAIN:-localhost}"
DIAG_CODE=$?
set -e

cat <<EOF

Deployment ready: $DEST
  python        : $DEST/.venv/bin/python
  env file      : $DEST/.env (chmod 600, secrets generated)
  database      : $(grep -E '^DB_ENGINE=' .env 2>/dev/null | cut -d= -f2- || true)$(grep -qE '^DB_ENGINE=' .env 2>/dev/null || echo 'alias default (set DB_ENGINE to be explicit)')
  diagnose exit : $DIAG_CODE (0 ok, 1 broken, 2 warnings)

Next steps:
  1. TLS proxy: point Caddy/nginx at 127.0.0.1:8000 (deploy/Caddyfile is a template)
  2. service   : gunicorn college_ums.wsgi:application --bind 127.0.0.1:8000 --workers 3
                 and 'manage.py qcluster' for background jobs
  3. cron      : 30 2 * * * $DEST/scripts/backup_db.sh
                 0 7  * * * $DEST/.venv/bin/python $DEST/manage.py send_error_digest --only-if-errors
  4. check     : curl -s http://127.0.0.1:8000/readyz/
  5. runbook   : docs/RUNBOOK.md
EOF
exit "$DIAG_CODE"
