#!/usr/bin/env bash
# Vercel Ignored Build Step (project root = web/):
#   exit 0 → skip deployment
#   exit 1 → run build
#
# Deploy only when a changed path is under web/, or is a file the production
# build reads outside web/ (prebuild of `npm run build:public`):
#   tests/license-date-cases.json  (web/scripts/test-license-dates.mjs)
#   db/statistics_scope.py         (web/scripts/test-statistics-scope.mjs)
# An explicit [skip deploy] in the current commit skips all deployment.
# Previews compare the whole branch against main, including the first preview.
# Production compares the incoming merge/squash commit against its first parent.
# The last successful deployment can lag intentionally skipped web changes and
# must not make a later municipality-only PR deploy them accidentally.
# Unavailable preview history skips the build: only verified web changes deploy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"

BEFORE="${VERCEL_GIT_PREVIOUS_SHA:-}"
AFTER="${VERCEL_GIT_COMMIT_SHA:-HEAD}"
FETCH_REMOTE=origin
# Vercel can reconstruct .git without retaining any configured remote.
if ! git remote get-url origin >/dev/null 2>&1; then
  FETCH_REMOTE="https://github.com/${VERCEL_GIT_REPO_OWNER:-PabloMoran23}/${VERCEL_GIT_REPO_SLUG:-homes-bocm}.git"
fi

deploy() {
  echo "vercel-should-build: deploy ($1)"
  exit 1
}

skip_unverified() {
  echo "vercel-should-build: skip (unverified web changes: $1)"
  exit 0
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

# Administrative onboarding batches must stay quiet even on the first deployment
# or when their safety changes touch web/. Trust the actual checked-out commit.
if commit_message=$(git log -1 --format=%B "$AFTER" 2>/dev/null); then
  if [[ "$commit_message" == *"[skip deploy]"* ]]; then
    echo "vercel-should-build: skip (explicit [skip deploy] in commit)"
    exit 0
  fi
fi

commit_exists() {
  set +e
  git cat-file -e "$1^{commit}" >/dev/null 2>&1
  local status=$?
  set -e
  return "$status"
}

fetch_history() {
  if command -v timeout >/dev/null 2>&1; then
    GIT_TERMINAL_PROMPT=0 timeout 30 git fetch --no-tags "$@"
  else
    GIT_TERMINAL_PROMPT=0 git fetch --no-tags "$@"
  fi
}

if [ "${VERCEL_ENV:-}" = "preview" ]; then
  # VERCEL_GIT_PREVIOUS_SHA is absent on a branch's first deployment. Comparing
  # only HEAD^ also misses web changes earlier in a multi-commit PR.
  preview_fetch_args=()
  if [ "$(git rev-parse --is-shallow-repository)" = "true" ]; then
    preview_fetch_args+=(--depth=100)
  fi
  if ! fetch_history "${preview_fetch_args[@]}" "$FETCH_REMOTE" '+refs/heads/main:refs/remotes/origin/main'; then
    skip_unverified "cannot fetch preview base main"
  fi
  if ! BEFORE=$(git merge-base "$AFTER" refs/remotes/origin/main); then
    # Vercel clones only a short history. Deepen the branch and main together.
    if ! fetch_history --deepen=1000 "$FETCH_REMOTE" "$AFTER" '+refs/heads/main:refs/remotes/origin/main'; then
      skip_unverified "cannot recover preview merge base"
    fi
    BEFORE=$(git merge-base "$AFTER" refs/remotes/origin/main) || skip_unverified "preview merge base unavailable"
  fi
  echo "vercel-should-build: comparing preview against main merge base ${BEFORE}"
elif [ "${VERCEL_ENV:-}" = "production" ]; then
  if ! BEFORE=$(git rev-parse --verify "${AFTER}^1" 2>/dev/null); then
    if ! fetch_history --depth=2 "$FETCH_REMOTE" "$AFTER"; then
      deploy "cannot recover production parent"
    fi
    BEFORE=$(git rev-parse --verify "${AFTER}^1" 2>/dev/null) || deploy "production parent unavailable"
  fi
  echo "vercel-should-build: comparing production commit against parent ${BEFORE}"
fi

if [ -z "$BEFORE" ] || [ "$BEFORE" = "0000000000000000000000000000000000000000" ]; then
  deploy "no VERCEL_GIT_PREVIOUS_SHA"
fi

if ! commit_exists "$BEFORE"; then
  echo "vercel-should-build: previous commit ${BEFORE} is not in this clone; trying git fetch --depth=1"
  fetch_log=$(mktemp)
  # `set +e` does not suppress the ERR trap; drop it around this expected failure.
  trap - ERR
  set +e
  if command -v timeout >/dev/null 2>&1; then
    GIT_TERMINAL_PROMPT=0 timeout 60 git fetch --depth=1 --no-tags "$FETCH_REMOTE" "$BEFORE" >"$fetch_log" 2>&1
  else
    GIT_TERMINAL_PROMPT=0 git fetch --depth=1 --no-tags "$FETCH_REMOTE" "$BEFORE" >"$fetch_log" 2>&1
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
  if [ "${VERCEL_ENV:-}" = "preview" ]; then
    echo "vercel-should-build: skip (no changes under web/, 0 files; preview already included in main)"
    exit 0
  fi
  deploy "empty diff ${BEFORE}..${AFTER}"
fi
if [ -n "$reason" ]; then
  deploy "${reason}"
fi

echo "vercel-should-build: skip (no changes under web/, ${changed} files)"
exit 0
