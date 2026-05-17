"""
POC: Estructurar 3 PDFs del histórico usando el modelo small (OpenAI compatible)
y evaluar la calidad comparando con texto extraído del propio PDF.

Salida:
  output/poc_small_examples.csv
  output/poc_small_examples_eval.md
"""

import csv
import os
import re
import subprocess
import time
from pathlib import Path

from openai import OpenAI

from boletin_llm_parse import BoletinContext, FIELDS, parse_with_llm

BASE_DIR = Path("/home/pablo/homes/poc-bocm")
OUT_DIR = BASE_DIR / "output"
OUT_DIR.mkdir(exist_ok=True)

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://192.168.1.15:11434/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "local")
LLM_MODEL = os.getenv("LLM_MODEL", "gemma4-small-8k:latest")

CSV_PATH = OUT_DIR / "poc_small_examples.csv"
EVAL_PATH = OUT_DIR / "poc_small_examples_eval.md"


EXAMPLES = [
    {
        "id": "torrelodones_20110224_80",
        "pdf_path": "pdfs_history/2011/BOCM-20110224-80.pdf",
        "note": "Plan Parcial/PRI, incluye 'Número máximo de viviendas ... 10 viv.'",
    },
    {
        "id": "rivas_20110308_56",
        "pdf_path": "pdfs_history/2011/BOCM-20110308-56.pdf",
        "note": "Incluye 'Tiene 76 viviendas en total' con contexto de parcela/edificabilidad.",
    },
    {
        "id": "normas_20110114_16",
        "pdf_path": "pdfs_history/2011/BOCM-20110114-16.pdf",
        "note": "Normas urbanísticas; aparece '... de 9 viviendas a 120 viviendas'.",
    },
]


RE_VIV_SNIPPET = re.compile(
    r"(n[uú]mero\s+(?:m[aá]ximo\s+)?de\s+viviendas[^:]*?:\s*\d[\d\.,]*\s*\w*|"
    r"\b\d{1,5}(?:[\.,]\d{1,3})?\s+viviendas?\b|"
    r"de\s+\d+\s+viviendas\s+a\s+\d+\s+viviendas)",
    re.IGNORECASE,
)


def pdftotext(pdf: Path) -> str:
    return subprocess.check_output(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf), "-"],
        text=True,
        stderr=subprocess.DEVNULL,
    )


def key_snippets(text: str, max_snippets: int = 6) -> str:
    snippets = []
    for m in RE_VIV_SNIPPET.finditer(text):
        start = max(0, m.start() - 120)
        end = min(len(text), m.end() + 160)
        s = text[start:end].replace("\n", " ").strip()
        if s and s not in snippets:
            snippets.append(s)
        if len(snippets) >= max_snippets:
            break
    if not snippets:
        return ""
    return "\n\n[SNIPPETS]\n" + "\n".join(f"- {s}" for s in snippets)


def call_llm(client: OpenAI, pdf_name: str, full_text: str) -> dict:
    ctx = BoletinContext(
        source_id="bocm",
        bulletin_name="Boletín Oficial de la Comunidad de Madrid (BOCM)",
        region_hint="Comunidad de Madrid, España",
    )
    return parse_with_llm(client, full_text, pdf_name, ctx=ctx, model=LLM_MODEL)


def to_row(o: dict, meta: dict) -> dict:
    row = {k: o.get(k) for k in FIELDS}
    row["pdf_path"] = meta["pdf_path"]
    row["id"] = meta["id"]
    return row


def eval_against_text(row: dict, full_text: str) -> dict:
    """Heurística simple: comprobar si el número de viviendas está en el texto y si coincide."""
    text_has = None
    m = RE_VIV_SNIPPET.search(full_text)
    if m:
        # Extraer el número mayor encontrado en el snippet como referencia
        nums = [int(n.replace(".", "").replace(",", "")) for n in re.findall(r"\d{1,5}(?:[.,]\d{1,3})?", m.group(0))]
        if nums:
            text_has = max(nums)

    llm_viv = row.get("num_viviendas_max")
    try:
        llm_viv_int = int(str(llm_viv).replace(".", "").replace(",", ""))
    except Exception:
        llm_viv_int = None

    return {
        "text_viviendas_guess": text_has,
        "llm_viviendas": llm_viv_int,
        "viviendas_match": (text_has is not None and llm_viv_int == text_has),
    }


def main():
    client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)

    rows = []
    eval_lines = [
        "## POC small: evaluación rápida",
        "",
        f"- **base_url**: `{LLM_BASE_URL}`",
        f"- **model**: `{LLM_MODEL}`",
        "",
    ]

    for ex in EXAMPLES:
        pdf = BASE_DIR / ex["pdf_path"]
        assert pdf.exists(), f"No existe: {pdf}"
        pdf_name = pdf.name

        full_text = pdftotext(pdf)
        t0 = time.time()
        parsed = call_llm(client, pdf_name, full_text)
        dt = time.time() - t0

        row = to_row(parsed, ex)
        row["latency_s"] = round(dt, 1)
        rows.append(row)

        ev = eval_against_text(row, full_text)
        eval_lines += [
            f"### {ex['id']}",
            f"- **PDF**: `{ex['pdf_path']}`",
            f"- **nota**: {ex['note']}",
            f"- **latencia**: {row['latency_s']}s",
            f"- **LLM es_relevante**: {row.get('es_relevante')}",
            f"- **LLM municipio/tipo**: {row.get('municipio')} / {row.get('tipo_instrumento')}",
            f"- **LLM viviendas**: {row.get('num_viviendas_max')}",
            f"- **texto (heurística) viviendas**: {ev['text_viviendas_guess']}",
            f"- **match**: {ev['viviendas_match']}",
            "",
            "**Snippet (texto PDF):**",
            "",
            "```",
            (key_snippets(full_text) or "[sin snippet]").strip(),
            "```",
            "",
        ]

    # CSV
    with CSV_PATH.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["id", "pdf_path", "latency_s"] + list(FIELDS)
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    EVAL_PATH.write_text("\n".join(eval_lines), encoding="utf-8")

    print(f"OK → {CSV_PATH}")
    print(f"OK → {EVAL_PATH}")


if __name__ == "__main__":
    main()

