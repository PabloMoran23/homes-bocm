#!/usr/bin/env bash
# Vercel Ignored Build Step (project root = web/):
#   exit 0 → skip deployment
#   exit 1 → run build
#
# Deploy only when a changed path is under web/, or is a file the production
# build reads outside web/ (prebuild of `npm run build:public`):
#   tests/license-date-cases.json  (web/scripts/test-license-dates.mjs)
#   db/statistics_scope.py         (web/scripts/test-statistics-scope.mjs)
# Any other diff is a skip. If the previous SHA is missing, that commit is
# not in the clone, the diff fails, or the diff is empty, deploy.
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
diff_out=$(git -c core.quotepath=false diff --name-status --find-renames "$BEFORE" "$AFTER" 2>"$diff_err")
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

# `git diff --name-only` hides the old path of a rename. A rename out of web/
# would otherwise look like a docs-only change and skip a build that lost a page.
affects_build() {
  local f="$1"
  case "$f" in
    web|web/*) return 0 ;;
    tests/license-date-cases.json|db/statistics_scope.py) return 0 ;;
  esac
  return 1
}

changed=0
reason=""
while IFS=$'\t' read -r status path1 path2 || [ -n "${status:-}" ]; do
  [ -n "${status:-}" ] || continue
  changed=$((changed + 1))
  if [ -z "$reason" ]; then
    if affects_build "$path1"; then
      reason=$path1
    elif [ -n "${path2:-}" ] && affects_build "$path2"; then
      reason=$path2
    fi
  fi
done <<< "$diff_out"

if [ "$changed" -eq 0 ]; then
  deploy "empty diff ${BEFORE}..${AFTER}"
fi
if [ -n "$reason" ]; then
  deploy "${reason}"
fi

echo "vercel-should-build: skip (no changes under web/, ${changed} files)"
exit 0
