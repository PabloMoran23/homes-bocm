"""
Procesa PDFs del histórico (history_index.jsonl) con LLM, orden cronológico
inverso (más reciente primero: 2026 → atrás).

Cada fila se escribe al CSV inmediatamente (flush + fsync) para no perder
progreso si se corta el proceso.

Variables de entorno:
  LLM_BASE_URL   (default http://192.168.1.15:11434/v1)
  LLM_API_KEY    (default local)
  LLM_MODEL      (default gemma4-small-8k:latest)
  HISTORY_INDEX  (default output/history_index.jsonl)
  HISTORY_CSV    (default output/history_parsed_incremental.csv)
  BOLETIN_SOURCE_ID, BOLETIN_NAME, BOLETIN_REGION_HINT  (ver boletin_llm_parse.BoletinContext)
  SKIP_CCAA_SPOTCHECK=1  (omitir spot-check de 5 PDFs CCAA al final)
  CCAA_SPOTCHECK_SEED=n   (semilla aleatoria reproducible)
  LLM_MAX_CONTEXT_CHARS   (default 4000; si el PDF supera este trozo, requiere_segunda_pasada=True)
  PARSE_HISTORY_MIN_DATE  (default 2020-01-01; no procesa boletines anteriores. Para histórico viejo:
                           p.ej. PARSE_HISTORY_MIN_DATE=2010-01-01)
  SKIP_CCAA_HISTORY=1     (no ejecutar tras el BOCM el parseo masivo de ccaa-boletines →
                           output/ccaa_history_parsed_incremental.csv; ver parse_ccaa_history_nightly.py)

Uso:
  LLM_MODEL=gemma4-small-8k:latest python3 -u parse_history_nightly.py
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from pathlib import Path

from openai import OpenAI

from boletin_llm_parse import (
    BoletinContext,
    DEFAULT_CONTEXT,
    context_meta_for_fulltext,
    merge_context_into_flat,
)
from ccaa_spotcheck import maybe_run_ccaa_spotcheck_after_job
from project_fingerprint import backfill_csv, compute_proyecto_fingerprint

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"

HISTORY_INDEX = Path(os.getenv("HISTORY_INDEX", str(OUTPUT_DIR / "history_index.jsonl")))
HISTORY_CSV = Path(os.getenv("HISTORY_CSV", str(OUTPUT_DIR / "history_parsed_incremental.csv")))

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.1.15:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "local")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma4-small-8k:latest")
LLM_MAX_CONTEXT_CHARS = int(os.getenv("LLM_MAX_CONTEXT_CHARS", "4000"))

# Boletines con fecha estrictamente anterior a este día no entran en la cola nocturna.
_PARSE_HISTORY_MIN_DATE_RAW = os.getenv("PARSE_HISTORY_MIN_DATE", "2020-01-01")
_BOCM_NAME_DATE = re.compile(r"BOCM-(\d{4})(\d{2})(\d{2})-", re.IGNORECASE)

# Cargar 3_llm_parse.py (nombre no importable como módulo)
_SPEC = importlib.util.spec_from_file_location("bocm_llm_parse", BASE_DIR / "3_llm_parse.py")
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("No se pudo cargar 3_llm_parse.py")
llm_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(llm_mod)


def _parse_min_bocm_date() -> date:
    try:
        return date.fromisoformat(_PARSE_HISTORY_MIN_DATE_RAW.strip()[:10])
    except ValueError as ex:
        raise SystemExit(
            f"PARSE_HISTORY_MIN_DATE inválido: {_PARSE_HISTORY_MIN_DATE_RAW!r} (esperado YYYY-MM-DD)"
        ) from ex


def _entry_bocm_date(e: dict) -> date | None:
    """Fecha del boletín desde campo `date` o, en su defecto, del nombre BOCM-YYYYMMDD-."""
    ds = (e.get("date") or "").strip()[:10]
    if ds:
        try:
            return date.fromisoformat(ds)
        except ValueError:
            pass
    rel = e.get("pdf_path") or ""
    m = _BOCM_NAME_DATE.search(Path(rel).name)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def load_index() -> list[dict]:
    if not HISTORY_INDEX.exists():
        raise FileNotFoundError(f"No existe {HISTORY_INDEX}")
    rows = []
    with HISTORY_INDEX.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def pdf_to_text(pdf_path: Path) -> str:
    r = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout or ""


def migrate_history_csv_columns(csv_path: Path, fieldnames: list[str]) -> None:
    """Si faltan columnas nuevas del parser, reescribe el CSV con cabecera completa."""
    if not csv_path.is_file() or csv_path.stat().st_size == 0:
        return
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        old_fn = reader.fieldnames or []
        rows = list(reader)
    if not old_fn:
        return
    missing = [fn for fn in fieldnames if fn not in old_fn]
    if not missing:
        return
    show = missing[:6]
    more = "…" if len(missing) > 6 else ""
    print(f"Migrando CSV: añadiendo columnas {show}{more} ({len(missing)} en total)", flush=True)
    for row in rows:
        for fn in missing:
            row.setdefault(fn, "")
    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(csv_path)
    print(f"  OK: {len(rows)} filas reescritas\n", flush=True)


def load_processed_keys(csv_path: Path) -> set[tuple[str, str]]:
    """Claves (bocm_date, art_num) ya escritas."""
    if not csv_path.exists():
        return set()
    done: set[tuple[str, str]] = set()
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("bocm_date") or ""
            a = row.get("art_num") or ""
            if d and a:
                done.add((d, a))
    return done


def _boletin_ctx() -> BoletinContext:
    return BoletinContext(
        source_id=os.getenv("BOLETIN_SOURCE_ID", "bocm"),
        bulletin_name=os.getenv("BOLETIN_NAME", DEFAULT_CONTEXT.bulletin_name),
        region_hint=os.getenv("BOLETIN_REGION_HINT", DEFAULT_CONTEXT.region_hint),
    )


def main() -> None:
    # Alinear env del submódulo (ya cargado; reasignar por si acaso)
    llm_mod.LLM_BASE_URL = LLM_BASE_URL
    llm_mod.LLM_API_KEY = LLM_API_KEY
    llm_mod.LLM_MODEL = LLM_MODEL

    boletin_ctx = _boletin_ctx()
    min_bocm_date = _parse_min_bocm_date()

    print("=== parse_history_nightly ===", flush=True)
    print(f"  index : {HISTORY_INDEX}", flush=True)
    print(f"  csv   : {HISTORY_CSV}", flush=True)
    print(f"  model : {LLM_MODEL}", flush=True)
    print(f"  url   : {LLM_BASE_URL}", flush=True)
    print(f"  fuente: {boletin_ctx.source_id}", flush=True)
    print(f"  fecha mín. boletín: {min_bocm_date.isoformat()} (PARSE_HISTORY_MIN_DATE)\n", flush=True)

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    entries = load_index()
    # Solo PDFs que existen
    valid = []
    for e in entries:
        rel = e.get("pdf_path")
        if not rel:
            continue
        p = BASE_DIR / rel
        if p.is_file() and p.stat().st_size > 500:
            e = dict(e)
            e["_abs_pdf"] = p
            valid.append(e)

    # Más reciente primero: fecha ISO descendente, luego artículo descendente
    def sort_key(e: dict):
        d = e.get("date", "")
        try:
            an = int(e.get("art_num", "0"))
        except ValueError:
            an = 0
        return (d, an)

    valid.sort(key=sort_key, reverse=True)

    # El índice puede tener líneas duplicadas (re-ejecuciones del fetcher).
    # Una sola fila CSV por (fecha, artículo).
    _seen: set[tuple[str, str]] = set()
    _deduped: list[dict] = []
    for e in valid:
        k = (e.get("date", ""), str(e.get("art_num", "")))
        if k in _seen:
            continue
        _seen.add(k)
        _deduped.append(e)
    valid = _deduped

    skipped_before_min = 0
    date_filtered: list[dict] = []
    for e in valid:
        ed = _entry_bocm_date(e)
        if ed is not None and ed < min_bocm_date:
            skipped_before_min += 1
            continue
        date_filtered.append(e)
    valid = date_filtered
    if skipped_before_min:
        print(
            f"Filtro fecha: omitidos {skipped_before_min} con boletín anterior a {min_bocm_date.isoformat()}",
            flush=True,
        )

    if HISTORY_CSV.exists() and HISTORY_CSV.stat().st_size > 0:
        with HISTORY_CSV.open(encoding="utf-8") as f:
            header_line = f.readline()
        if "proyecto_fingerprint" not in header_line:
            print("Migrando CSV: añadiendo columna proyecto_fingerprint…", flush=True)
            n_mig, _ = backfill_csv(HISTORY_CSV)
            print(f"  migradas {n_mig} filas existentes\n", flush=True)

    meta_cols = [
        "bocm_date",
        "art_num",
        "title",
        "pdf_path",
        "pdf_url",
        "txt_chars",
        "latency_s",
        "error",
    ]
    fieldnames = meta_cols + list(llm_mod.FIELDS) + ["proyecto_fingerprint"]
    migrate_history_csv_columns(HISTORY_CSV, fieldnames)

    processed = load_processed_keys(HISTORY_CSV)
    print(f"Entradas índice: {len(entries)} | PDFs válidos: {len(valid)} | ya en CSV: {len(processed)}\n", flush=True)

    new_file = not HISTORY_CSV.exists() or HISTORY_CSV.stat().st_size == 0

    with HISTORY_CSV.open("a", newline="", encoding="utf-8", buffering=1) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            writer.writeheader()
            f.flush()
            os.fsync(f.fileno())

        n = 0
        for e in valid:
            d_str = e.get("date", "")
            a_str = str(e.get("art_num", ""))
            if (d_str, a_str) in processed:
                continue

            pdf_path: Path = e["_abs_pdf"]
            pdf_name = pdf_path.name
            n += 1
            t0 = time.time()
            err = ""
            print(f"[{n}] {d_str} #{a_str} {pdf_name}", flush=True)

            try:
                text = pdf_to_text(pdf_path)
            except Exception as ex:
                err = f"pdftotext:{ex}"
                text = ""

            txt_chars = len(text)
            parsed: dict = {}
            row: dict = {
                "bocm_date": d_str,
                "art_num": a_str,
                "title": (e.get("title") or "")[:500],
                "pdf_path": e.get("pdf_path", ""),
                "pdf_url": e.get("pdf_url", ""),
                "txt_chars": txt_chars,
                "latency_s": "",
                "error": err,
            }

            if txt_chars < 80:
                row["error"] = (row["error"] + ";texto_corto").strip(";")
                for fld in llm_mod.FIELDS:
                    row[fld] = None
            else:
                try:
                    parsed = llm_mod.parse_with_llm(
                        client,
                        text,
                        pdf_name,
                        ctx=boletin_ctx,
                        model=LLM_MODEL,
                        max_context_chars=LLM_MAX_CONTEXT_CHARS,
                    )
                except Exception as ex:
                    err = f"llm:{ex}"
                    parsed = {"es_relevante": None}
                    row["error"] = err

                for fld in llm_mod.FIELDS:
                    row[fld] = parsed.get(fld)

            if txt_chars > 0:
                merge_context_into_flat(
                    row,
                    context_meta_for_fulltext(text, max_context_chars=LLM_MAX_CONTEXT_CHARS),
                )

            row["latency_s"] = round(time.time() - t0, 2)
            row["proyecto_fingerprint"] = compute_proyecto_fingerprint(row)

            writer.writerow(row)
            f.flush()
            os.fsync(f.fileno())

            rel_flag = parsed.get("es_relevante") if txt_chars >= 80 else None
            seg2 = row.get("requiere_segunda_pasada")
            seg_mark = " | 2ªpasada" if seg2 else ""
            print(
                f"  → {row['latency_s']}s | relevante={rel_flag} | {row.get('municipio')} | {row.get('tipo_instrumento')}{seg_mark}",
                flush=True,
            )

            time.sleep(0.15)

    print(f"\n=== Hecho. CSV: {HISTORY_CSV} ===", flush=True)

    if os.getenv("SKIP_CCAA_HISTORY", "").strip().lower() not in ("1", "true", "yes"):
        import parse_ccaa_history_nightly as ccaa_hist  # noqa: E402

        ccaa_hist.run_ccaa_history_batch(
            client=client,
            min_bocm_date=_parse_min_bocm_date(),
            llm_model=LLM_MODEL,
            max_context_chars=LLM_MAX_CONTEXT_CHARS,
        )

    maybe_run_ccaa_spotcheck_after_job(client=client, model=LLM_MODEL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[interrumpido] última fila ya debería estar guardada.", flush=True)
        sys.exit(130)
