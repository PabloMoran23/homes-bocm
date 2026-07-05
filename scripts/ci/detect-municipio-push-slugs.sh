#!/usr/bin/env bash
# Detecta slugs de municipios tocados en un push a main (manifest.yaml).
set -euo pipefail

OUT="${GITHUB_OUTPUT:?GITHUB_OUTPUT required}"

python3 - <<'PY' >> "$OUT"
import json
import os
import re
import subprocess

manual = (os.environ.get("MANUAL_SLUG") or "").strip()
if manual:
    slugs = [] if manual == "_template" else [manual]
    print(f"slugs={json.dumps(slugs)}")
    raise SystemExit(0)

before = os.environ.get("GITHUB_EVENT_BEFORE") or ""
after = os.environ["GITHUB_SHA"]

if before in ("", "0000000000000000000000000000000000000000"):
    proc = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], capture_output=True, text=True)
else:
    proc = subprocess.run(["git", "diff", "--name-only", before, after], capture_output=True, text=True)

files = (proc.stdout or "").splitlines()
pat = re.compile(r"^data/municipios/([^/]+)/manifest\.yaml$")
seen: set[str] = set()
for line in files:
    m = pat.match(line.strip())
    if m and m.group(1) != "_template":
        seen.add(m.group(1))

print(f"slugs={json.dumps(sorted(seen))}")
PY
