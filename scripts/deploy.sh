#!/usr/bin/env bash
# Deploy one college (one compose project) — build, backup, migrate, health-check.
# Rollback to the previously deployed image tag with --rollback.
#
#   ./scripts/deploy.sh <slug> [--tag <git-ref>] [--rollback] [--no-backup] [--dry-run]
#
# Layout expected on the server:
#   deployments/<slug>/.env      (per-college secrets + COLLEGE_* branding)
#   releases/<slug>/<tag>.json   (deployed tags, newest last)
set -euo pipefail
cd "$(dirname "$0")/.."

SLUG="${1:-}"
[ -z "$SLUG" ] && { echo "usage: $0 <slug> [--tag <ref>] [--rollback] [--no-backup] [--dry-run]" >&2; exit 2; }
shift || true

TAG=""
ROLLBACK=0
DO_BACKUP=1
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --tag) TAG="$2"; shift 2 ;;
    --rollback) ROLLBACK=1; shift ;;
    --no-backup) DO_BACKUP=0; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
ENV_FILE="deployments/$SLUG/.env"
[ -f "$ENV_FILE" ] || { echo "missing $ENV_FILE (run scripts/new_college.sh $SLUG)" >&2; exit 1; }
RELEASE_DIR="releases/$SLUG"
mkdir -p "$RELEASE_DIR"
HISTORY="$RELEASE_DIR/tags.txt"
touch "$HISTORY"

run() { if [ "$DRY_RUN" = 1 ]; then echo "[dry-run] $*"; else "$@"; fi; }

env_get() { grep -m1 "^$1=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true; }

if [ "$ROLLBACK" = 1 ]; then
  PREVIOUS="$(tail -n 2 "$HISTORY" | head -n 1)"
  [ -z "$PREVIOUS" ] && { echo "no previous tag recorded for $SLUG — nothing to roll back to" >&2; exit 1; }
  TAG="$PREVIOUS"
  echo "==> rolling back $SLUG to $TAG"
elif [ -z "$TAG" ]; then
  TAG="$(git rev-parse --short HEAD)"
fi

DOMAIN="$(env_get COLLEGE_DOMAIN)"
DOMAIN="${DOMAIN:-$(env_get ALLOWED_HOSTS | cut -d, -f1)}"
HEALTH_URL="https://${DOMAIN}/healthz/"

# 1. backup before we touch the schema
if [ "$DO_BACKUP" = 1 ]; then
  echo "==> backup $SLUG"
  if [ -x scripts/backup_db.sh ]; then
    run env ENV_FILE="$ENV_FILE" ./scripts/backup_db.sh || \
      { echo "backup failed — refusing to deploy" >&2; exit 1; }
  fi
fi

# 2. build + migrate + restart with the new tag
echo "==> deploying $SLUG @ $TAG"
export GIT_TAG="$TAG"
run docker compose -p "$SLUG" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build
run docker compose -p "$SLUG" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm web python manage.py migrate --noinput
run docker compose -p "$SLUG" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans

# 3. health check (retry: containers need a few seconds)
if [ "$DRY_RUN" = 0 ]; then
  echo "==> health check $HEALTH_URL"
  for i in $(seq 1 20); do
    if curl -fsS --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
      echo "==> healthy after ${i} attempt(s)"
      echo "$TAG" >> "$HISTORY"
      echo "$SLUG deployed: $TAG"
      exit 0
    fi
    sleep 3
  done
  echo "!! health check failed for $SLUG — rolling back" >&2
  docker compose -p "$SLUG" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs --tail 60 web >&2 || true
  PREVIOUS="$(tail -n 2 "$HISTORY" | head -n 1)"
  if [ -n "$PREVIOUS" ] && [ "$PREVIOUS" != "$TAG" ]; then
    GIT_TAG="$PREVIOUS" docker compose -p "$SLUG" -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d --remove-orphans
    echo "rolled back to $PREVIOUS" >&2
  fi
  exit 1
fi
