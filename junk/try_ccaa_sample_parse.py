"""
Prueba el parser genérico con 5 PDFs de distintas comunidades (ccaa-boletines).

Uso (desde poc-bocm):
  python3 try_ccaa_sample_parse.py
  # Por defecto: Ollama en 192.168.1.15, modelo gemma4-small-8k:latest. Sobrescribir con:
  LLM_BASE_URL=http://otro:11434/v1 LLM_MODEL=otro-modelo python3 try_ccaa_sample_parse.py
  OPENAI_API_KEY=sk-... LLM_BASE_URL=https://api.openai.com/v1 LLM_MODEL=gpt-4o-mini python3 try_ccaa_sample_parse.py

Solo comprobar que existen los PDFs y cuántos caracteres extrae pdftotext (sin LLM):
  python3 try_ccaa_sample_parse.py --check-only

Salida: output/ccaa_sample_parse.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path

from openai import OpenAI

from boletin_llm_parse import (
    BoletinContext,
    FIELDS,
    context_meta_for_fulltext,
    extract_raw_from_llm,
    merge_context_into_flat,
    normalize_llm_result,
)

BASE = Path(__file__).resolve().parent
CCAA_ROOT = BASE.parent / "ccaa-boletines" / "pdfs_history"
OUT_JSON = BASE / "output" / "ccaa_sample_parse.json"

# (carpeta bajo pdfs_history, BoletinContext, ruta relativa a CCAA_ROOT de un PDF de prueba)
SAMPLES: list[tuple[str, BoletinContext, str]] = [
    (
        "boja",
        BoletinContext(
            source_id="boja",
            bulletin_name="Boletín Oficial de la Junta de Andalucía (BOJA)",
            region_hint="Andalucía, España",
        ),
        "boja/vivienda/2020/BOJA-2020-199-disposition.2020.199.77.pdf",
    ),
    (
        "dogv",
        BoletinContext(
            source_id="dogv",
            bulletin_name="Diari Oficial de la Generalitat Valenciana (DOGV)",
            region_hint="Comunitat Valenciana, España",
        ),
        "dogv/vivienda/2020/DOGV-2020-6393.pdf",
    ),
    (
        "bocyl",
        BoletinContext(
            source_id="bocyl",
            bulletin_name="Boletín Oficial de Castilla y León (BOCyL)",
            region_hint="Castilla y León, España",
        ),
        "bocyl/vivienda/2020/BOCYL-20200330-30032020-4.pdf",
    ),
    (
        "docm",
        BoletinContext(
            source_id="docm",
            bulletin_name="Diario Oficial de Castilla-La Mancha (DOCM)",
            region_hint="Castilla-La Mancha, España",
        ),
        # Nota: evitar DOCM solo por consejería "Vivienda" en el título — puede ser energía/otro;
        # este anuncio trata ayuda al alquiler y notificación.
        "docm/vivienda/2011/DOCM-20111108-2011_15556.pdf",
    ),
    (
        "boc_canarias",
        BoletinContext(
            source_id="boc_canarias",
            bulletin_name="Boletín Oficial de Canarias (BOC)",
            region_hint="Canarias, España",
        ),
        "boc_canarias/vivienda/2020/BOC-20201230-269-5265.pdf",
    ),
]


def pdf_to_text(pdf: Path) -> str:
    r = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout or ""


def main() -> None:
    ap = argparse.ArgumentParser(description="Prueba parser boletín con PDFs de varias CCAA")
    ap.add_argument(
        "--check-only",
        action="store_true",
        help="Solo verificar rutas y extracción de texto (sin llamar al LLM)",
    )
    args = ap.parse_args()

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []

    if args.check_only:
        for folder, ctx, rel in SAMPLES:
            pdf = CCAA_ROOT / rel
            ok = pdf.is_file()
            text = pdf_to_text(pdf) if ok else ""
            results.append(
                {
                    "folder": folder,
                    "source_id": ctx.source_id,
                    "pdf": rel,
                    "pdf_exists": ok,
                    "chars": len(text),
                    "preview": (text[:400].replace("\n", " ") + "…") if len(text) > 400 else text.replace("\n", " "),
                }
            )
            st = "OK" if ok else "FALTA"
            print(f"{st}  {ctx.source_id:14}  {len(text):6} chars  {rel}", flush=True)
        OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n→ {OUT_JSON} (--check-only, sin LLM)", flush=True)
        return

    base_url = os.getenv("LLM_BASE_URL", "http://192.168.1.15:11434/v1")
    api_key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "local"))
    model = os.getenv("LLM_MODEL", "gemma4-small-8k:latest")

    if api_key in ("", "local") and "api.openai.com" in base_url:
        print(
            "Aviso: sin OPENAI_API_KEY válida la API de OpenAI devolverá 401. "
            "Exporta OPENAI_API_KEY o usa LLM_BASE_URL apuntando a Ollama/vLLM.\n",
            flush=True,
        )

    client = OpenAI(api_key=api_key, base_url=base_url)

    for folder, ctx, rel in SAMPLES:
        pdf = CCAA_ROOT / rel
        if not pdf.is_file():
            results.append(
                {
                    "folder": folder,
                    "source_id": ctx.source_id,
                    "pdf": rel,
                    "error": "pdf_no_encontrado",
                    "path_checked": str(pdf),
                }
            )
            print(f"FALTA PDF  {rel}", flush=True)
            continue

        text = pdf_to_text(pdf)
        t0 = time.time()
        try:
            raw, ctx_meta = extract_raw_from_llm(
                client, text, pdf.name, ctx=ctx, model=model, max_context_chars=4500
            )
            flat = (
                normalize_llm_result(raw)
                if raw
                else {k: None for k in FIELDS} | {"es_relevante": None}
            )
            merge_context_into_flat(flat, ctx_meta)
            err = None
        except Exception as ex:
            raw = {}
            flat = {k: None for k in FIELDS} | {"es_relevante": None}
            merge_context_into_flat(flat, context_meta_for_fulltext(text, max_context_chars=4500))
            err = str(ex)
        elapsed = round(time.time() - t0, 2)

        results.append(
            {
                "folder": folder,
                "source_id": ctx.source_id,
                "pdf": rel,
                "chars": len(text),
                "latency_s": elapsed,
                "error": err,
                "raw_llm": raw,
                "flat": flat,
            }
        )
        hint = (flat.get("municipio") or flat.get("categorias_tematicas") or "")[:60]
        err_mark = f" ERR: {err[:80]}…" if err else ""
        print(
            f"{ctx.source_id:14} {elapsed:5.1f}s  relevante={flat.get('es_relevante')}  {hint}{err_mark}",
            flush=True,
        )

    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {OUT_JSON}", flush=True)


if __name__ == "__main__":
    main()
