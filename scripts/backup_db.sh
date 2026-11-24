#!/usr/bin/env bash
# Encrypted database backup for one College UMS deployment.
#
#   ./scripts/backup_db.sh                          # postgres via docker compose (prod default)
#   DB_ENGINE=sqlite DB_PATH=db.sqlite3 ./scripts/backup_db.sh
#   BACKUP_DIR=/mnt/backups RETENTION_DAYS=14 ./scripts/backup_db.sh
#
# Encryption (required unless ALLOW_UNENCRYPTED_BACKUP=1):
#   BACKUP_ENCRYPTION_KEY = long random passphrase, stored in the deployment .env,
#   never in git. Generate one:  openssl rand -base64 32
#
# Cron (2:30 AM daily):
#   30 2 * * * cd /opt/ums/<slug> && ./scripts/backup_db.sh >> /var/log/ums-backup.log 2>&1
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

BACKUP_DIR="${BACKUP_DIR:-$(env_get BACKUP_DIR || echo backups)}"
RETENTION_DAYS="${RETENTION_DAYS:-$(env_get RETENTION_DAYS || echo 14)}"
DB_ENGINE="${DB_ENGINE:-$(env_get DB_ENGINE || echo postgres)}"
SLUG="${COLLEGE_SLUG:-$(env_get COLLEGE_SLUG || basename "$PWD")}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M)"
BASE="$BACKUP_DIR/${SLUG}-${STAMP}.sql.gz"

log() { echo "[$(date -Is)] $*"; }

dump_postgres() {
  local db_name="${DB_NAME:-$(env_get DB_NAME || env_get POSTGRES_DB || echo ums)}"
  local db_user="${DB_USER:-$(env_get DB_USER || env_get POSTGRES_USER || echo ums)}"
  local db_host="${DB_HOST:-$(env_get DB_HOST || echo db)}"
  local db_port="${DB_PORT:-$(env_get DB_PORT || echo 5432)}"
  local db_password="${DB_PASSWORD:-$(env_get DB_PASSWORD || env_get POSTGRES_PASSWORD || true)}"

  if command -v docker >/dev/null 2>&1 && docker compose ps db >/dev/null 2>&1; then
    docker compose exec -T -e PGPASSWORD="$db_password" db \
      pg_dump -U "$db_user" -h localhost "$db_name"
  else
    PGPASSWORD="$db_password" pg_dump -U "$db_user" -h "$db_host" -p "$db_port" "$db_name"
  fi
}

dump_sqlite() {
  local db_path="${DB_PATH:-$(env_get DB_PATH || echo db.sqlite3)}"
  [[ -f "$db_path" ]] || { log "ERROR: sqlite DB not found: $db_path"; exit 1; }
  # iterdump produces a portable SQL script (same role as pg_dump output)
  "$PYTHON_BIN" - "$db_path" <<'PY'
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
try:
    for line in conn.iterdump():
        print(line)
finally:
    conn.close()
PY
}

log "backing up engine=$DB_ENGINE slug=$SLUG"

case "$DB_ENGINE" in
  postgres|postgresql) dump_postgres | gzip -9 > "$BASE" ;;
  sqlite|sqlite3)      dump_sqlite   | gzip -9 > "$BASE" ;;
  *) log "ERROR: unknown DB_ENGINE '$DB_ENGINE' (use postgres|sqlite)"; exit 1 ;;
esac

if [[ ! -s "$BASE" ]]; then
  log "ERROR: dump is empty, removing $BASE"
  rm -f "$BASE"
  exit 1
fi

# gzip integrity check before encrypting
gzip -t "$BASE"

OUT="$BASE"
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-$(env_get BACKUP_ENCRYPTION_KEY || true)}"
if [[ -n "${BACKUP_ENCRYPTION_KEY:-}" ]]; then
  OUT="${BASE}.enc"
  openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt \
    -pass env:BACKUP_ENCRYPTION_KEY -in "$BASE" -out "$OUT"
  rm -f "$BASE"
  chmod 600 "$OUT"
  # Verify we can decrypt what we just wrote
  openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
    -pass env:BACKUP_ENCRYPTION_KEY -in "$OUT" | gzip -t
  log "encrypted backup written: $OUT ($(du -h "$OUT" | cut -f1))"
elif [[ "${ALLOW_UNENCRYPTED_BACKUP:-0}" == "1" ]]; then
  chmod 600 "$OUT"
  log "WARNING: unencrypted backup written (ALLOW_UNENCRYPTED_BACKUP=1): $OUT"
else
  rm -f "$OUT"
  log "ERROR: BACKUP_ENCRYPTION_KEY is not set; refusing to write a plaintext backup."
  log "Generate one with: openssl rand -base64 32  (store in .env, never in git)"
  log "Override for local dev only: ALLOW_UNENCRYPTED_BACKUP=1"
  exit 1
fi

find "$BACKUP_DIR" -maxdepth 1 -type f \( -name "${SLUG}-*.sql.gz" -o -name "${SLUG}-*.sql.gz.enc" \) \
  -mtime "+${RETENTION_DAYS}" -print -delete

# Restore:
#   ./scripts/restore_db.sh --file backups/<file>.sql.gz.enc --yes
