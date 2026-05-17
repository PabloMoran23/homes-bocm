#!/usr/bin/env python3
"""
Runner continuo: procesa PDFs NTI locales conforme se descargan.

- Selección por rol (--pipeline)
- Guarda en SQLite tras cada PDF (commit tras cada llamada LLM)
- Re-agrega expediente tras cada PDF procesado
- Bucle: re-escanea disco cada poll_seconds

Uso:
  python3 -m sector_geometry.madrid_nti_pdf_pipeline_runner --since-year 2020 --llm
  python3 -m sector_geometry.madrid_nti_pdf_pipeline_runner --once --limit 20
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from sector_geometry.madrid_nti_metrics_db import (
    DEFAULT_DB,
    connect,
    count_metrics,
    fetch_pdf_rows_for_expediente,
    get_state,
    load_done_pdf_paths,
    set_state,
    upsert_expediente_metric,
    upsert_pdf_metric,
)
from sector_geometry.madrid_nti_pdf_extract import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    OUTPUT_DIR,
    POC_ROOT,
    VISOR_JSON,
    _load_index_by_grupo,
    iter_local_pdfs,
    process_pdf_job,
    test_llm_connection,
)
from sector_geometry.madrid_nti_pdf_metrics import merge_expediente_metrics
from sector_geometry.madrid_nti_pdf_select import select_pipeline_jobs

PDF_METRICS_JSONL = OUTPUT_DIR / "madrid_sigma_pdf_metrics.jsonl"
LOG_PATH = OUTPUT_DIR / "sigma_pdf_extract_pipeline.log"


def _log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).isoformat()} {msg}"
    print(line, flush=True)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _append_jsonl(row: dict[str, Any]) -> None:
    with PDF_METRICS_JSONL.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _reload_jobs(
    visor: dict[str, Any],
    *,
    since_year: int | None,
    max_pdfs_per_exp: int,
) -> list[dict[str, Any]]:
    raw = iter_local_pdfs(visor, since_year=since_year, only_types=None)
    return select_pipeline_jobs(raw, max_pdfs_per_exp=max_pdfs_per_exp)


def _process_one(
    job: dict[str, Any],
    *,
    con,
    client: OpenAI | None,
    use_llm: bool,
    llm_always: bool,
    max_pages: int,
    llm_model: str,
    index_by_g: dict[str, dict[str, Any]],
    visor: dict[str, Any],
) -> bool:
    rel = str(job["local_path"].relative_to(POC_ROOT))
    row = process_pdf_job(
        job,
        client=client,
        use_llm=use_llm,
        llm_if_regex_empty=not llm_always,
        max_pages=max_pages,
    )
    row["pdf_path"] = rel

    upsert_pdf_metric(con, row, llm_model=llm_model)
    con.commit()

    _append_jsonl(row)

    grupo = job["grupo"]
    rows = fetch_pdf_rows_for_expediente(con, grupo)
    idx = index_by_g.get(grupo) or {}
    rec = (visor.get("byGrupoExpediente") or {}).get(grupo) or {}
    tipo_inst = ""
    for r in rows:
        if r.get("tipo_instrumento"):
            tipo_inst = str(r["tipo_instrumento"])
            break
    agg = merge_expediente_metrics(
        rows,
        prefer_llm=use_llm,
        denominacion=str(idx.get("EXP_TX_DENOM") or ""),
        tipo_instrumento=tipo_inst,
    )
    upsert_expediente_metric(
        con,
        grupo,
        denominacion=str(idx.get("EXP_TX_DENOM") or ""),
        fase_sigma=str(idx.get("FAS_TX_DENOM") or ""),
        agg=agg,
    )
    con.commit()

    set_state(con, "last_pdf_path", rel)
    set_state(con, "last_expediente_grupo", grupo)
    counts = count_metrics(con)
    set_state(con, "stats_json", json.dumps(counts))
    con.commit()

    m = agg.get("metrics") or {}
    _log(
        f"OK {grupo} | {row.get('doc_role')} | {row.get('method')} "
        f"| viv={m.get('num_viviendas_max')} sup={m.get('sup_total_m2')} "
        f"| db_pdfs={counts['pdf_metrics']} exps={counts['expediente_metrics']}"
    )
    return True


def run_loop(
    *,
    db_path: Path,
    since_year: int | None,
    use_llm: bool,
    llm_always: bool,
    max_pages: int,
    max_pdfs_per_exp: int,
    poll_seconds: float,
    delay: float,
    once: bool,
    limit: int,
    force: bool,
) -> None:
    if not VISOR_JSON.is_file():
        raise SystemExit(f"No existe {VISOR_JSON}")

    con = connect(db_path)
    llm_model = LLM_MODEL
    base_url = LLM_BASE_URL

    client: OpenAI | None = None
    if use_llm:
        client = OpenAI(api_key=LLM_API_KEY, base_url=base_url)
        try:
            test_llm_connection(base_url, LLM_API_KEY, llm_model)
        except Exception as exc:
            _log(f"LLM no disponible ({exc}); modo regex")
            client = None
            use_llm = False

    set_state(con, "runner_status", "running")
    set_state(con, "runner_started_at", datetime.now(timezone.utc).isoformat())
    set_state(con, "llm_base_url", base_url)
    set_state(con, "llm_model", llm_model)
    con.commit()

    processed_session = 0
    visor_mtime = 0.0
    visor: dict[str, Any] = {}
    index_by_g: dict[str, dict[str, Any]] = {}

    while True:
        mtime = VISOR_JSON.stat().st_mtime
        if mtime != visor_mtime:
            visor = json.loads(VISOR_JSON.read_text(encoding="utf-8"))
            index_by_g = _load_index_by_grupo()
            visor_mtime = mtime

        jobs = _reload_jobs(visor, since_year=since_year, max_pdfs_per_exp=max_pdfs_per_exp)
        done = set() if force else load_done_pdf_paths(con)
        pending = [j for j in jobs if str(j["local_path"].relative_to(POC_ROOT)) not in done]

        if limit > 0:
            pending = pending[: max(0, limit - processed_session)]

        set_state(con, "pending_pdfs", str(len(pending)))
        set_state(con, "total_pipeline_jobs", str(len(jobs)))
        con.commit()

        if not pending:
            _log(f"idle: 0 pendientes de {len(jobs)} jobs pipeline (poll {poll_seconds}s)")
            if once:
                break
            time.sleep(poll_seconds)
            continue

        _log(f"cola: {len(pending)} PDFs pendientes / {len(jobs)} seleccionados")

        for i, job in enumerate(pending):
            if delay > 0 and i > 0:
                time.sleep(delay)
            try:
                _process_one(
                    job,
                    con=con,
                    client=client,
                    use_llm=use_llm,
                    llm_always=llm_always,
                    max_pages=max_pages,
                    llm_model=llm_model,
                    index_by_g=index_by_g,
                    visor=visor,
                )
                processed_session += 1
            except Exception as exc:
                _log(f"ERROR {job['grupo']} {job['local_path'].name}: {exc}")
                set_state(con, "last_error", str(exc)[:500])
                con.commit()
                if once:
                    raise

            if limit > 0 and processed_session >= limit:
                break

        if once or (limit > 0 and processed_session >= limit):
            break
        time.sleep(poll_seconds)

    set_state(con, "runner_status", "stopped")
    set_state(con, "runner_stopped_at", datetime.now(timezone.utc).isoformat())
    con.commit()
    counts = count_metrics(con)
    _log(f"fin sesión: procesados={processed_session} stats={counts}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Runner continuo extracción métricas NTI → SQLite.")
    ap.add_argument("--db", type=Path, default=DEFAULT_DB)
    ap.add_argument("--since-year", type=int, default=2020)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--regex-only", action="store_true")
    ap.add_argument("--llm-always", action="store_true")
    ap.add_argument("--max-pages", type=int, default=25)
    ap.add_argument("--max-pdfs-per-exp", type=int, default=8)
    ap.add_argument("--poll-seconds", type=float, default=45.0)
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--once", action="store_true", help="Una pasada y salir.")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true", help="Reprocesar aunque esté en DB.")
    args = ap.parse_args()

    since = args.since_year if args.since_year > 0 else None
    run_loop(
        db_path=args.db,
        since_year=since,
        use_llm=args.llm and not args.regex_only,
        llm_always=args.llm_always,
        max_pages=args.max_pages,
        max_pdfs_per_exp=args.max_pdfs_per_exp,
        poll_seconds=args.poll_seconds,
        delay=args.delay,
        once=args.once,
        limit=args.limit,
        force=args.force,
    )


if __name__ == "__main__":
    main()
