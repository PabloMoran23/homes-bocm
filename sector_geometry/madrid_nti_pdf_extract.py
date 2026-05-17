#!/usr/bin/env python3
"""
Extrae métricas urbanísticas (viviendas, m², edificabilidad, etc.) de PDFs NTI locales.

Pipeline por PDF:
  1. pdftotext (hasta N páginas)
  2. Regex (rápido)
  3. LLM opcional (API OpenAI-compatible: Ollama, vLLM, OpenAI)

Salidas:
  output/madrid_sigma_pdf_metrics.jsonl   — una fila por PDF procesado
  output/madrid_sigma_expediente_metrics.json — agregado por expediente

Uso desde poc-bocm/:
  python3 -m sector_geometry.madrid_nti_pdf_extract --pipeline --since-year 2020 --llm
  python3 -m sector_geometry.madrid_nti_pdf_extract --limit 8 --llm
  python3 -m sector_geometry.madrid_nti_pdf_extract --all-local --since-year 2020 --llm
  python3 -m sector_geometry.madrid_nti_pdf_extract --regex-only --pipeline

Variables LLM (igual que 3_llm_parse.py):
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_MAX_CONTEXT_CHARS
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from boletin_llm_parse import (
    BoletinContext,
    extract_numeric_snippets,
    merge_context_into_flat,
    normalize_llm_result,
    parse_with_llm,
    truncate_text,
)
from sector_geometry.madrid_nti_doc_roles import classify_doc_role
from sector_geometry.madrid_nti_pdf_metrics import (
    DOC_TYPE_PRIORITY,
    METRIC_KEYS,
    _metric_sane,
    extract_regex_metrics,
    infer_doc_type,
    merge_expediente_metrics,
)
from sector_geometry.madrid_nti_pdf_select import select_pipeline_jobs
from sector_geometry.madrid_viso_filters import expediente_is_recent, filter_nti_documents

POC_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = POC_ROOT / "output"
VISOR_JSON = OUTPUT_DIR / "madrid_viso_expedientes.json"
INDEX_JSON = OUTPUT_DIR / "madrid_ayto_expedientes_index.json"
DOWNLOAD_ROOT = OUTPUT_DIR / "madrid_nti_downloads"
PDF_METRICS_JSONL = OUTPUT_DIR / "madrid_sigma_pdf_metrics.jsonl"
EXP_METRICS_JSON = OUTPUT_DIR / "madrid_sigma_expediente_metrics.json"

NTI_CONTEXT = BoletinContext(
    source_id="madrid_sigma_nti",
    bulletin_name="Documentación técnica expediente urbanístico Ayuntamiento de Madrid (VISOR/NTI)",
    region_hint="Madrid capital, España — plan parcial, estudio de detalle, modificación PGOU, gestión, urbanización",
)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.1.15:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "local"))
LLM_MODEL = os.getenv("LLM_MODEL", "gemma4-small-8k:latest")
LLM_MAX_CONTEXT_CHARS = int(os.getenv("LLM_MAX_CONTEXT_CHARS", "6000"))
NTI_PDF_MAX_PAGES = int(os.getenv("NTI_PDF_MAX_PAGES", "25"))


def _norm_exp_slug(grupo: str) -> str:
    return grupo.replace("/", "_").replace("\\", "_").strip()


def pdf_to_text(pdf_path: Path, *, max_pages: int) -> tuple[str, int]:
    """Devuelve (texto, páginas_leídas)."""
    try:
        proc = subprocess.run(
            ["pdftotext", "-l", str(max_pages), str(pdf_path), "-"],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return "", 0
    if proc.returncode != 0:
        return "", 0
    return proc.stdout.decode("utf-8", errors="replace"), max_pages


def _load_index_by_grupo() -> dict[str, dict[str, Any]]:
    if not INDEX_JSON.is_file():
        return {}
    raw = json.loads(INDEX_JSON.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for row in raw.get("expedientes") or []:
        num = row.get("EXP_TX_NUMERO")
        if num:
            parts = str(num).strip().split("/")
            if len(parts) == 3 and parts[2].isdigit():
                key = f"{parts[0]}/{parts[1]}/{int(parts[2]):05d}"
            else:
                key = str(num).strip()
            out[key] = row
    return out


def _grupo_from_slug(slug: str) -> str:
    parts = slug.split("_")
    if len(parts) == 3 and parts[2].isdigit():
        return f"{parts[0]}/{parts[1]}/{int(parts[2]):05d}"
    return slug.replace("_", "/")


def iter_local_pdfs(
    visor: dict[str, Any],
    *,
    since_year: int | None,
    only_types: set[str] | None,
) -> list[dict[str, Any]]:
    """Lista trabajos desde disco (carpetas madrid_nti_downloads/*)."""
    by_g = visor.get("byGrupoExpediente") or {}
    jobs: list[dict[str, Any]] = []
    if not DOWNLOAD_ROOT.is_dir():
        return jobs
    for slug_dir in sorted(DOWNLOAD_ROOT.iterdir()):
        if not slug_dir.is_dir():
            continue
        grupo = _grupo_from_slug(slug_dir.name)
        rec = by_g.get(grupo) or {}
        if since_year is not None and not expediente_is_recent(rec, grupo, since_year=since_year):
            continue
        files_dir = slug_dir / "files"
        if not files_dir.is_dir():
            continue
        nti_docs = ((rec.get("ntiArbol") or {}).get("documentos") or []) if rec else []
        for i, pdf_path in enumerate(sorted(files_dir.glob("*.pdf"))):
            titulo = pdf_path.name
            ruta = ""
            # enriquecer con metadatos NTI si el índice encaja por posición/nombre
            if i < len(nti_docs):
                meta = nti_docs[i]
                titulo = (meta.get("titulo") or meta.get("tooltip") or pdf_path.name).strip()
                ruta = meta.get("rutaCarpetas") or ""
            else:
                meta = {"titulo": pdf_path.name, "rutaCarpetas": ""}
            doc_type = infer_doc_type(titulo, ruta, pdf_path.name)
            doc_role = classify_doc_role(titulo, ruta, pdf_path.name)
            if only_types and doc_type not in only_types:
                continue
            jobs.append(
                {
                    "grupo": grupo,
                    "rec": rec,
                    "meta": meta,
                    "local_path": pdf_path,
                    "doc_type": doc_type,
                    "doc_role": doc_role,
                    "doc_titulo": titulo,
                    "doc_ruta": ruta,
                    "doc_index": i,
                }
            )
    jobs.sort(key=lambda j: (j["grupo"], DOC_TYPE_PRIORITY.get(j["doc_type"], 9), j["doc_index"]))
    return jobs


def _regex_has_core_metrics(rx: dict[str, Any]) -> bool:
    return any(rx.get(k) is not None for k in ("num_viviendas_max", "sup_total_m2", "sup_edificable_m2"))


def process_pdf_job(
    job: dict[str, Any],
    *,
    client: OpenAI | None,
    use_llm: bool,
    llm_if_regex_empty: bool,
    max_pages: int,
) -> dict[str, Any]:
    grupo = job["grupo"]
    rec = job["rec"]
    meta = job["meta"]
    pdf_path: Path = job["local_path"]
    doc_type = job["doc_type"]
    doc_role = job.get("doc_role") or classify_doc_role(
        job.get("doc_titulo") or pdf_path.name,
        job.get("doc_ruta") or meta.get("rutaCarpetas") or "",
        pdf_path.name,
    )

    text, pages_read = pdf_to_text(pdf_path, max_pages=max_pages)
    rx = extract_regex_metrics(text)
    row: dict[str, Any] = {
        "expediente_grupo": grupo,
        "pdf_path": str(pdf_path.relative_to(POC_ROOT)),
        "pdf_name": pdf_path.name,
        "doc_type": doc_type,
        "doc_role": doc_role,
        "doc_titulo": meta.get("titulo"),
        "doc_ruta": meta.get("rutaCarpetas"),
        "text_chars": len(text),
        "pages_read": pages_read,
        "method": "regex",
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    for k in METRIC_KEYS:
        v = rx.get(k)
        row[k] = v if _metric_sane(k, v) else None
    row["texto_util"] = rx.get("texto_util", False)
    if rx.get("sup_ambito_strict"):
        row["sup_ambito_strict"] = True

    need_llm = use_llm and client is not None
    if need_llm and llm_if_regex_empty and _regex_has_core_metrics(rx) and rx.get("texto_util"):
        need_llm = False

    if need_llm and client is not None and len(text.strip()) >= 80:
        try:
            flat = parse_with_llm(
                client,
                text,
                pdf_path.name,
                ctx=NTI_CONTEXT,
                model=LLM_MODEL,
                max_context_chars=LLM_MAX_CONTEXT_CHARS,
            )
            row["method"] = "llm" if flat.get("es_relevante") else "llm_no_relevante"
            if flat.get("es_relevante"):
                for k in METRIC_KEYS:
                    v = flat.get(k)
                    if _metric_sane(k, v):
                        row[k] = v
                row["resumen"] = flat.get("resumen")
                row["tipo_instrumento"] = flat.get("tipo_instrumento")
                row["estado_tramitacion"] = flat.get("estado_tramitacion")
            row["llm_truncated"] = flat.get("texto_truncado_llm")
        except Exception as exc:
            row["llm_error"] = str(exc)[:500]
            row["method"] = "regex+llm_error"

    return row


def aggregate_expedientes(
    pdf_rows: list[dict[str, Any]],
    visor: dict[str, Any],
    index_by_g: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    by_exp: dict[str, list[dict[str, Any]]] = {}
    for r in pdf_rows:
        by_exp.setdefault(r["expediente_grupo"], []).append(r)

    out: dict[str, Any] = {"generatedAt": datetime.now(timezone.utc).isoformat(), "expedientes": {}}
    for grupo, rows in sorted(by_exp.items()):
        rec = (visor.get("byGrupoExpediente") or {}).get(grupo) or {}
        idx = index_by_g.get(grupo) or {}
        denom = idx.get("EXP_TX_DENOM") or ""
        tipo_inst = ""
        for r in rows:
            if r.get("tipo_instrumento"):
                tipo_inst = str(r["tipo_instrumento"])
                break
        agg = merge_expediente_metrics(
            rows,
            prefer_llm=True,
            denominacion=str(denom),
            tipo_instrumento=tipo_inst,
            familia_hint="",
        )
        out["expedientes"][grupo] = {
            "expediente_grupo": grupo,
            "denominacion": denom,
            "fase_sigma": idx.get("FAS_TX_DENOM"),
            "sigma_layer_kind": rec.get("sigmaLayerKind") or idx.get("sigma_layer_kind"),
            "tramitacion_ultima": _last_tramite(rec),
            "metrics": agg.get("metrics") or {},
            "hechos": agg.get("hechos") or [],
            "fuentes_pdf": agg.get("fuentes_pdf") or [],
            "doc_role_principal": agg.get("doc_role_principal"),
            "pdfs_procesados": len(rows),
        }
    return out


def _last_tramite(rec: dict[str, Any]) -> dict[str, Any] | None:
    tr = rec.get("tramitacion") or []
    if not tr:
        return None
    return tr[-1] if isinstance(tr[-1], dict) else None


def load_done_keys(jsonl_path: Path) -> set[str]:
    if not jsonl_path.is_file():
        return set()
    done: set[str] = set()
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
            k = o.get("pdf_path")
            if k:
                done.add(k)
        except json.JSONDecodeError:
            continue
    return done


def test_llm_connection(base_url: str, api_key: str, model: str) -> bool:
    client = OpenAI(api_key=api_key, base_url=base_url)
    client.models.list()
    print(f"  Conexión OK: {base_url}", flush=True)
    return True


def run_test_llm(
    *,
    base_url: str,
    api_key: str,
    model: str,
    max_pages: int,
    since_year: int | None,
) -> None:
    """Prueba LLM en ~5 PDFs de expedientes distintos (memoria/resumen)."""
    if not VISOR_JSON.is_file():
        raise SystemExit(f"No existe {VISOR_JSON}")
    visor = json.loads(VISOR_JSON.read_text(encoding="utf-8"))
    index_by_g = _load_index_by_grupo()
    jobs = iter_local_pdfs(visor, since_year=since_year, only_types={"memoria", "resumen_ejecutivo"})
    # un PDF por expediente
    seen: set[str] = set()
    picked: list[dict[str, Any]] = []
    for j in jobs:
        if j["grupo"] in seen:
            continue
        seen.add(j["grupo"])
        picked.append(j)
        if len(picked) >= 5:
            break
    if not picked:
        raise SystemExit("No hay PDFs locales memoria/resumen para probar.")

    print(f"Prueba LLM: {len(picked)} PDFs de {len(seen)} expedientes", flush=True)
    print(f"  URL: {base_url}  model: {model}", flush=True)
    client = OpenAI(api_key=api_key, base_url=base_url)
    try:
        test_llm_connection(base_url, api_key, model)
    except Exception as exc:
        print(f"  ERROR conexión: {exc}", flush=True)
        print("  Si Ollama está en esta máquina: export LLM_BASE_URL=http://127.0.0.1:11434/v1", flush=True)
        raise SystemExit(1) from exc

    for i, job in enumerate(picked):
        print(f"\n{'='*60}\n[{i+1}] {job['grupo']} | {job['local_path'].name}\n{'='*60}", flush=True)
        text, _ = pdf_to_text(job["local_path"], max_pages=max_pages)
        rx = extract_regex_metrics(text)
        print(
            f"  REGEX: viv={rx.get('num_viviendas_max')} sup={rx.get('sup_total_m2')} "
            f"edif={rx.get('sup_edificable_m2')} tipo={rx.get('tipo_vivienda')} chars={len(text)}",
            flush=True,
        )
        t0 = time.time()
        flat = parse_with_llm(
            client,
            text,
            job["local_path"].name,
            ctx=NTI_CONTEXT,
            model=model,
            max_context_chars=LLM_MAX_CONTEXT_CHARS,
        )
        dt = time.time() - t0
        print(f"  LLM ({dt:.1f}s): relevante={flat.get('es_relevante')}", flush=True)
        if flat.get("es_relevante"):
            print(
                f"         viv={flat.get('num_viviendas_max')} sup={flat.get('sup_total_m2')} "
                f"edif={flat.get('sup_edificable_m2')} tipo={flat.get('tipo_vivienda')}",
                flush=True,
            )
            print(f"         instrumento={flat.get('tipo_instrumento')} sector={flat.get('nombre_sector')}", flush=True)
            if flat.get("resumen"):
                print(f"         resumen: {str(flat.get('resumen'))[:200]}...", flush=True)
        else:
            print(f"         (no relevante o parseo vacío)", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Extrae métricas de PDFs NTI Madrid (regex + LLM).")
    ap.add_argument("--limit", type=int, default=0, help="Máx. PDFs a procesar (0=todos los jobs).")
    ap.add_argument(
        "--pipeline",
        action="store_true",
        help="Selección inteligente: hasta N PDFs/rol por expediente (recomendado).",
    )
    ap.add_argument(
        "--max-pdfs-per-exp",
        type=int,
        default=8,
        help="Con --pipeline: máx. PDFs por expediente.",
    )
    ap.add_argument("--all-local", action="store_true", help="Todos los PDF locales con índice NTI.")
    ap.add_argument("--since-year", type=int, default=0, help="Filtrar expedientes/docs >= año.")
    ap.add_argument("--llm", action="store_true", help="Usar LLM además de regex.")
    ap.add_argument(
        "--llm-always",
        action="store_true",
        help="Llamar LLM aunque regex ya tenga viviendas/m².",
    )
    ap.add_argument("--regex-only", action="store_true", help="No llamar al LLM.")
    ap.add_argument("--max-pages", type=int, default=NTI_PDF_MAX_PAGES)
    ap.add_argument(
        "--doc-types",
        nargs="*",
        default=["resumen_ejecutivo", "memoria", "informe_tecnico", "informe_juridico", "acuerdo"],
        help="Tipos documentales a procesar.",
    )
    ap.add_argument("--delay", type=float, default=0.0, help="Pausa entre PDFs (LLM).")
    ap.add_argument("--force", action="store_true", help="Reprocesar aunque ya esté en el JSONL.")
    ap.add_argument("--test-llm", action="store_true", help="Probar conexión y 5 PDFs (sin escribir JSONL).")
    ap.add_argument("--llm-base-url", default="", help="Override LLM_BASE_URL.")
    args = ap.parse_args()

    base_url = (args.llm_base_url or LLM_BASE_URL).strip()
    api_key = LLM_API_KEY
    model = LLM_MODEL

    if not VISOR_JSON.is_file():
        raise SystemExit(f"No existe {VISOR_JSON}")

    since_year = args.since_year if args.since_year > 0 else None

    if args.test_llm:
        run_test_llm(
            base_url=base_url,
            api_key=api_key,
            model=model,
            max_pages=args.max_pages,
            since_year=since_year,
        )
        return
    only_types = set(args.doc_types) if args.doc_types else None
    use_llm = args.llm and not args.regex_only
    use_pipeline = args.pipeline or (not args.all_local and only_types is None)
    # En modo pipeline se filtra por rol después; no recortar en iter_local_pdfs
    iter_types = None if use_pipeline else only_types

    visor = json.loads(VISOR_JSON.read_text(encoding="utf-8"))
    index_by_g = _load_index_by_grupo()
    jobs = iter_local_pdfs(visor, since_year=since_year, only_types=iter_types)
    raw_count = len(jobs)
    if use_pipeline:
        jobs = select_pipeline_jobs(jobs, max_pdfs_per_exp=args.max_pdfs_per_exp)
    if not args.all_local and args.limit <= 0 and not use_pipeline:
        args.limit = 10
    if args.limit > 0:
        jobs = jobs[: args.limit]

    print(f"PDFs en cola: {len(jobs)} (raw={raw_count}, pipeline={use_pipeline})", flush=True)
    print(f"  LLM: {use_llm} ({base_url} / {model})", flush=True)
    print(f"  since_year: {since_year}", flush=True)

    client: OpenAI | None = None
    if use_llm:
        client = OpenAI(api_key=api_key, base_url=base_url)
        try:
            test_llm_connection(base_url, api_key, model)
        except Exception as exc:
            print(f"  AVISO: LLM no responde ({exc}); solo regex", flush=True)
            client = None
            use_llm = False

    done = load_done_keys(PDF_METRICS_JSONL)
    pdf_rows: list[dict[str, Any]] = []
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    with PDF_METRICS_JSONL.open("a", encoding="utf-8") as fj:
        for i, job in enumerate(jobs):
            rel = str(job["local_path"].relative_to(POC_ROOT))
            if rel in done and not args.force:
                continue
            if args.delay > 0 and i > 0:
                time.sleep(args.delay)
            row = process_pdf_job(
                job,
                client=client,
                use_llm=use_llm,
                llm_if_regex_empty=not args.llm_always,
                max_pages=args.max_pages,
            )
            fj.write(json.dumps(row, ensure_ascii=False) + "\n")
            fj.flush()
            pdf_rows.append(row)
            viv = row.get("num_viviendas_max")
            m2 = row.get("sup_total_m2")
            ed = row.get("sup_edificable_m2")
            print(
                f"  [{i+1}/{len(jobs)}] {job['grupo']} | {row.get('doc_role')} | {row['method']} "
                f"| viv={viv} sup={m2} edif={ed} chars={row['text_chars']}",
                flush=True,
            )

    # Recargar todas las filas del jsonl para agregado
    all_rows: list[dict[str, Any]] = []
    if PDF_METRICS_JSONL.is_file():
        for line in PDF_METRICS_JSONL.read_text(encoding="utf-8").splitlines():
            if line.strip():
                all_rows.append(json.loads(line))

    agg = aggregate_expedientes(all_rows, visor, index_by_g)
    agg["pdf_rows_total"] = len(all_rows)
    EXP_METRICS_JSON.write_text(json.dumps(agg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nEscrito {PDF_METRICS_JSONL} (+{len(pdf_rows)} filas esta corrida)", flush=True)
    print(f"Escrito {EXP_METRICS_JSON} ({len(agg.get('expedientes') or {})} expedientes)", flush=True)


if __name__ == "__main__":
    main()
