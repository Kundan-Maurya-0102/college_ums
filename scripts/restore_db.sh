#!/usr/bin/env bash
# Restore a College UMS backup (encrypted or plain), with a safety check.
#
#   ./scripts/restore_db.sh --file backups/ums-20260101-0230.sql.gz.enc --yes
#   DB_ENGINE=sqlite DB_PATH=/tmp/restore-test.sqlite3 ./scripts/restore_db.sh --file ... --yes
#
# Never restores into a live DB without --yes. Prints row counts after restore.
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
# Read only the keys we need. `source`ing .env is unsafe: values may contain spaces
# (e.g. COLLEGE_NAME=Government Polytechnic Tekari, Gaya).
env_get() {
  local key="$1" line
  [[ -f "$ENV_FILE" ]] || return 1
  line="$(grep -E "^[[:space:]]*${key}=" "$ENV_FILE" | tail -n 1 || true)"
  [[ -n "$line" ]] || return 1
  printf '%s' "${line#*=}" | sed -e 's/^["'"'"']//' -e 's/["'"'"'][[:space:]]*$//'
}

# Own name on purpose: exporting DB_ENGINE would shadow Django's setting
# (django.db.backends.*) and break management commands run from here.
BACKUP_DB_ENGINE="${BACKUP_DB_ENGINE:-${DB_ENGINE:-$(env_get BACKUP_DB_ENGINE || env_get DB_ENGINE || echo postgres)}}"
# Accept the Django backend path as well: the same .env serves both.
case "$BACKUP_DB_ENGINE" in
  *postgresql*|*postgres*) BACKUP_DB_ENGINE=postgres ;;
  *sqlite*)                BACKUP_DB_ENGINE=sqlite ;;
esac
# Hand Django the full backend path (never the short name) for the helper calls below.
if [[ "$BACKUP_DB_ENGINE" == "postgres" ]]; then
  export DB_ENGINE="django.db.backends.postgresql"
else
  export DB_ENGINE="django.db.backends.sqlite3"
fi
PYTHON_BIN="${PYTHON_BIN:-python3}"
# Some hosts keep psql outside PATH (e.g. /usr/lib/postgresql/16/bin).
PG_BIN_DIR="${PG_BIN_DIR:-$(env_get PG_BIN_DIR || true)}"
if [[ -n "$PG_BIN_DIR" ]]; then
  export PATH="$PG_BIN_DIR:$PATH"
fi

require_binary() {
  command -v "$1" >/dev/null 2>&1 && return 0
  {
    echo "ERROR: '$1' not found on this host."
    echo "       Install the postgres client tools, or set PG_BIN_DIR=/usr/lib/postgresql/16/bin"
  } >&2
  exit 1
}
FILE=""
ASSUME_YES=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --file) FILE="$2"; shift 2 ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$FILE" ]] || { echo "Usage: $0 --file <backup> [--yes]" >&2; exit 2; }
[[ -f "$FILE" ]] || { echo "ERROR: file not found: $FILE" >&2; exit 1; }

log() { echo "[$(date -Is)] $*"; }

TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

SQL_GZ="$TMP_DIR/dump.sql.gz"
case "$FILE" in
  *.enc)
    BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-$(env_get BACKUP_ENCRYPTION_KEY || true)}"
    [[ -n "${BACKUP_ENCRYPTION_KEY:-}" ]] || {
      echo "ERROR: encrypted backup but BACKUP_ENCRYPTION_KEY is not set." >&2; exit 1; }
    # openssl reads it from the environment: export it when it came from .env.
    export BACKUP_ENCRYPTION_KEY
    openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
      -pass env:BACKUP_ENCRYPTION_KEY -in "$FILE" -out "$SQL_GZ"
    ;;
  *.gz) cp "$FILE" "$SQL_GZ" ;;
  *) echo "ERROR: expected .sql.gz or .sql.gz.enc" >&2; exit 1 ;;
esac

gzip -t "$SQL_GZ" || { echo "ERROR: gzip integrity check failed" >&2; exit 1; }
SQL="$TMP_DIR/dump.sql"
gunzip -c "$SQL_GZ" > "$SQL"
log "backup decrypted and verified: $(wc -l < "$SQL") lines"

if [[ "$BACKUP_DB_ENGINE" == "sqlite" || "$BACKUP_DB_ENGINE" == "sqlite3" ]]; then
  DB_PATH="${DB_PATH:-$(env_get DB_PATH || echo db.sqlite3)}"
  if [[ "$ASSUME_YES" != "1" ]]; then
    echo "Refusing to overwrite $DB_PATH without --yes" >&2
    exit 3
  fi
  [[ -f "$DB_PATH" ]] && cp "$DB_PATH" "${DB_PATH}.pre-restore.$(date +%s)"
  rm -f "$DB_PATH"
  "$PYTHON_BIN" - "$DB_PATH" "$SQL" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
with open(sys.argv[2]) as fh:
    conn.executescript(fh.read())
conn.commit()
print("restored tables:", conn.execute(
    "select count(*) from sqlite_master where type='table'").fetchone()[0])
print("students:", conn.execute("select count(*) from students_studentprofile").fetchone()[0])
print("users:", conn.execute("select count(*) from auth_user").fetchone()[0])
print("integrity:", conn.execute("pragma integrity_check").fetchone()[0])
conn.close()
PY
else
  DB_NAME="${DB_NAME:-$(env_get DB_NAME || env_get POSTGRES_DB || echo ums)}"
  DB_USER="${DB_USER:-$(env_get DB_USER || env_get POSTGRES_USER || echo ums)}"
  # Same fallback as backup_db.sh: a VPS role has a password, so psql needs it.
  DB_PASSWORD="${DB_PASSWORD:-$(env_get DB_PASSWORD || env_get POSTGRES_PASSWORD || true)}"
  DB_HOST="${DB_HOST:-$(env_get DB_HOST || echo localhost)}"
  DB_PORT="${DB_PORT:-$(env_get DB_PORT || echo 5432)}"
  export DB_PASSWORD
  if [[ "$ASSUME_YES" != "1" ]]; then
    echo "Refusing to restore into $DB_NAME without --yes" >&2
    exit 3
  fi
  if command -v docker >/dev/null 2>&1 && docker compose ps db >/dev/null 2>&1; then
    docker compose exec -T -e PGPASSWORD="${DB_PASSWORD:-}" db \
      psql -U "$DB_USER" -d "$DB_NAME" < "$SQL"
  else
    require_binary psql "psql is needed to restore a postgres dump"
    PGARGS=(-U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT")
    # A brand-new server has no database yet: create it instead of failing.
    if ! PGPASSWORD="${DB_PASSWORD:-}" psql "${PGARGS[@]}" -d postgres -tAc \
         "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
      log "database $DB_NAME does not exist — creating it"
      PGPASSWORD="${DB_PASSWORD:-}" psql "${PGARGS[@]}" -d postgres \
        -c "CREATE DATABASE \"$DB_NAME\"" >/dev/null
    fi
    PGPASSWORD="${DB_PASSWORD:-}" psql "${PGARGS[@]}" -d "$DB_NAME" < "$SQL"
  fi
  log "restore finished into $DB_NAME"
fi

log "Restore complete. Log in and spot-check dashboard, a student profile and a fee receipt."
