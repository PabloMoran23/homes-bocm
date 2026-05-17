"""
Spot-check del parser: 5 PDFs aleatorios de comunidades distintas (ccaa-boletines).

Uso directo:
  python3 ccaa_spotcheck.py
  SKIP_CCAA_SPOTCHECK=1  → no-op si se llama desde otros scripts

Variables: mismas que el parser (LLM_BASE_URL, LLM_MODEL, …).
CCAA_SPOTCHECK_SEED=n  → semilla para reproducir la muestra aleatoria.
"""

from __future__ import annotations

import json
import os
import random
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

POC_BOCM = Path(__file__).resolve().parent
CCAA_ROOT = POC_BOCM.parent / "ccaa-boletines" / "pdfs_history"
DEFAULT_OUT = POC_BOCM / "output" / "ccaa_spotcheck_last.json"

_MIN_PDF_BYTES = 512

# Contexto por carpeta bajo pdfs_history (fallback genérico si falta alguna)
_CCAA_CONTEXTS: dict[str, BoletinContext] = {
    "boja": BoletinContext(
        source_id="boja",
        bulletin_name="Boletín Oficial de la Junta de Andalucía (BOJA)",
        region_hint="Andalucía, España",
    ),
    "dogv": BoletinContext(
        source_id="dogv",
        bulletin_name="Diari Oficial de la Generalitat Valenciana (DOGV)",
        region_hint="Comunitat Valenciana, España",
    ),
    "bocyl": BoletinContext(
        source_id="bocyl",
        bulletin_name="Boletín Oficial de Castilla y León (BOCyL)",
        region_hint="Castilla y León, España",
    ),
    "docm": BoletinContext(
        source_id="docm",
        bulletin_name="Diario Oficial de Castilla-La Mancha (DOCM)",
        region_hint="Castilla-La Mancha, España",
    ),
    "boc_canarias": BoletinContext(
        source_id="boc_canarias",
        bulletin_name="Boletín Oficial de Canarias (BOC)",
        region_hint="Canarias, España",
    ),
    "bopa": BoletinContext(
        source_id="bopa",
        bulletin_name="Boletín Oficial del Principado de Asturias (BOPA)",
        region_hint="Principado de Asturias, España",
    ),
    "boc_cantabria": BoletinContext(
        source_id="boc_cantabria",
        bulletin_name="Boletín Oficial de Cantabria (BOC)",
        region_hint="Cantabria, España",
    ),
    "boib": BoletinContext(
        source_id="boib",
        bulletin_name="Butlletí Oficial de les Illes Balears (BOIB)",
        region_hint="Illes Balears, España",
    ),
    "dog": BoletinContext(
        source_id="dog",
        bulletin_name="Diario Oficial de Galicia (DOG)",
        region_hint="Galicia, España",
    ),
    "bopv": BoletinContext(
        source_id="bopv",
        bulletin_name="Boletín Oficial del País Vasco (BOPV)",
        region_hint="Euskadi, España",
    ),
    "borm": BoletinContext(
        source_id="borm",
        bulletin_name="Boletín Oficial de la Región de Murcia (BORM)",
        region_hint="Región de Murcia, España",
    ),
    "dogc": BoletinContext(
        source_id="dogc",
        bulletin_name="Diari Oficial de la Generalitat de Catalunya (DOGC)",
        region_hint="Catalunya, España",
    ),
}


def context_for_folder(folder_id: str) -> BoletinContext:
    if folder_id in _CCAA_CONTEXTS:
        return _CCAA_CONTEXTS[folder_id]
    return BoletinContext(
        source_id=folder_id,
        bulletin_name=f"Boletín / fuente «{folder_id}»",
        region_hint="España",
    )


def pdf_to_text(pdf: Path) -> str:
    r = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return r.stdout or ""


def _list_community_dirs() -> list[Path]:
    if not CCAA_ROOT.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(CCAA_ROOT.iterdir()):
        if p.is_dir() and not p.name.startswith("."):
            out.append(p)
    return out


def _pdfs_for_community(comm: Path) -> list[Path]:
    v = comm / "vivienda"
    candidates: list[Path] = []
    roots = [v] if v.is_dir() else [comm]
    for root in roots:
        for pdf in root.rglob("*.pdf"):
            try:
                if pdf.is_file() and pdf.stat().st_size >= _MIN_PDF_BYTES:
                    candidates.append(pdf)
            except OSError:
                continue
    return candidates


def pick_random_ccaa_pdfs(
    *,
    k: int = 5,
    rng: random.Random | None = None,
) -> list[tuple[str, BoletinContext, Path]]:
    """
    Elige k comunidades distintas con al menos un PDF y un PDF aleatorio por comunidad.
    Devuelve (folder_id, context, path_absoluto).
    """
    rng = rng or random.Random()
    communities = _list_community_dirs()
    eligible: list[tuple[str, list[Path]]] = []
    for c in communities:
        pdfs = _pdfs_for_community(c)
        if pdfs:
            eligible.append((c.name, pdfs))
    if not eligible:
        return []
    rng.shuffle(eligible)
    chosen = eligible[: min(k, len(eligible))]
    out: list[tuple[str, BoletinContext, Path]] = []
    for folder_id, pdfs in chosen:
        pdf = rng.choice(pdfs)
        out.append((folder_id, context_for_folder(folder_id), pdf))
    return out


def run_ccaa_spotcheck(
    *,
    client: OpenAI,
    model: str,
    max_context_chars: int = 4500,
    k: int = 5,
    seed: int | None = None,
    out_json: Path | None = None,
) -> list[dict]:
    """
    Ejecuta el LLM sobre k PDFs aleatorios (comunidades distintas).
    Escribe JSON y devuelve la lista de resultados.
    """
    out_json = out_json or DEFAULT_OUT
    out_json.parent.mkdir(parents=True, exist_ok=True)

    seed_val = seed
    if seed_val is None and os.getenv("CCAA_SPOTCHECK_SEED"):
        try:
            seed_val = int(os.getenv("CCAA_SPOTCHECK_SEED", ""))
        except ValueError:
            seed_val = None
    rng = random.Random(seed_val)

    picks = pick_random_ccaa_pdfs(k=k, rng=rng)
    results: list[dict] = []

    print(f"\n=== Spot-check CCAA ({len(picks)} PDFs, seed={seed_val!r}) ===", flush=True)

    for folder_id, ctx, pdf in picks:
        rel = str(pdf.relative_to(CCAA_ROOT)) if CCAA_ROOT in pdf.parents else str(pdf)
        text = pdf_to_text(pdf)
        t0 = time.time()
        err = None
        raw: dict = {}
        try:
            raw, ctx_meta = extract_raw_from_llm(
                client, text, pdf.name, ctx=ctx, model=model, max_context_chars=max_context_chars
            )
            flat = (
                normalize_llm_result(raw)
                if raw
                else {fn: None for fn in FIELDS} | {"es_relevante": None}
            )
            merge_context_into_flat(flat, ctx_meta)
        except Exception as ex:
            flat = {fn: None for fn in FIELDS} | {"es_relevante": None}
            merge_context_into_flat(
                flat, context_meta_for_fulltext(text, max_context_chars=max_context_chars)
            )
            err = str(ex)
        elapsed = round(time.time() - t0, 2)

        results.append(
            {
                "folder": folder_id,
                "source_id": ctx.source_id,
                "pdf": rel,
                "chars": len(text),
                "latency_s": elapsed,
                "error": err,
                "seed": seed_val,
                "raw_llm": raw,
                "flat": flat,
            }
        )
        hint = (flat.get("municipio") or flat.get("categorias_tematicas") or "")[:55]
        em = f" | ERR {err[:70]}…" if err else ""
        print(f"  {ctx.source_id:16} {elapsed:5.1f}s rel={flat.get('es_relevante')} {hint}{em}", flush=True)

    out_json.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  → {out_json}\n", flush=True)
    return results


def maybe_run_ccaa_spotcheck_after_job(
    *,
    client: OpenAI,
    model: str,
) -> None:
    """Si no está desactivado por env, ejecuta el spot-check al final de un job de parseo."""
    if os.getenv("SKIP_CCAA_SPOTCHECK", "").strip().lower() in ("1", "true", "yes"):
        print("Spot-check CCAA omitido (SKIP_CCAA_SPOTCHECK).", flush=True)
        return
    if not CCAA_ROOT.is_dir():
        print("Spot-check CCAA omitido (no existe ccaa-boletines/pdfs_history).", flush=True)
        return
    try:
        run_ccaa_spotcheck(client=client, model=model)
    except Exception as ex:
        print(f"Spot-check CCAA falló (no aborta el job): {ex}", flush=True)


def main() -> None:
    base_url = os.getenv("LLM_BASE_URL", "http://192.168.1.15:11434/v1")
    api_key = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", "local"))
    model = os.getenv("LLM_MODEL", "gemma4-small-8k:latest")
    client = OpenAI(api_key=api_key, base_url=base_url)
    run_ccaa_spotcheck(client=client, model=model)


if __name__ == "__main__":
    main()
