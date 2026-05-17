#!/usr/bin/env bash
# Pipeline largo: visor SIGMA (índice completo) → ingest SQLite → descarga NTI.
# Uso: bash db/run_full_pipeline_bg.sh
# Log: output/poc_sigma_full_pipeline.log

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LOG="${ROOT}/output/poc_sigma_full_pipeline.log"
mkdir -p "${ROOT}/output"

{
  echo "=== $(date -Iseconds) START pipeline pid=$$ host=$(hostname) ==="
  echo "--- df -h / ---"
  df -h / || true
  echo "--- visor fetch (todos los expedientes del índice + NTI) ---"
  python3 -m sector_geometry.madrid_viso_fetch --all-index --limit 0 --delay 0.35
  echo "--- ingest SQLite (--preserve-nti-local) ---"
  python3 db/ingest_visor_sqlite.py --preserve-nti-local
  echo "--- download NTI pendientes ---"
  if ! python3 db/download_nti_sqlite.py --delay 0.35; then
    echo "--- AVISO: descarga NTI salió con error (reintenta: python3 db/download_nti_sqlite.py --delay 0.35) ---"
  fi
  echo "=== PIPELINE DONE === $(date -Iseconds) ==="
} >>"$LOG" 2>&1
