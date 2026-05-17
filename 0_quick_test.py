"""
Quick test — descarga directamente algunos PDFs de urbanismo conocidos
del BOCM para probar el pipeline sin esperar al collector completo.

Usa artículos reales de boletines recientes con contenido urbanístico.
"""

import subprocess
import time
from pathlib import Path

import httpx

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BOCM-POC/1.0; research)"}
PDF_DIR = Path("pdfs")
PDF_DIR.mkdir(exist_ok=True)

# PDFs de urbanismo conocidos del BOCM (artículos reales verificados)
# Formato: (nombre_descriptivo, url_pdf)
SAMPLE_PDFS = [
    # Art. 81 - Plan especial - Madrid capital (2026-05-04, Sección III/Urbanismo)
    ("bocm-20260504-81-plan-especial-madrid",
     "https://www.bocm.es/boletin/CM_Orden_BOCM/2026/05/04/BOCM-20260504-81.PDF"),
    # Art. 82 - Estudio de detalle - Madrid capital (2026-05-04)
    ("bocm-20260504-82-estudio-detalle-madrid",
     "https://www.bocm.es/boletin/CM_Orden_BOCM/2026/05/04/BOCM-20260504-82.PDF"),
    # Art. 109 - Normas subsidiarias - Valdemaqueda (2026-05-04)
    ("bocm-20260504-109-normas-subsidiarias-valdemaqueda",
     "https://www.bocm.es/boletin/CM_Orden_BOCM/2026/05/04/BOCM-20260504-109.PDF"),
    # Art. 115 - Proyecto urbanización - Villanueva del Pardillo (2026-05-04)
    ("bocm-20260504-115-proy-urban-villanueva-pardillo",
     "https://www.bocm.es/boletin/CM_Orden_BOCM/2026/05/04/BOCM-20260504-115.PDF"),
    # Art. 118 - SR-6 Ensanche Sureste - Iniciativa urbanismo (2026-05-04, Sección V)
    ("bocm-20260504-118-sr6-ensanche-sureste",
     "https://www.bocm.es/boletin/CM_Orden_BOCM/2026/05/04/BOCM-20260504-118.PDF"),
    # Plan parcial - Alcalá de Henares 2020
    ("bocm-20200113-plan-parcial-alcala",
     "https://www.bocm.es/boletin/CM_Orden_BOCM/2020/01/13/BOCM-20200113-25.PDF"),
    # Plan parcial - Villalbilla 2022 (extenso, buen test)
    ("bocm-20221028-plan-parcial-villalbilla",
     "https://www.bocm.es/boletin/CM_Orden_BOCM/2022/10/28/BOCM-20221028-104.PDF"),
]


def download(url: str, out_path: Path) -> bool:
    if out_path.exists():
        print(f"  [skip] ya existe: {out_path.name}")
        return True
    try:
        r = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
        r.raise_for_status()
        out_path.write_bytes(r.content)
        print(f"  [ok]  {out_path.name}  ({len(r.content)//1024} KB)")
        return True
    except Exception as e:
        print(f"  [err] {url}: {e}")
        return False


def extract_text(pdf_path: Path) -> str:
    result = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        capture_output=True, text=True, encoding="utf-8",
    )
    return result.stdout.strip()


def main():
    print("=== Quick Test: descargando PDFs de muestra ===\n")

    ok = 0
    for name, url in SAMPLE_PDFS:
        print(f"→ {name}")
        out = PDF_DIR / f"{name}.pdf"
        if download(url, out):
            ok += 1
        time.sleep(0.5)

    print(f"\n{ok}/{len(SAMPLE_PDFS)} PDFs descargados en {PDF_DIR}/\n")

    # Vista previa del texto de cada PDF
    print("=== Preview de texto extraído ===\n")
    for pdf_path in sorted(PDF_DIR.glob("*.pdf")):
        text = extract_text(pdf_path)
        lines = [l for l in text.splitlines() if l.strip()]
        preview = "\n".join(lines[:8])
        print(f"--- {pdf_path.name} ({len(text)} chars) ---")
        print(preview)
        print()

    print("Ahora ejecuta:  python3 2_extract_text.py")
    print("Luego:          OPENAI_API_KEY=sk-... python3 3_llm_parse.py")


if __name__ == "__main__":
    main()
