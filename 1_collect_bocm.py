"""
BOCM Collector — descarga PDFs de artículos de Urbanismo del BOCM.

Estrategia:
  1. Lee el RSS de sumarios (últimos 20 boletines) para obtener fechas y URLs.
  2. Para cada boletín, descarga la página HTML del boletín completo.
  3. Filtra los artículos de la Sección III (Administración Local) / Urbanismo.
  4. Descarga el PDF de cada artículo relevante.
"""

import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BOCM_BASE = "https://www.bocm.es"
SUMARIOS_RSS = "https://www.bocm.es/sumarios.rss"
PDF_DIR = Path("pdfs")
PDF_DIR.mkdir(exist_ok=True)

# Palabras clave para filtrar artículos relevantes (urbanismo / vivienda)
KEYWORDS = [
    "urbanismo", "plan parcial", "plan especial", "plan general",
    "proyecto de urbanización", "estudio de detalle", "normas subsidiarias",
    "modificación", "reparcelación", "compensación", "vivienda",
    "sector", "pgou",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BOCM-POC/1.0; research)"
}


def fetch(url: str, retries: int = 3) -> httpx.Response | None:
    for attempt in range(retries):
        try:
            r = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as e:
            print(f"  [warn] intento {attempt+1}/{retries} fallido para {url}: {e}")
            time.sleep(2 ** attempt)
    return None


def parse_sumarios_rss() -> list[dict]:
    """Devuelve lista de {date, boletín_url} de los últimos 20 boletines."""
    r = fetch(SUMARIOS_RSS)
    if not r:
        raise RuntimeError("No se pudo descargar el RSS de sumarios")

    root = ET.fromstring(r.text)
    items = []
    for item in root.findall(".//item"):
        title = item.findtext("title", "")
        link = item.findtext("link", "")
        # título: "Boletín Nº 104 del 04 Mayo 2026"
        match = re.search(r"Nº\s*(\d+).*?(\d{2})\s+(\w+)\s+(\d{4})", title)
        date_str = match.group(0) if match else title
        items.append({"title": title, "url": link, "date": date_str})
    return items


def get_article_links_from_boletin(boletin_url: str) -> list[dict]:
    """
    Dado el URL de un boletín completo, devuelve todos los artículos de
    Sección III / Urbanismo o Licencias.
    """
    r = fetch(boletin_url)
    if not r:
        return []

    soup = BeautifulSoup(r.text, "lxml")
    articles = []

    # La página del boletín lista artículos con sus títulos y enlaces
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        text = a_tag.get_text(" ", strip=True).lower()

        # Filtrar por keywords urbanísticas
        if any(kw in text for kw in KEYWORDS):
            full_url = urljoin(BOCM_BASE, href) if not href.startswith("http") else href
            # Sólo páginas de artículo (no PDFs todavía)
            if "/bocm-" in href and not href.endswith(".PDF") and not href.endswith(".epub"):
                articles.append({
                    "title": a_tag.get_text(" ", strip=True),
                    "url": full_url,
                    "source_boletin": boletin_url,
                })

    # Deduplicar por URL
    seen = set()
    unique = []
    for art in articles:
        if art["url"] not in seen:
            seen.add(art["url"])
            unique.append(art)
    return unique


def get_pdf_url_from_article(article_url: str) -> str | None:
    """Dado el URL de un artículo, encuentra el enlace al PDF."""
    r = fetch(article_url)
    if not r:
        return None
    soup = BeautifulSoup(r.text, "lxml")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.upper().endswith(".PDF"):
            return urljoin(BOCM_BASE, href) if not href.startswith("http") else href
    return None


def download_pdf(pdf_url: str, out_path: Path) -> bool:
    """Descarga un PDF y lo guarda en out_path. Devuelve True si ok."""
    if out_path.exists():
        print(f"  [skip] ya existe: {out_path.name}")
        return True
    r = fetch(pdf_url)
    if not r:
        return False
    out_path.write_bytes(r.content)
    print(f"  [ok] {out_path.name} ({len(r.content)//1024} KB)")
    return True


def main():
    print("=== BOCM Collector ===\n")

    print("1. Leyendo RSS de sumarios...")
    boletines = parse_sumarios_rss()
    print(f"   {len(boletines)} boletines encontrados\n")

    all_articles = []
    for boletin in boletines:
        print(f"2. Buscando artículos en: {boletin['title']}")
        articles = get_article_links_from_boletin(boletin["url"])
        print(f"   → {len(articles)} artículos de urbanismo")
        for art in articles:
            art["boletin_date"] = boletin["date"]
        all_articles.extend(articles)
        time.sleep(0.5)  # cortés con el servidor

    print(f"\n   Total artículos a procesar: {len(all_articles)}\n")

    downloaded = 0
    for i, art in enumerate(all_articles):
        print(f"3. [{i+1}/{len(all_articles)}] {art['title'][:80]}")
        pdf_url = get_pdf_url_from_article(art["url"])
        if not pdf_url:
            print("   [warn] no se encontró PDF")
            continue

        # Nombre del fichero: bocm-YYYYMMDD-N.pdf
        slug = re.sub(r"[^a-z0-9\-]", "", pdf_url.split("/")[-1].lower().replace(".pdf", ""))
        out_path = PDF_DIR / f"{slug}.pdf"
        download_pdf(pdf_url, out_path)
        art["pdf_path"] = str(out_path)
        art["pdf_url"] = pdf_url
        time.sleep(0.3)

    print(f"\n=== Descarga completada: {downloaded} PDFs en {PDF_DIR}/ ===")


if __name__ == "__main__":
    main()
