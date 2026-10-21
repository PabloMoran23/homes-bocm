#!/usr/bin/env bash
# Vercel Ignored Build Step (project root = web/):
#   exit 0 → skip deployment
#   exit 1 → run build
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

BEFORE="${VERCEL_GIT_PREVIOUS_SHA:-}"
AFTER="${VERCEL_GIT_COMMIT_SHA:-HEAD}"

if [ -z "$BEFORE" ] || [ "$BEFORE" = "0000000000000000000000000000000000000000" ]; then
  exit 1
fi

mapfile -t files < <(git diff --name-only "$BEFORE" "$AFTER" 2>/dev/null || true)
if [ ${#files[@]} -eq 0 ]; then
  exit 0
fi

municipio_only_path() {
  local f="$1"
  case "$f" in
    data/municipios/*) return 0 ;;
    municipio/*) return 0 ;;
    scripts/post-merge-municipio.sh|scripts/check-municipio-pr-static.sh|scripts/validate-municipio-onboard.sh|scripts/local-merge-municipio-batch.sh) return 0 ;;
    scripts/ci/municipio_batch.py|scripts/ci/test_municipio_batch.py) return 0 ;;
    requirements-municipio.txt) return 0 ;;
    .github/workflows/municipio-post-merge.yml|.github/workflows/validate-municipio-pr.yml) return 0 ;;
    docs/automation-onboard-municipio.md|docs/automation-merge-municipio-prs.md|docs/geography-control.md) return 0 ;;
    tools/review_municipio_backlog.py) return 0 ;;
  esac
  case "$f" in
    docs/municipio-batch*) return 0 ;;
  esac
  return 1
}

for f in "${files[@]}"; do
  if ! municipio_only_path "$f"; then
    echo "vercel-should-build: deploy (${f})"
    exit 1
  fi
done

echo "vercel-should-build: skip municipio-only (${#files[@]} files)"
exit 0
