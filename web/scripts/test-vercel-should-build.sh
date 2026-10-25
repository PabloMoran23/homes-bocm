#!/usr/bin/env bash
# Cases for web/scripts/vercel-should-build.sh:
#   no previous SHA, failed diff, empty diff, municipio-only, code change,
#   plus a shallow clone whose previous commit must be fetched.
set -euo pipefail

SCRIPT_SRC="$(cd "$(dirname "$0")" && pwd)/vercel-should-build.sh"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

failures=0

fail() {
  echo "FAIL: $*" >&2
  failures=$((failures + 1))
}

run_case() {
  local name="$1"
  local expected="$2"
  local needle="$3"
  shift 3
  local out code
  set +e
  out=$("$@" 2>&1)
  code=$?
  set -e
  if [ "$code" -ne "$expected" ]; then
    fail "$name: exit $code, expected $expected. output: $out"
    return
  fi
  case "$out" in
    *"$needle"*) ;;
    *)
      fail "$name: output missing [$needle]. output: $out"
      return
      ;;
  esac
  if [ "$expected" -eq 0 ]; then
    case "$out" in
      *"vercel-should-build: skip municipio-only"*) ;;
      *)
        fail "$name: skip without the municipio-only log. output: $out"
        return
        ;;
    esac
  else
    case "$out" in
      *"vercel-should-build: deploy"*) ;;
      *)
        fail "$name: deploy without a reason. output: $out"
        return
        ;;
    esac
  fi
  echo "ok $name"
  echo "$out" | sed 's/^/   /'
}

install_script() {
  local repo="$1"
  mkdir -p "$repo/web/scripts"
  cp "$SCRIPT_SRC" "$repo/web/scripts/vercel-should-build.sh"
  chmod +x "$repo/web/scripts/vercel-should-build.sh"
}

make_fixture() {
  local repo="$TMP/origin"
  mkdir -p "$repo"
  git -C "$repo" init -q -b main
  git -C "$repo" config user.email "test@example.com"
  git -C "$repo" config user.name "test"
  mkdir -p \
    "$repo/data/municipios/madrid" \
    "$repo/municipio" \
    "$repo/scripts/ci" \
    "$repo/docs" \
    "$repo/web/app" \
    "$repo/.github/workflows"
  printf 'a\n' > "$repo/data/municipios/madrid/manifest.yaml"
  printf 'a\n' > "$repo/municipio/cli.py"
  printf 'a\n' > "$repo/scripts/ci/municipio_batch.py"
  printf 'a\n' > "$repo/docs/municipio-batch-notes.md"
  printf 'a\n' > "$repo/requirements-municipio.txt"
  git -C "$repo" add .
  git -C "$repo" commit -q -m "municipio base"
  FIX_BASE="$(git -C "$repo" rev-parse HEAD)"

  printf 'b\n' > "$repo/data/municipios/madrid/manifest.yaml"
  printf 'b\n' > "$repo/municipio/cli.py"
  git -C "$repo" add .
  git -C "$repo" commit -q -m "municipio only"
  FIX_MUNICIPIO="$(git -C "$repo" rev-parse HEAD)"

  printf 'code\n' > "$repo/web/app/page.tsx"
  printf 'name: refresh\n' > "$repo/.github/workflows/refresh-municipios.yml"
  git -C "$repo" add .
  git -C "$repo" commit -q -m "code"
  FIX_CODE="$(git -C "$repo" rev-parse HEAD)"
  install_script "$repo"
}

make_fixture

SCRIPT="$TMP/origin/web/scripts/vercel-should-build.sh"

run_case "no previous SHA" 1 "no VERCEL_GIT_PREVIOUS_SHA" \
  env -u VERCEL_GIT_PREVIOUS_SHA VERCEL_GIT_COMMIT_SHA="$FIX_CODE" \
  bash "$SCRIPT"

run_case "zero previous SHA" 1 "no VERCEL_GIT_PREVIOUS_SHA" \
  env VERCEL_GIT_PREVIOUS_SHA="0000000000000000000000000000000000000000" \
  VERCEL_GIT_COMMIT_SHA="$FIX_CODE" \
  bash "$SCRIPT"

run_case "diff fails" 1 "git diff failed" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_CODE" \
  VERCEL_GIT_COMMIT_SHA="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" \
  bash "$SCRIPT"

run_case "empty diff" 1 "empty diff ${FIX_CODE}..${FIX_CODE}" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_CODE" VERCEL_GIT_COMMIT_SHA="$FIX_CODE" \
  bash "$SCRIPT"

run_case "municipio only" 0 "skip municipio-only (2 files)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_BASE" VERCEL_GIT_COMMIT_SHA="$FIX_MUNICIPIO" \
  bash "$SCRIPT"

run_case "code change" 1 "deploy (.github/workflows/refresh-municipios.yml)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_MUNICIPIO" VERCEL_GIT_COMMIT_SHA="$FIX_CODE" \
  bash "$SCRIPT"

# Depth-1 clone does not contain the previous commit. Fetch must recover it.
git clone --quiet --depth=1 "file://$TMP/origin" "$TMP/shallow"
install_script "$TMP/shallow"
SHALLOW_SCRIPT="$TMP/shallow/web/scripts/vercel-should-build.sh"
shallow_out=$(
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_MUNICIPIO" VERCEL_GIT_COMMIT_SHA="$FIX_CODE" \
  bash "$SHALLOW_SCRIPT" 2>&1
) && shallow_code=0 || shallow_code=$?
if [ "$shallow_code" -ne 1 ]; then
  fail "shallow clone fetches missing commit: exit $shallow_code. output: $shallow_out"
else
  case "$shallow_out" in
    *"fetched previous commit ${FIX_MUNICIPIO}"*"deploy (.github/workflows/refresh-municipios.yml)"*)
      echo "ok shallow clone fetches missing commit"
      echo "$shallow_out" | sed 's/^/   /'
      ;;
    *) fail "shallow clone fetches missing commit: output: $shallow_out" ;;
  esac
fi

# A remote that cannot serve the SHA must still deploy, not skip.
git clone --quiet --depth=1 "file://$TMP/origin" "$TMP/shallow-fail"
install_script "$TMP/shallow-fail"
git -C "$TMP/shallow-fail" remote set-url origin "$TMP/not-a-repo"
run_case "shallow fetch failure deploys" 1 "unavailable after fetch --depth=1" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_MUNICIPIO" VERCEL_GIT_COMMIT_SHA="$FIX_CODE" \
  bash "$TMP/shallow-fail/web/scripts/vercel-should-build.sh"

# The production commits that were canceled are not municipio-only.
run_case "ef510d6 code change" 1 "deploy (db/export_sitemap_projects.py)" \
  env VERCEL_GIT_PREVIOUS_SHA="891af373adab5c63203620683c1edae3263bb8dd" \
  VERCEL_GIT_COMMIT_SHA="ef510d637d2c5f048e3b8f8b529baf9d7757bf0e" \
  bash "$ROOT/web/scripts/vercel-should-build.sh"

run_case "11312bf against last successful deploy" 1 "deploy (.cursor/prompts/merge-municipio-prs.md)" \
  env VERCEL_GIT_PREVIOUS_SHA="ae7822ad93de7920f541f3747f6a27b600e87272" \
  VERCEL_GIT_COMMIT_SHA="11312bfda51ccefe7037174ee77a4a6eb4de41db" \
  bash "$ROOT/web/scripts/vercel-should-build.sh"

if [ "$failures" -ne 0 ]; then
  echo "$failures test(s) failed" >&2
  exit 1
fi
echo "all vercel-should-build cases passed"
