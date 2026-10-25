#!/usr/bin/env bash
# Cases for web/scripts/vercel-should-build.sh:
#   no previous SHA, failed diff, empty diff,
#   outside web/ skips, inside web/ deploys, a mix deploys,
#   the two build inputs outside web/ deploy, a rename out of web/ deploys,
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
      *"vercel-should-build: skip (no changes under web/"*) ;;
      *)
        fail "$name: skip without the web/ log. output: $out"
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

commit() {
  local repo="$1"
  local message="$2"
  git -C "$repo" add .
  git -C "$repo" commit -q -m "$message"
  git -C "$repo" rev-parse HEAD
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
    "$repo/db" \
    "$repo/tests" \
    "$repo/docs" \
    "$repo/web/app" \
    "$repo/.github/workflows"
  printf 'a\n' > "$repo/data/municipios/madrid/manifest.yaml"
  printf 'a\n' > "$repo/municipio/cli.py"
  FIX_BASE="$(commit "$repo" "base")"

  printf 'b\n' > "$repo/data/municipios/madrid/manifest.yaml"
  printf 'b\n' > "$repo/municipio/cli.py"
  FIX_OUTSIDE="$(commit "$repo" "outside web")"

  printf 'page\n' > "$repo/web/app/page.tsx"
  FIX_WEB="$(commit "$repo" "web only")"

  printf '{}\n' > "$repo/tests/license-date-cases.json"
  FIX_LICENSE="$(commit "$repo" "license fixtures")"

  printf 'db\n' > "$repo/db/test_license_dates.py"
  FIX_DB_OTHER="$(commit "$repo" "unrelated db")"

  printf 'scope\n' > "$repo/db/statistics_scope.py"
  FIX_SCOPE="$(commit "$repo" "statistics scope")"

  printf 'page2\n' > "$repo/web/app/page.tsx"
  printf 'name: refresh\n' > "$repo/.github/workflows/refresh-municipios.yml"
  FIX_MIX="$(commit "$repo" "mix")"

  git -C "$repo" mv web/app/page.tsx docs/page.tsx
  FIX_RENAME="$(commit "$repo" "rename out of web")"
  install_script "$repo"
}

make_fixture

SCRIPT="$TMP/origin/web/scripts/vercel-should-build.sh"

run_case "no previous SHA" 1 "no VERCEL_GIT_PREVIOUS_SHA" \
  env -u VERCEL_GIT_PREVIOUS_SHA VERCEL_GIT_COMMIT_SHA="$FIX_RENAME" \
  bash "$SCRIPT"

run_case "zero previous SHA" 1 "no VERCEL_GIT_PREVIOUS_SHA" \
  env VERCEL_GIT_PREVIOUS_SHA="0000000000000000000000000000000000000000" \
  VERCEL_GIT_COMMIT_SHA="$FIX_RENAME" \
  bash "$SCRIPT"

run_case "diff fails" 1 "git diff failed" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_RENAME" \
  VERCEL_GIT_COMMIT_SHA="deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" \
  bash "$SCRIPT"

run_case "empty diff" 1 "empty diff ${FIX_RENAME}..${FIX_RENAME}" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_RENAME" VERCEL_GIT_COMMIT_SHA="$FIX_RENAME" \
  bash "$SCRIPT"

run_case "outside web only" 0 "skip (no changes under web/, 2 files)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_BASE" VERCEL_GIT_COMMIT_SHA="$FIX_OUTSIDE" \
  bash "$SCRIPT"

run_case "inside web only" 1 "deploy (web/app/page.tsx)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_OUTSIDE" VERCEL_GIT_COMMIT_SHA="$FIX_WEB" \
  bash "$SCRIPT"

run_case "mix deploys" 1 "deploy (web/app/page.tsx)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_SCOPE" VERCEL_GIT_COMMIT_SHA="$FIX_MIX" \
  bash "$SCRIPT"

run_case "license fixtures deploy" 1 "deploy (tests/license-date-cases.json)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_WEB" VERCEL_GIT_COMMIT_SHA="$FIX_LICENSE" \
  bash "$SCRIPT"

run_case "unrelated db skips" 0 "skip (no changes under web/, 1 files)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_LICENSE" VERCEL_GIT_COMMIT_SHA="$FIX_DB_OTHER" \
  bash "$SCRIPT"

run_case "statistics scope deploys" 1 "deploy (db/statistics_scope.py)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_DB_OTHER" VERCEL_GIT_COMMIT_SHA="$FIX_SCOPE" \
  bash "$SCRIPT"

run_case "rename out of web deploys" 1 "deploy (web/app/page.tsx)" \
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_MIX" VERCEL_GIT_COMMIT_SHA="$FIX_RENAME" \
  bash "$SCRIPT"

# Depth-1 clone does not contain the previous commit. Fetch must recover it.
git clone --quiet --depth=1 "file://$TMP/origin" "$TMP/shallow"
install_script "$TMP/shallow"
SHALLOW_SCRIPT="$TMP/shallow/web/scripts/vercel-should-build.sh"
shallow_out=$(
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_MIX" VERCEL_GIT_COMMIT_SHA="$FIX_RENAME" \
  bash "$SHALLOW_SCRIPT" 2>&1
) && shallow_code=0 || shallow_code=$?
if [ "$shallow_code" -ne 1 ]; then
  fail "shallow clone fetches missing commit: exit $shallow_code. output: $shallow_out"
else
  case "$shallow_out" in
    *"fetched previous commit ${FIX_MIX}"*"deploy (web/app/page.tsx)"*)
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
  env VERCEL_GIT_PREVIOUS_SHA="$FIX_MIX" VERCEL_GIT_COMMIT_SHA="$FIX_RENAME" \
  bash "$TMP/shallow-fail/web/scripts/vercel-should-build.sh"

# ef510d6 touches web/app and must deploy. 891af37 and 11312bf do not.
run_case "ef510d6 deploys web/app" 1 "deploy (web/app/page.tsx)" \
  env VERCEL_GIT_PREVIOUS_SHA="891af373adab5c63203620683c1edae3263bb8dd" \
  VERCEL_GIT_COMMIT_SHA="ef510d637d2c5f048e3b8f8b529baf9d7757bf0e" \
  bash "$ROOT/web/scripts/vercel-should-build.sh"

run_case "891af37 skips outside web" 0 "skip (no changes under web/, 5 files)" \
  env VERCEL_GIT_PREVIOUS_SHA="11312bfda51ccefe7037174ee77a4a6eb4de41db" \
  VERCEL_GIT_COMMIT_SHA="891af373adab5c63203620683c1edae3263bb8dd" \
  bash "$ROOT/web/scripts/vercel-should-build.sh"

run_case "11312bf skips outside web" 0 "skip (no changes under web/, 7 files)" \
  env VERCEL_GIT_PREVIOUS_SHA="49d6d95" \
  VERCEL_GIT_COMMIT_SHA="11312bfda51ccefe7037174ee77a4a6eb4de41db" \
  bash "$ROOT/web/scripts/vercel-should-build.sh"

if [ "$failures" -ne 0 ]; then
  echo "$failures test(s) failed" >&2
  exit 1
fi
echo "all vercel-should-build cases passed"
