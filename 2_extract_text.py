"""
BOCM Text Extractor — convierte los PDFs descargados a texto limpio.

Usa pdftotext (poppler) como primera opción por calidad.
Guarda el texto en output/<nombre>.txt y un resumen en output/index.json.
"""

import json
import subprocess
from pathlib import Path

PDF_DIR = Path("pdfs")
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
INDEX_FILE = OUTPUT_DIR / "index.json"


def pdf_to_text_pdftotext(pdf_path: Path) -> str:
    """Extrae texto con pdftotext (poppler). Mejor para PDFs de texto."""
    result = subprocess.run(
        ["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def clean_text(raw: str) -> str:
    """Limpieza básica: elimina líneas vacías consecutivas, normaliza espacios."""
    lines = raw.splitlines()
    cleaned = []
    blank_count = 0
    for line in lines:
        stripped = line.strip()
        if not stripped:
            blank_count += 1
            if blank_count <= 1:
                cleaned.append("")
        else:
            blank_count = 0
            cleaned.append(stripped)
    return "\n".join(cleaned).strip()


def count_pages(pdf_path: Path) -> int:
    result = subprocess.run(
        ["pdfinfo", str(pdf_path)],
        capture_output=True, text=True
    )
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            return int(line.split(":")[1].strip())
    return 0


def main():
    pdfs = sorted(PDF_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No hay PDFs en {PDF_DIR}/. Ejecuta primero 1_collect_bocm.py")
        return

    print(f"=== BOCM Text Extractor ===")
    print(f"PDFs encontrados: {len(pdfs)}\n")

    index = []

    for i, pdf_path in enumerate(pdfs):
        print(f"[{i+1}/{len(pdfs)}] {pdf_path.name}")

        text = pdf_to_text_pdftotext(pdf_path)
        text = clean_text(text)

        if len(text) < 100:
            print(f"  [warn] texto muy corto ({len(text)} chars), puede ser PDF escaneado")

        # Guardar texto
        txt_path = OUTPUT_DIR / (pdf_path.stem + ".txt")
        txt_path.write_text(text, encoding="utf-8")

        # Preview de las primeras líneas
        preview = "\n".join(text.splitlines()[:5])
        print(f"  chars: {len(text)} | páginas: {count_pages(pdf_path)}")
        print(f"  preview: {preview[:200]}\n")

        index.append({
            "pdf": str(pdf_path),
            "txt": str(txt_path),
            "chars": len(text),
            "pages": count_pages(pdf_path),
            "preview": text[:300],
        })

    INDEX_FILE.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== Extracción completada. Índice en {INDEX_FILE} ===")


if __name__ == "__main__":
    main()
