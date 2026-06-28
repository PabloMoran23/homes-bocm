#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.

SLUGS=(
  san-sebastian-de-los-reyes leganes navalcarnero majadahonda collado-villalba
  torrelodones san-agustin-del-guadalix galapagar villanueva-del-pardillo arganda-del-rey
  grinon valdemoro cubas-de-la-sagra fuente-el-saz-de-jarama parla paracuellos-de-jarama
  coslada algete hoyo-de-manzanares humanes-de-madrid san-martin-de-la-vega
)

LOG="output/municipios/batch-run-new-municipios.log"
mkdir -p output/municipios
echo "Batch run all — $(date -Iseconds)" | tee "$LOG"

for slug in "${SLUGS[@]}"; do
  echo "[$slug] pipeline all..." | tee -a "$LOG"
  if python3 -m municipio run -m "$slug" --step all >>"$LOG" 2>&1; then
    echo "[$slug] OK" | tee -a "$LOG"
  else
    echo "[$slug] FAILED (see log)" | tee -a "$LOG"
  fi
done

echo "DONE — $(date -Iseconds)" | tee -a "$LOG"
