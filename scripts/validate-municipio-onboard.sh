#!/usr/bin/env bash
# Valida que un municipio onboarded cumple paridad mínima antes de merge.
set -euo pipefail
cd "$(dirname "$0")/.."

SLUG="${1:?Uso: scripts/validate-municipio-onboard.sh <slug>}"

echo "==> Validando municipio: $SLUG"

test -f "data/municipios/$SLUG/manifest.yaml" || { echo "Falta manifest.yaml"; exit 1; }
test -f "data/municipios/$SLUG/RESEARCH.md" || { echo "Falta RESEARCH.md"; exit 1; }

PYTHONPATH=. python -m municipio run --municipio "$SLUG" --step validate

PARITY="output/municipios/$SLUG/parity-report.json"
test -f "$PARITY" || { echo "Falta parity-report"; exit 1; }

python3 - <<'PY' "$PARITY"
import json, sys
path = sys.argv[1]
report = json.load(open(path, encoding="utf-8"))
overall = report.get("overall")
proy = report.get("datasets", {}).get("proyectos", {})
rows = proy.get("rows", 0)
print(f"parity overall={overall} proyectos={rows}")
if overall == "none" or rows < 1:
    sys.exit(1)
PY

python3 db/sync_municipio_to_supabase.py --municipio "$SLUG" --dry-run

echo "OK: $SLUG válido para PR"
