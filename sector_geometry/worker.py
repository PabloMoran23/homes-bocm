from __future__ import annotations

import argparse
import os
import time
import traceback
from pathlib import Path

from .db import connect, fetch_next_pending, mark_result
from .enqueue import default_csv_paths, enqueue_csv
from .export_map_geojson import maybe_export_map
from .resolvers_builtin import SectorContext, load_resolvers_from_json, try_resolve_chain


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _db_path() -> Path:
    raw = os.getenv("SECTOR_GEOMETRY_DB")
    if raw:
        return Path(raw)
    return _repo_root() / "output" / "sector_geometry.sqlite3"


def _resolvers_path() -> Path | None:
    raw = os.getenv("SECTOR_RESOLVERS_JSON")
    if raw:
        p = Path(raw)
        return p if p.is_file() else None
    p = _repo_root() / "sector_geometry" / "resolvers.json"
    return p if p.is_file() else None


def sync_csvs_once(db: Path) -> None:
    total_ins = 0
    for csv_p in default_csv_paths():
        if not csv_p.is_file():
            continue
        scanned, ins = enqueue_csv(csv_p, db_path=db)
        print(f"[enqueue] {csv_p.name}: escaneadas={scanned} nuevas={ins}", flush=True)
        total_ins += ins
    print(f"[enqueue] total nuevas claves: {total_ins}", flush=True)


def process_one(con, resolvers) -> bool:
    row = fetch_next_pending(con)
    if row is None:
        return False
    sk = row["stable_key"]
    ctx = SectorContext(
        municipio_raw=row["municipio_raw"] or "",
        sector_raw=row["sector_raw"] or "",
        municipio_norm=row["municipio_norm"] or "",
        sector_norm=row["sector_norm"] or "",
        municipio_provincia_raw=row["municipio_provincia_raw"],
        boletin_source_id=row["boletin_source_id"],
        stable_key=sk,
    )
    if not resolvers:
        mark_result(
            con,
            sk,
            status="failed",
            last_error="no_resolvers_configured",
            match_detail={"hint": "Crea sector_geometry/resolvers.json o exporta SECTOR_RESOLVERS_JSON"},
        )
        return True
    try:
        hit, chain_err = try_resolve_chain(resolvers, ctx)
    except Exception as ex:
        mark_result(
            con,
            sk,
            status="failed",
            last_error=f"resolver_exception: {ex!r}",
            match_detail={"traceback": traceback.format_exc()[-4000:]},
        )
        return True
    if hit:
        mark_result(
            con,
            sk,
            status="matched",
            geometry_geojson=hit.geometry_geojson,
            centroid_lon=hit.centroid_lon,
            centroid_lat=hit.centroid_lat,
            resolver_id=hit.resolver_id,
            match_detail=hit.detail,
            last_error=None,
        )
    else:
        err = chain_err or "no_unique_geometry_match"
        mark_result(
            con,
            sk,
            status="failed",
            last_error=err,
            match_detail={"municipio": ctx.municipio_raw, "sector": ctx.sector_raw},
        )
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cola + worker: sectores → geometría (SQLite).")
    ap.add_argument("--db", type=Path, default=None, help="Ruta SQLite (default output/sector_geometry.sqlite3)")
    ap.add_argument("--sync-csv", action="store_true", help="Encolar desde CSVs y salir")
    ap.add_argument("--once", action="store_true", help="Un ciclo: sync + procesar hasta vaciar o 1 job")
    ap.add_argument("--daemon", action="store_true", help="Bucle: sync + procesar con pausa")
    ap.add_argument("--interval", type=float, default=120.0, help="Segundos entre ciclos en --daemon")
    ap.add_argument("--max-jobs", type=int, default=0, help="Máx. trabajos por ciclo (0 = sin límite)")
    ap.add_argument(
        "--reset-no-config-failed",
        action="store_true",
        help="Pasa a pending los failed con last_error=no_resolvers_configured (tras crear resolvers.json)",
    )
    args = ap.parse_args(argv)

    if not (args.sync_csv or args.once or args.daemon or args.reset_no_config_failed):
        ap.print_help()
        return 1

    db = args.db or _db_path()
    if args.reset_no_config_failed:
        con0 = connect(db)
        try:
            cur = con0.execute(
                """
                UPDATE sector_spatial
                SET status = 'pending', last_error = NULL, updated_at = ?
                WHERE status = 'failed' AND last_error = 'no_resolvers_configured'
                """,
                (time.time(),),
            )
            con0.commit()
            print(f"[reset] filas reencoladas: {cur.rowcount}", flush=True)
        finally:
            con0.close()
    res_path = _resolvers_path()
    resolvers = load_resolvers_from_json(res_path) if res_path else []

    if args.sync_csv or args.once or args.daemon:
        sync_csvs_once(db)

    if args.sync_csv and not args.once and not args.daemon:
        return 0

    if not args.once and not args.daemon:
        return 0

    con = connect(db)
    try:
        if args.once:
            n = 0
            while process_one(con, resolvers):
                n += 1
                if args.max_jobs and n >= args.max_jobs:
                    break
            print(f"[once] procesados: {n}", flush=True)
            maybe_export_map(db)
            return 0
        if args.daemon:
            while True:
                if res_path:
                    resolvers = load_resolvers_from_json(res_path)
                processed = 0
                while process_one(con, resolvers):
                    processed += 1
                    if args.max_jobs and processed >= args.max_jobs:
                        break
                print(
                    f"[daemon] ciclo fin: procesados={processed} próxima espera={args.interval}s",
                    flush=True,
                )
                maybe_export_map(db)
                time.sleep(args.interval)
                sync_csvs_once(db)
            return 0
    finally:
        con.close()

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
