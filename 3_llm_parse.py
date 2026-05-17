"""
BOCM LLM Parser — estructura el texto extraído de los PDFs usando cualquier
API compatible con OpenAI (OpenAI, Gemma local, Ollama, etc.)

El núcleo genérico vive en boletin_llm_parse.py (prompt multi-fuente, esquema
enriquecido, columnas extra para presupuesto / ayudas / procedimiento).

Variables de entorno:
  LLM_BASE_URL   URL base de la API  (default: http://192.168.1.15:11434/v1 — Ollama en red local)
  LLM_API_KEY    API key             (default: "local" para Ollama)
  LLM_MODEL      Nombre del modelo   (default: gemma4-small-8k:latest)
  BOLETIN_SOURCE_ID   (default: bocm)
  BOLETIN_NAME        (default: Boletín Oficial de la Comunidad de Madrid (BOCM))
  BOLETIN_REGION_HINT (default: Comunidad de Madrid, España)
  SKIP_CCAA_SPOTCHECK=1  (no ejecutar al final el spot-check de 5 PDFs aleatorios multi-CCAA)
  CCAA_SPOTCHECK_SEED=n  (semilla para la muestra aleatoria)
  LLM_MAX_CONTEXT_CHARS   (default 4000; columnas requiere_segunda_pasada / texto_truncado_llm en CSV)

Ejemplo con Gemma local:
  LLM_BASE_URL=http://192.168.1.15:11434/v1 LLM_MODEL=gemma4-small-8k:latest python3 3_llm_parse.py

Genera output/proyectos.csv con todos los registros.
"""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path

from openai import OpenAI

from boletin_llm_parse import (
    BoletinContext,
    DEFAULT_CONTEXT,
    FIELDS,
    extract_raw_from_llm,
    flatten_record,
    merge_context_into_flat,
    normalize_llm_result,
    parse_with_llm,
)
from ccaa_spotcheck import maybe_run_ccaa_spotcheck_after_job

OUTPUT_DIR = Path("output")
INDEX_FILE = OUTPUT_DIR / "index.json"
CSV_FILE = OUTPUT_DIR / "proyectos.csv"

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.1.15:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "local"))
LLM_MODEL = os.getenv("LLM_MODEL", "gemma4-small-8k:latest")
LLM_MAX_CONTEXT_CHARS = int(os.getenv("LLM_MAX_CONTEXT_CHARS", "4000"))


def _load_context() -> BoletinContext:
    sid = os.getenv("BOLETIN_SOURCE_ID", DEFAULT_CONTEXT.source_id)
    name = os.getenv("BOLETIN_NAME", DEFAULT_CONTEXT.bulletin_name)
    region = os.getenv("BOLETIN_REGION_HINT", DEFAULT_CONTEXT.region_hint)
    return BoletinContext(source_id=sid, bulletin_name=name, region_hint=region)


def main():
    print("=== Boletín LLM Parser ===", flush=True)
    print(f"  base_url : {LLM_BASE_URL}", flush=True)
    print(f"  model    : {LLM_MODEL}", flush=True)
    print(f"  api_key  : {'*' * min(len(LLM_API_KEY), 8)} ({len(LLM_API_KEY)} chars)", flush=True)
    ctx = _load_context()
    print(f"  fuente   : {ctx.source_id} — {ctx.bulletin_name}\n", flush=True)

    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    if not INDEX_FILE.exists():
        print(f"No se encontró {INDEX_FILE}. Ejecuta primero 2_extract_text.py", flush=True)
        return

    index = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    index.sort(key=lambda x: x.get("chars", 0))
    print(f"Documentos a procesar: {len(index)}\n", flush=True)

    results = []
    skipped = 0

    for i, meta in enumerate(index):
        txt_path = Path(meta["txt"])
        pdf_name = Path(meta["pdf"]).name
        t0 = time.time()
        print(f"[{i+1}/{len(index)}] {pdf_name}  ({meta.get('chars',0)} chars)", flush=True)

        if not txt_path.exists():
            print(f"  [skip] no existe {txt_path}", flush=True)
            continue

        full_text = txt_path.read_text(encoding="utf-8")
        if len(full_text) < 50:
            print(f"  [skip] texto demasiado corto", flush=True)
            continue

        raw, ctx_meta = extract_raw_from_llm(
            client,
            full_text,
            pdf_name,
            ctx=ctx,
            model=LLM_MODEL,
            max_context_chars=LLM_MAX_CONTEXT_CHARS,
        )
        if raw:
            llm_flat = normalize_llm_result(raw)
        else:
            llm_flat = {k: None for k in FIELDS} | {"es_relevante": None}
        merge_context_into_flat(llm_flat, ctx_meta)
        elapsed = time.time() - t0

        if llm_flat.get("es_relevante") is False:
            skipped += 1
            print(f"  → {elapsed:.0f}s | [NO RELEVANTE] descartado", flush=True)
            continue

        municipio = llm_flat.get("municipio") or "?"
        tipo = llm_flat.get("tipo_instrumento") or "?"
        nviv = llm_flat.get("num_viviendas_max") or "?"
        estado = llm_flat.get("estado_tramitacion") or "?"
        fecha_fin = llm_flat.get("fecha_fin_estimada") or "?"
        cats = llm_flat.get("categorias_tematicas") or "?"
        seg = " | 2ªpasada" if llm_flat.get("requiere_segunda_pasada") else ""
        print(
            f"  → {elapsed:.0f}s | {municipio} | {tipo} | viv={nviv} | fin={fecha_fin} | {estado} | [{cats}]{seg}",
            flush=True,
        )

        record = flatten_record(llm_flat, meta)
        results.append(record)

        json_out = OUTPUT_DIR / (txt_path.stem + "_parsed.json")
        json_out.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

        time.sleep(0.3)

    if not results:
        print(f"No hay resultados relevantes ({skipped} descartados).", flush=True)
        maybe_run_ccaa_spotcheck_after_job(client=client, model=LLM_MODEL)
        return

    all_keys = list(results[0].keys())
    with CSV_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n=== CSV generado: {CSV_FILE} ({len(results)} filas, {skipped} descartados) ===", flush=True)

    with_viviendas = sum(1 for r in results if r.get("num_viviendas_max"))
    with_fecha_fin = sum(1 for r in results if r.get("fecha_fin_estimada"))
    with_cats = sum(1 for r in results if r.get("categorias_tematicas"))
    tipos = {}
    for r in results:
        t = r.get("tipo_instrumento") or "desconocido"
        tipos[t] = tipos.get(t, 0) + 1

    print(f"\nEstadísticas:", flush=True)
    print(f"  Con num_viviendas  : {with_viviendas}/{len(results)}", flush=True)
    print(f"  Con fecha_fin      : {with_fecha_fin}/{len(results)}", flush=True)
    print(f"  Con categorías     : {with_cats}/{len(results)}", flush=True)
    print(f"  Por tipo:")
    for t, c in sorted(tipos.items(), key=lambda x: -x[1]):
        print(f"    {t}: {c}", flush=True)

    maybe_run_ccaa_spotcheck_after_job(client=client, model=LLM_MODEL)


# Re-export para parse_history_nightly y scripts que importan el módulo dinámicamente
__all__ = [
    "FIELDS",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "parse_with_llm",
    "BoletinContext",
    "DEFAULT_CONTEXT",
    "extract_raw_from_llm",
    "merge_context_into_flat",
    "normalize_llm_result",
    "flatten_record",
]

if __name__ == "__main__":
    main()
