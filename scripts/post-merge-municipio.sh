#!/usr/bin/env bash
# Post-merge: marca cola, pipeline completo y sync Supabase (local o GitHub Actions).
set -euo pipefail
cd "$(dirname "$0")/.."

SLUG="${1:?Uso: scripts/post-merge-municipio.sh <slug> [pr-url]}"
PR_URL="${2:-}"

NOTES="${POST_MERGE_NOTES:-Mergeado por automation merge-babysitter}"
if [ -n "${GITHUB_ACTIONS:-}" ]; then
  NOTES="Post-merge GitHub Actions (${GITHUB_WORKFLOW:-workflow}) run ${GITHUB_RUN_ID:-}"
fi

echo "==> Post-merge: $SLUG"

if [ -n "$PR_URL" ]; then
  PYTHONPATH=. python3 -m municipio queue done --municipio "$SLUG" --pr-url "$PR_URL" --notes "$NOTES"
else
  PYTHONPATH=. python3 -m municipio queue done --municipio "$SLUG" --notes "$NOTES"
fi

if [ -n "${GITHUB_ACTIONS:-}" ] && [ -z "${SUPABASE_DB_URL:-${DATABASE_URL:-}}" ]; then
  echo "ERROR: SUPABASE_DB_URL requerida en GitHub Actions" >&2
  exit 1
fi

if [ -n "${SUPABASE_DB_URL:-${DATABASE_URL:-}}" ]; then
  PYTHONPATH=. python3 -m municipio run --municipio "$SLUG" --step all
else
  echo "Aviso: sin SUPABASE_DB_URL — pipeline completo omitido (solo queue done)"
  PYTHONPATH=. python3 -m municipio run --municipio "$SLUG" --step validate || true
fi

echo "OK: post-merge $SLUG"
