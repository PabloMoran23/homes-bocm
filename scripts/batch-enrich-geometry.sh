#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.

SLUGS=(
  pozuelo-de-alarcon torrejon-de-ardoz mostoles alcala-de-henares alcobendas getafe
  fuenlabrada las-rozas-de-madrid rivas-vaciamadrid boadilla-del-monte villaviciosa-de-odon
  meco san-fernando-de-henares alcorcon pinto villalbilla tres-cantos aranjuez colmenar-viejo
  villanueva-de-la-canada brunete el-boalo ciempozuelos
)

LOG="output/municipios/batch-enrich-geometry.log"
mkdir -p output/municipios
echo "Batch enrich_geometry + geocode — $(date -Iseconds)" | tee "$LOG"

total_geom=0
for slug in "${SLUGS[@]}"; do
  echo "[$slug] enrich_geometry..." | tee -a "$LOG"
  out=$(python3 -m municipio run -m "$slug" --step enrich_geometry 2>&1) || true
  enriched=$(echo "$out" | python3 -c "
import sys,json
try:
 d=json.load(sys.stdin)
 s=d['steps']['enrich_geometry']
 print(s.get('proyectos',{}).get('enriched',0))
except Exception:
 print(0)
" 2>/dev/null || echo 0)
  echo "[$slug] enriched=$enriched" | tee -a "$LOG"
  total_geom=$((total_geom + enriched))

  echo "[$slug] geocode..." | tee -a "$LOG"
  python3 -m municipio run -m "$slug" --step geocode >>"$LOG" 2>&1 || true
done

echo "DONE total_enriched=$total_geom — $(date -Iseconds)" | tee -a "$LOG"
