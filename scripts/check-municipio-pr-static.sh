#!/usr/bin/env bash
# Comprobaciones estáticas de una PR de onboarding (sin scrape del portal).
set -euo pipefail
cd "$(dirname "$0")/.."

SLUG="${1:?Uso: scripts/check-municipio-pr-static.sh <slug>}"

MANIFEST="data/municipios/$SLUG/manifest.yaml"
RESEARCH="data/municipios/$SLUG/RESEARCH.md"

echo "==> Check estático: $SLUG"

test -f "$MANIFEST" || { echo "FALTA: $MANIFEST"; exit 1; }
test -f "$RESEARCH" || { echo "FALTA: $RESEARCH"; exit 1; }

PYTHONPATH=. python3 - <<'PY' "$SLUG" "$MANIFEST"
import sys
import yaml
from pathlib import Path

slug = sys.argv[1]
manifest_path = Path(sys.argv[2])
raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
if raw.get("slug") != slug:
    raise SystemExit(f"slug manifest ({raw.get('slug')!r}) != argument ({slug!r})")

portal = raw.get("portal") or {}
adapter = portal.get("adapter")
if not adapter:
    raise SystemExit("portal.adapter vacío")

mod = adapter.split(":", 1)[0].strip()
if not mod.startswith("municipio.adapters."):
    raise SystemExit(f"adapter inválido: {adapter!r}")

rel = mod.replace(".", "/") + ".py"
path = Path(rel)
if not path.is_file():
    raise SystemExit(f"Falta módulo adapter: {rel}")

__import__(mod)
print(f"OK import {mod}")
print(f"comunidad_autonoma={raw.get('comunidad_autonoma')!r}")
print(f"portal.base_url={portal.get('base_url')!r}")
PY

echo "OK: check estático $SLUG"
