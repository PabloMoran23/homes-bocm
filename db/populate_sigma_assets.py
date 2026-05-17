#!/usr/bin/env python3
"""
Orquestador: ingest visor SQLite + descarga NTI opcional (+ fetch visor opcional vía subprocess).

Desde poc-bocm/::

  # 1) (opcional) refrescar todo el JSON visor (~ muchas peticiones)
  python3 db/populate_sigma_assets.py --run-visor-fetch

  # 2) Volcar JSON → DB y bajar ficheros pendientes
  python3 db/populate_sigma_assets.py --ingest --download

  # Prueba corta:
  python3 db/populate_sigma_assets.py --ingest --download --download-limit 20
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent


def main() -> None:
    ap = argparse.ArgumentParser(description="Populate Sigma visor / NTI en SQLite local.")
    ap.add_argument(
        "--run-visor-fetch",
        action="store_true",
        help="Ejecuta python3 -m sector_geometry.madrid_viso_fetch (tarda; muchas URLs).",
    )
    ap.add_argument("--ingest", action="store_true", help="Ejecutar db/ingest_visor_sqlite.py")
    ap.add_argument(
        "--ingest-use-preserve-nti",
        action="store_true",
        help="Pasa --preserve-nti-local a la ingest.",
    )
    ap.add_argument("--download", action="store_true", help="Ejecutar db/download_nti_sqlite.py")
    ap.add_argument("--download-limit", type=int, default=0)
    ap.add_argument("--download-delay", type=float, default=0.35)
    ap.add_argument("--db", type=Path, default=DB_DIR / "poc_local.sqlite")
    ap.add_argument("--visor-json", type=Path, default=POC_ROOT / "output/madrid_viso_expedientes.json")
    args = ap.parse_args()

    if not any([args.run_visor_fetch, args.ingest, args.download]):
        ap.print_help()
        raise SystemExit(1)

    if args.run_visor_fetch:
        cmd = [
            sys.executable,
            "-m",
            "sector_geometry.madrid_viso_fetch",
        ]
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=str(POC_ROOT), check=True)

    if args.ingest:
        cmd = [sys.executable, str(DB_DIR / "ingest_visor_sqlite.py"), "--db", str(args.db)]
        cmd += ["--visor-json", str(args.visor_json)]
        if args.ingest_use_preserve_nti:
            cmd.append("--preserve-nti-local")
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=str(POC_ROOT), check=True)

    if args.download:
        cmd = [
            sys.executable,
            str(DB_DIR / "download_nti_sqlite.py"),
            "--db",
            str(args.db),
            "--delay",
            str(args.download_delay),
        ]
        if args.download_limit > 0:
            cmd += ["--limit-rows", str(args.download_limit)]
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, cwd=str(POC_ROOT), check=True)


if __name__ == "__main__":
    main()
