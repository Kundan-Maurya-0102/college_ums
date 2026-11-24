#!/usr/bin/env bash
# Nightly Postgres backup for one College UMS deployment.
#
# Usage (from the deployment directory that holds .env):
#   ./scripts/backup_db.sh                 # writes to ./backups/<slug>-YYYYmmdd-HHMM.sql.gz
#   BACKUP_DIR=/mnt/backups ./scripts/backup_db.sh
#   RETENTION_DAYS=14 ./scripts/backup_db.sh
#
# Cron (2:30 AM daily):
#   30 2 * * * cd /opt/ums/mycollage && ./scripts/backup_db.sh >> /var/log/ums-backup.log 2>&1
set -euo pipefail

ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found. Run this from the deployment directory." >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; source "$ENV_FILE"; set +a

DB_NAME="${DB_NAME:-${POSTGRES_DB:-ums}}"
DB_USER="${DB_USER:-${POSTGRES_USER:-ums}}"
DB_HOST="${DB_HOST:-${POSTGRES_HOST:-db}}"
DB_PORT="${DB_PORT:-${POSTGRES_PORT:-5432}}"
SLUG="${COLLEGE_SLUG:-$(basename "$PWD")}"

mkdir -p "$BACKUP_DIR"
STAMP="$(date +%Y%m%d-%H%M)"
OUT="$BACKUP_DIR/${SLUG}-${STAMP}.sql.gz"

echo "[$(date -Is)] dumping $DB_NAME from $DB_HOST:$DB_PORT"

if command -v docker >/dev/null 2>&1 && docker compose ps db >/dev/null 2>&1; then
  # Database runs in the compose project: dump from inside the container.
  docker compose exec -T -e PGPASSWORD="${DB_PASSWORD:-${POSTGRES_PASSWORD:-}}" db \
    pg_dump -U "$DB_USER" -h localhost "$DB_NAME" | gzip -9 > "$OUT"
else
  PGPASSWORD="${DB_PASSWORD:-${POSTGRES_PASSWORD:-}}" pg_dump \
    -U "$DB_USER" -h "$DB_HOST" -p "$DB_PORT" "$DB_NAME" | gzip -9 > "$OUT"
fi

# Fail loudly on an empty/failed dump instead of keeping a useless file.
if [[ ! -s "$OUT" ]]; then
  echo "ERROR: backup file is empty: $OUT" >&2
  rm -f "$OUT"
  exit 1
fi

echo "[$(date -Is)] wrote $OUT ($(du -h "$OUT" | cut -f1))"

# Retention
find "$BACKUP_DIR" -name "${SLUG}-*.sql.gz" -type f -mtime "+${RETENTION_DAYS}" -print -delete

# Restore (documented, never run automatically):
#   gunzip -c backups/<file>.sql.gz | docker compose exec -T db psql -U <user> <db>
