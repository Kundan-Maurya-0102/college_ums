#!/usr/bin/env bash
# Update every college deployment to the same code — one command.
#
#   ./scripts/update_all.sh            # deploy current HEAD to all colleges
#   ./scripts/update_all.sh --dry-run  # show what would happen
#   ./scripts/update_all.sh --only gp-tekari,abc-college
#
# Each college keeps its own .env, DB and volumes (compose project per slug), so
# the code stays identical while data stays isolated.
set -uo pipefail
cd "$(dirname "$0")/.."

DRY_RUN=""
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN="--dry-run"; shift ;;
    --only) ONLY="$2"; shift 2 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done

shopt -s nullglob
ENVS=(deployments/*/.env)
if [ ${#ENVS[@]} -eq 0 ]; then
  echo "no deployments/*/.env found — create one with scripts/new_college.sh <slug>"
  exit 1
fi

TAG="$(git rev-parse --short HEAD)"
echo "updating $((${#ENVS[@]})) college(s) to $TAG${DRY_RUN:+ (dry run)}"

FAILED=()
SKIPPED=()
for env_file in "${ENVS[@]}"; do
  slug="$(basename "$(dirname "$env_file")")"
  if [ -n "$ONLY" ] && [[ ",$ONLY," != *",$slug,"* ]]; then
    SKIPPED+=("$slug")
    continue
  fi
  echo
  echo "── $slug ────────────────────────────────────────────────"
  if ./scripts/deploy.sh "$slug" --tag "$TAG" $DRY_RUN; then
    echo "OK   $slug"
  else
    echo "FAIL $slug"
    FAILED+=("$slug")
  fi
done

echo
echo "──────────────── summary ────────────────"
echo "tag:     $TAG"
echo "ok:      $(( ${#ENVS[@]} - ${#FAILED[@]} - ${#SKIPPED[@]} ))"
echo "failed:  ${#FAILED[@]} ${FAILED[*]:-}"
echo "skipped: ${#SKIPPED[@]} ${SKIPPED[*]:-}"
[ ${#FAILED[@]} -eq 0 ] || exit 1
