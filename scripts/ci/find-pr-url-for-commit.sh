#!/usr/bin/env bash
# URL de la PR mergeada asociada al commit actual (si existe).
set -euo pipefail

REPO="${GITHUB_REPOSITORY:?}"
SHA="${GITHUB_SHA:?}"

URL=""
if command -v gh >/dev/null 2>&1; then
  URL=$(gh api "repos/${REPO}/commits/${SHA}/pulls" --jq '.[0].html_url // empty' 2>/dev/null || true)
fi

{
  echo "url<<EOF"
  echo "$URL"
  echo "EOF"
} >> "${GITHUB_OUTPUT:?GITHUB_OUTPUT required}"
