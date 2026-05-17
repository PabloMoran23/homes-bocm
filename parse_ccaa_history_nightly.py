"""
Parseo incremental con LLM de los índices history_index*.jsonl de ccaa-boletines
(todas las fuentes bajo pdfs_history/<carpeta>/…), con fecha de publicación >= corte.

Salida: output/ccaa_history_parsed_incremental.csv (columna boletin_source_id para
distinguir fuente; el resto alinea con history_parsed_incremental del BOCM).

Variables de entorno (además de LLM_*):
  PARSE_HISTORY_MIN_DATE     (default 2020-01-01, misma que BOCM)
  CCAA_BOLETINES_ROOT        (default <repo>/ccaa-boletines)
  CCAA_HISTORY_INDEX_DIR     (default $CCAA_BOLETINES_ROOT/output)
  CCAA_HISTORY_CSV           (default poc-bocm/output/ccaa_history_parsed_incremental.csv)

Uso aislado:
  python3 -u parse_ccaa_history_nightly.py
"""

from __future__ import annotations

import csv
import importlib.util
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

from openai import OpenAI

from boletin_llm_parse import context_meta_for_fulltext, merge_context_into_flat
from ccaa_spotcheck import context_for_folder, pdf_to_text
from project_fingerprint import backfill_csv, compute_proyecto_fingerprint

POC_DIR = Path(__file__).resolve().parent
DEFAULT_CCAA_ROOT = POC_DIR.parent / "ccaa-boletines"
DEFAULT_DOGC_ROOT = POC_DIR.parent / "poc-dogc"
CCAA_BOLETINES_ROOT = Path(os.getenv("CCAA_BOLETINES_ROOT", str(DEFAULT_CCAA_ROOT)))
DOGC_BOLETINES_ROOT = Path(os.getenv("DOGC_BOLETINES_ROOT", str(DEFAULT_DOGC_ROOT)))
CCAA_HISTORY_INDEX_DIR = Path(
    os.getenv("CCAA_HISTORY_INDEX_DIR", str(CCAA_BOLETINES_ROOT / "output"))
)
DOGC_HISTORY_INDEX_DIR = Path(
    os.getenv("DOGC_HISTORY_INDEX_DIR", str(DOGC_BOLETINES_ROOT / "output"))
)
PARSE_ONLY_BOLETIN = (os.getenv("PARSE_ONLY_BOLETIN") or "").strip().lower()
CCAA_HISTORY_CSV = Path(
    os.getenv(
        "CCAA_HISTORY_CSV",
        str(POC_DIR / "output" / "ccaa_history_parsed_incremental.csv"),
    )
)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.1.15:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "local")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma4-small-8k:latest")
LLM_MAX_CONTEXT_CHARS = int(os.getenv("LLM_MAX_CONTEXT_CHARS", "4000"))

_SPEC = importlib.util.spec_from_file_location("bocm_llm_parse", POC_DIR / "3_llm_parse.py")
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("No se pudo cargar 3_llm_parse.py")
llm_mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(llm_mod)


def _parse_min_date(raw: str) -> date:
    try:
        return date.fromisoformat(raw.strip()[:10])
    except ValueError as ex:
        raise SystemExit(f"PARSE_HISTORY_MIN_DATE inválido: {raw!r}") from ex


def _parse_dmy(s: str) -> date | None:
    s = (s or "").strip()[:10]
    if not s or "/" not in s:
        return None
    parts = s.split("/")
    if len(parts) != 3:
        return None
    try:
        d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
        return date(y, m, d)
    except ValueError:
        return None


def _normalize_ccaa_pub_date(e: dict) -> date | None:
    for key in ("date_pub", "fecha"):
        v = e.get(key)
        if not isinstance(v, str) or not v.strip():
            continue
        s = v.strip()[:10]
        if "/" in s:
            d = _parse_dmy(s)
            if d:
                return d
        else:
            try:
                return date.fromisoformat(s)
            except ValueError:
                pass
    fp = e.get("fecha_publicacion")
    if isinstance(fp, str) and fp.strip():
        d = _parse_dmy(fp.strip())
        if d:
            return d
    v = e.get("date")
    if isinstance(v, str) and v.strip():
        s = v.strip()[:10]
        if "/" in s:
            d = _parse_dmy(s)
            if d:
                return d
        else:
            try:
                return date.fromisoformat(s)
            except ValueError:
                pass
    return None


def _folder_id_from_pdf_path(rel: str) -> str | None:
    parts = rel.strip("/").replace("\\", "/").split("/")
    if len(parts) > 2 and parts[0] == "pdfs_history":
        return parts[1]
    return None


def _is_dogc_pdf(rel: str, pdf_stem: str) -> bool:
    r = rel.replace("\\", "/")
    if r.startswith("pdfs_history/dogc/"):
        return True
    return pdf_stem.upper().startswith("DOGC-")


def _resolve_index_entry(rel: str, pdf_stem: str, index_origin: str) -> tuple[Path | None, str | None]:
    """Devuelve (ruta absoluta al PDF, folder_id / boletin_source_id)."""
    if index_origin == "dogc" or _is_dogc_pdf(rel, pdf_stem):
        abs_pdf = DOGC_BOLETINES_ROOT / rel
        if abs_pdf.is_file():
            return abs_pdf, "dogc"
        return None, None
    folder_id = _folder_id_from_pdf_path(rel)
    if not folder_id:
        return None, None
    abs_pdf = CCAA_BOLETINES_ROOT / rel
    if abs_pdf.is_file():
        return abs_pdf, folder_id
    return None, None


_YEAR_DIR = re.compile(r"/(19\d{2}|20\d{2})/")


def _fallback_date_from_path(rel: str) -> date | None:
    """Si falta fecha en JSON, usa el primer /AAAA/ de la ruta (carpeta año)."""
    m = _YEAR_DIR.search(rel.replace("\\", "/"))
    if not m:
        return None
    try:
        y = int(m.group(1))
        return date(y, 1, 1)
    except ValueError:
        return None


def _stable_art_num(e: dict, pdf_stem: str) -> str:
    for k in ("disposition_id", "codigo_insercion", "id_anuncio", "id_objeto"):
        v = e.get(k)
        if v is not None and str(v).strip():
            return str(v).strip()[:120]
    num_dogc = e.get("numDOGC")
    if num_dogc is not None and str(num_dogc).strip():
        tail = pdf_stem.split("-")[-1] if "-" in pdf_stem else pdf_stem
        return f"{str(num_dogc).strip()}-{tail}"[:120]
    return (pdf_stem or "unknown")[:120]


def _entry_title(e: dict) -> str:
    for k in ("title", "titulo", "summary"):
        v = e.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()[:500]
    return ""


def _migrate_csv_columns(csv_path: Path, fieldnames: list[str]) -> None:
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
    print(f"[CCAA] Migrando CSV: añadiendo columnas {missing[:8]}{'…' if len(missing) > 8 else ''}", flush=True)
    for row in rows:
        for fn in missing:
            row.setdefault(fn, "")
    tmp = csv_path.with_suffix(csv_path.suffix + ".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(csv_path)


def _load_ccaa_processed(csv_path: Path) -> set[tuple[str, str, str]]:
    out: set[tuple[str, str, str]] = set()
    if not csv_path.exists():
        return out
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row.get("boletin_source_id") or ""
            d = row.get("bocm_date") or ""
            a = row.get("art_num") or ""
            if sid and d and a:
                out.add((sid, d, a))
    return out


def _load_index_rows_from_dir(index_dir: Path, origin: str) -> list[dict]:
    rows: list[dict] = []
    if not index_dir.is_dir():
        return rows
    for p in sorted(index_dir.glob("history_index*.jsonl")):
        with p.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                e = json.loads(line)
                e["_index_src"] = p.name
                e["_index_origin"] = origin
                rows.append(e)
    return rows


def _load_all_ccaa_index_rows() -> list[dict]:
    rows = _load_index_rows_from_dir(CCAA_HISTORY_INDEX_DIR, "ccaa")
    rows.extend(_load_index_rows_from_dir(DOGC_HISTORY_INDEX_DIR, "dogc"))
    return rows


def run_ccaa_history_batch(
    *,
    client: OpenAI,
    min_bocm_date: date,
    llm_model: str | None = None,
    max_context_chars: int | None = None,
) -> None:
    llm_model = llm_model or LLM_MODEL
    max_context_chars = max_context_chars if max_context_chars is not None else LLM_MAX_CONTEXT_CHARS

    llm_mod.LLM_BASE_URL = LLM_BASE_URL
    llm_mod.LLM_API_KEY = LLM_API_KEY
    llm_mod.LLM_MODEL = llm_model

    if not CCAA_BOLETINES_ROOT.is_dir():
        print(
            f"[CCAA] Omitido: no existe CCAA_BOLETINES_ROOT={CCAA_BOLETINES_ROOT}",
            flush=True,
        )
        return

    print("\n=== parse_ccaa_history (índices multi-comunidad) ===", flush=True)
    print(f"  raíz CCAA : {CCAA_BOLETINES_ROOT}", flush=True)
    print(f"  raíz DOGC : {DOGC_BOLETINES_ROOT}", flush=True)
    print(f"  índices CCAA: {CCAA_HISTORY_INDEX_DIR}", flush=True)
    print(f"  índices DOGC: {DOGC_HISTORY_INDEX_DIR}", flush=True)
    if PARSE_ONLY_BOLETIN:
        print(f"  solo fuente: {PARSE_ONLY_BOLETIN}", flush=True)
    print(f"  csv       : {CCAA_HISTORY_CSV}", flush=True)
    print(f"  fecha mín.: {min_bocm_date.isoformat()}\n", flush=True)

    raw_rows = _load_all_ccaa_index_rows()
    valid: list[dict] = []
    skipped_date = 0
    skipped_path = 0
    skipped_nodate = 0
    seen_pdf: set[str] = set()

    for e in raw_rows:
        rel = (e.get("pdf_path") or "").strip().replace("\\", "/")
        if not rel:
            skipped_path += 1
            continue
        if rel in seen_pdf:
            continue
        origin = e.get("_index_origin") or "ccaa"
        stem_guess = Path(rel).stem
        abs_pdf, folder_id = _resolve_index_entry(rel, stem_guess, origin)
        if not abs_pdf or not folder_id:
            skipped_path += 1
            continue
        if PARSE_ONLY_BOLETIN and folder_id != PARSE_ONLY_BOLETIN:
            continue
        pub = _normalize_ccaa_pub_date(e)
        eff = pub or _fallback_date_from_path(rel)
        if eff is None:
            skipped_nodate += 1
            continue
        if eff < min_bocm_date:
            skipped_date += 1
            continue
        if abs_pdf.stat().st_size < 500:
            skipped_path += 1
            continue
        seen_pdf.add(rel)
        d_iso = pub.isoformat() if pub else eff.isoformat()
        stem = abs_pdf.stem
        art = _stable_art_num(e, stem)
        ne = dict(e)
        ne["_abs_pdf"] = abs_pdf
        ne["_folder_id"] = folder_id
        ne["_pub_iso"] = d_iso
        ne["_art_key"] = art
        ne["_rel_pdf"] = rel
        valid.append(ne)

    def sort_key(x: dict) -> tuple[str, str]:
        return (x.get("_pub_iso") or "", x.get("_rel_pdf") or "")

    valid.sort(key=sort_key, reverse=True)

    CCAA_HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)

    if CCAA_HISTORY_CSV.exists() and CCAA_HISTORY_CSV.stat().st_size > 0:
        with CCAA_HISTORY_CSV.open(encoding="utf-8") as f:
            header_line = f.readline()
        if "proyecto_fingerprint" not in header_line:
            n_mig, _ = backfill_csv(CCAA_HISTORY_CSV)
            print(f"[CCAA] Migración fingerprint: {n_mig} filas\n", flush=True)

    meta_cols = [
        "boletin_source_id",
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
    _migrate_csv_columns(CCAA_HISTORY_CSV, fieldnames)

    processed = _load_ccaa_processed(CCAA_HISTORY_CSV)
    print(
        f"[CCAA] Líneas índice leídas: {len(raw_rows)} | candidatos únicos (PDF ok, fecha): {len(valid)} "
        f"| ya en CSV: {len(processed)} | omitidos por fecha<corte: {skipped_date} "
        f"| sin PDF/path: {skipped_path} | sin fecha ni año en ruta: {skipped_nodate}",
        flush=True,
    )

    new_file = not CCAA_HISTORY_CSV.exists() or CCAA_HISTORY_CSV.stat().st_size == 0
    n = 0
    with CCAA_HISTORY_CSV.open("a", newline="", encoding="utf-8", buffering=1) as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if new_file:
            writer.writeheader()
            f.flush()
            os.fsync(f.fileno())

        for e in valid:
            folder_id = e["_folder_id"]
            ctx = context_for_folder(folder_id)
            sid = ctx.source_id
            d_str = e["_pub_iso"]
            a_str = e["_art_key"]
            if (sid, d_str, a_str) in processed:
                continue

            pdf_path: Path = e["_abs_pdf"]
            pdf_name = pdf_path.name
            n += 1
            t0 = time.time()
            err = ""
            print(f"[CCAA {n}] {sid} {d_str or '?'} {pdf_name}", flush=True)

            try:
                text = pdf_to_text(pdf_path)
            except Exception as ex:
                err = f"pdftotext:{ex}"
                text = ""

            txt_chars = len(text)
            parsed: dict = {}
            row: dict = {
                "boletin_source_id": sid,
                "bocm_date": d_str,
                "art_num": a_str,
                "title": _entry_title(e),
                "pdf_path": e["_rel_pdf"],
                "pdf_url": (e.get("pdf_url") or "")[:800],
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
                        ctx=ctx,
                        model=llm_model,
                        max_context_chars=max_context_chars,
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
                    context_meta_for_fulltext(text, max_context_chars=max_context_chars),
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

    print(f"\n=== [CCAA] Hecho. CSV: {CCAA_HISTORY_CSV} ===\n", flush=True)


def main() -> None:
    min_d = _parse_min_date(os.getenv("PARSE_HISTORY_MIN_DATE", "2020-01-01"))
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    run_ccaa_history_batch(client=client, min_bocm_date=min_d)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[CCAA interrumpido] última fila debería estar guardada.", flush=True)
        sys.exit(130)
