#!/usr/bin/env bash
# Vercel Ignored Build Step (project root = web/):
#   exit 0 → skip deployment
#   exit 1 → run build
#
# Skip only when git can list every file changed since the last successful
# deployment and all of them are municipio-pipeline paths. If the previous
# SHA is missing, that commit is not in the clone, the diff fails, or the
# diff is empty, deploy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

BEFORE="${VERCEL_GIT_PREVIOUS_SHA:-}"
AFTER="${VERCEL_GIT_COMMIT_SHA:-HEAD}"

deploy() {
  echo "vercel-should-build: deploy ($1)"
  exit 1
}

# First fatal/error line of a captured git command, for the decision log.
first_reason() {
  local file="$1"
  local line=""
  line=$(grep -m1 -E '^(fatal|error):' "$file" 2>/dev/null || true)
  if [ -z "$line" ]; then
    line=$(grep -m1 -v '^[[:space:]]*$' "$file" 2>/dev/null || true)
  fi
  printf '%s' "$line"
}

on_err() {
  echo "vercel-should-build: deploy (unexpected error at line ${BASH_LINENO[0]:-?})"
  exit 1
}
trap on_err ERR

if [ -z "$BEFORE" ] || [ "$BEFORE" = "0000000000000000000000000000000000000000" ]; then
  deploy "no VERCEL_GIT_PREVIOUS_SHA"
fi

commit_exists() {
  set +e
  git cat-file -e "$1^{commit}" >/dev/null 2>&1
  local status=$?
  set -e
  return "$status"
}

if ! commit_exists "$BEFORE"; then
  echo "vercel-should-build: previous commit ${BEFORE} is not in this clone; trying git fetch --depth=1"
  fetch_log=$(mktemp)
  # `set +e` does not suppress the ERR trap; drop it around this expected failure.
  trap - ERR
  set +e
  if command -v timeout >/dev/null 2>&1; then
    GIT_TERMINAL_PROMPT=0 timeout 60 git fetch --depth=1 --no-tags origin "$BEFORE" >"$fetch_log" 2>&1
  else
    GIT_TERMINAL_PROMPT=0 git fetch --depth=1 --no-tags origin "$BEFORE" >"$fetch_log" 2>&1
  fi
  fetch_status=$?
  set -e
  trap on_err ERR
  if [ "$fetch_status" -ne 0 ] || ! commit_exists "$BEFORE"; then
    reason=$(first_reason "$fetch_log")
    rm -f "$fetch_log"
    if [ -n "${reason:-}" ]; then
      deploy "previous commit ${BEFORE} unavailable after fetch --depth=1 (${reason})"
    fi
    deploy "previous commit ${BEFORE} unavailable after fetch --depth=1"
  fi
  rm -f "$fetch_log"
  echo "vercel-should-build: fetched previous commit ${BEFORE}"
fi

diff_err=$(mktemp)
trap - ERR
set +e
diff_out=$(git diff --name-only "$BEFORE" "$AFTER" 2>"$diff_err")
diff_status=$?
set -e
trap on_err ERR
if [ "$diff_status" -ne 0 ]; then
  reason=$(first_reason "$diff_err")
  rm -f "$diff_err"
  if [ -n "${reason:-}" ]; then
    deploy "git diff failed: ${reason}"
  fi
  deploy "git diff failed"
fi
rm -f "$diff_err"

files=()
while IFS= read -r line || [ -n "$line" ]; do
  [ -n "$line" ] || continue
  files+=("$line")
done <<< "$diff_out"

if [ "${#files[@]}" -eq 0 ]; then
  deploy "empty diff ${BEFORE}..${AFTER}"
fi

municipio_only_path() {
  local f="$1"
  case "$f" in
    data/municipios/*) return 0 ;;
    municipio/*) return 0 ;;
    scripts/post-merge-municipio.sh|scripts/check-municipio-pr-static.sh|scripts/validate-municipio-onboard.sh|scripts/local-merge-municipio-batch.sh) return 0 ;;
    scripts/ci/municipio_batch.py|scripts/ci/test_municipio_batch.py) return 0 ;;
    requirements-municipio.txt) return 0 ;;
    .github/workflows/municipio-post-merge.yml) return 0 ;;
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
    deploy "${f}"
  fi
done

echo "vercel-should-build: skip municipio-only (${#files[@]} files)"
exit 0
