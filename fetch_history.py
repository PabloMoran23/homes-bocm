"""
BOCM Historical Fetcher — descarga todos los PDFs de urbanismo del BOCM desde 2010.

Estrategia:
  - Itera cada día hábil desde 2010-02-12 (primera edición digital) hasta hoy.
  - Para cada fecha, descarga la página HTML del boletín y extrae los artículos
    de Sección III (Administración Local) / Urbanismo y Licencias.
  - También captura Sección I-C y I-D con palabras clave urbanísticas
    (modificaciones de PGOU, aprobaciones de la Comisión de Urbanismo CM).
  - Descarga los PDFs con rate limiting educado.
  - Guarda un índice JSON incremental para poder reanudar en cualquier punto.

Uso:
  python3 fetch_history.py                  # desde 2010 hasta hoy
  python3 fetch_history.py --from 2023-01-01  # desde fecha concreta
  python3 fetch_history.py --from 2023-01-01 --to 2024-12-31
"""

import argparse
import json
import re
import time
import sys
from datetime import date, timedelta
from pathlib import Path

import httpx
from bs4 import BeautifulSoup


_YEAR_OFFSET_CACHE: dict[int, int] = {
    2024: 1,   # Jan 1 = lunes → solo se salta Jan 1
    2025: 1,   # Jan 1 = miercoles → solo se salta Jan 1
    2026: 2,   # Jan 1 = jueves → se saltan Jan 1 y Jan 2
}

def _non_sundays_up_to(d: date) -> int:
    start = date(d.year, 1, 1)
    return sum(1 for i in range((d - start).days + 1)
               if (start + timedelta(i)).weekday() != 6)


def _discover_year_offset(year: int) -> int:
    """Descubre el offset del año probando Jan 3 (siempre existe si el año tiene boletines)."""
    d = date(year, 1, 3)
    base = _non_sundays_up_to(d)
    for offset in range(0, 5):
        num = base - offset
        if num < 1:
            continue
        url = f"{BOCM_BASE}/boletin-completo/BOCM-{d.strftime('%Y%m%d')}/{num}"
        try:
            r = httpx.get(url, headers=HEADERS, timeout=10, follow_redirects=True)
            if r.status_code == 200:
                _YEAR_OFFSET_CACHE[year] = offset
                return offset
        except Exception:
            pass
    return 2  # fallback conservador


def boletin_num(d: date) -> int:
    """
    Número de boletín del BOCM para la fecha d.
    El BOCM publica todos los días excepto domingo.
    El offset (días sin publicar al inicio del año) varía según el año.
    """
    year = d.year
    if year not in _YEAR_OFFSET_CACHE:
        _YEAR_OFFSET_CACHE[year] = _discover_year_offset(year)
    offset = _YEAR_OFFSET_CACHE[year]
    return _non_sundays_up_to(d) - offset

BOCM_BASE   = "https://www.bocm.es"
PDF_DIR     = Path("pdfs_history")
STATE_FILE  = Path("output/history_state.json")   # progreso incremental
INDEX_FILE  = Path("output/history_index.jsonl")  # un JSON por línea

PDF_DIR.mkdir(exist_ok=True)
Path("output").mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; BOCM-research/1.0)"}

# Delay entre peticiones (segundos) — educado con el servidor público
DELAY_BETWEEN_PAGES = 1.0
DELAY_BETWEEN_PDFS  = 0.5

# Palabras clave en el título del artículo para considerarlo relevante
URBANISMO_KEYWORDS = [
    "urbanismo", "plan parcial", "plan especial", "plan general",
    "planeamiento", "urbanización", "proyecto de urban",
    "normas subsidiarias", "estudio de detalle", "reparcelación",
    "compensación", "pgou", "modificación puntual", "área de planeamiento",
    "ensanche", "sector", "iniciativa urban", "comisión gestora",
    "vivienda", "edificación", "licencia de obra", "declaración responsable",
]

# Secciones/apartados del BOCM que nos interesan
RELEVANT_SECTIONS = [
    "iii.",           # Administración Local (contiene Urbanismo, Licencias)
    "v. otros",       # Otros anuncios (comisiones gestoras, etc.)
    "i. comunidad",   # Solo si aparece "urbanismo" en el texto
]


def fetch(url: str, retries: int = 3) -> httpx.Response | None:
    for attempt in range(retries):
        try:
            r = httpx.get(url, headers=HEADERS, timeout=30, follow_redirects=True)
            r.raise_for_status()
            return r
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None  # Boletín no publicado ese día
            print(f"  [warn] HTTP {e.response.status_code} en {url}", flush=True)
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"  [warn] intento {attempt+1} fallido: {e}", flush=True)
            time.sleep(2 ** attempt)
    return None


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"processed_dates": [], "total_pdfs": 0, "last_date": None}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def is_relevant(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in URBANISMO_KEYWORDS)


def get_articles_for_date(d: date) -> list[dict]:
    """
    Descarga la página del boletín de una fecha y extrae artículos relevantes.
    Estructura HTML real del BOCM: cada artículo está en un div.views-row que
    empieza con el número, seguido del título y links (PDF, HTML, epub, XML, JSON).
    """
    date_str    = d.strftime("%Y%m%d")
    num         = boletin_num(d)
    if num <= 0:
        return []  # primeros días del año sin boletín
    boletin_url = f"{BOCM_BASE}/boletin-completo/BOCM-{date_str}/{num}"

    r = fetch(boletin_url)
    if not r:
        return []  # no publicado ese día (finde, festivo, etc.)

    soup = BeautifulSoup(r.text, "lxml")
    articles = []

    for row in soup.find_all("div", class_=re.compile(r"views-row")):
        row_text = row.get_text(" ", strip=True)

        # Número al inicio del row
        m = re.match(r"^(\d+)\s+(.*)", row_text, re.DOTALL)
        if not m:
            continue

        art_num   = m.group(1)
        art_title = re.split(r"Descargar|pdf\s+HTML", m.group(2))[0].strip()
        art_title = re.sub(r"^[–\-•\s]+", "", art_title).strip()

        if not is_relevant(art_title):
            continue

        # El PDF está directamente como link en el row
        pdf_link = row.find("a", href=re.compile(r"\.PDF$", re.I))
        pdf_url  = pdf_link["href"] if pdf_link else (
            f"{BOCM_BASE}/boletin/CM_Orden_BOCM/{d.year}/{d.month:02d}/{d.day:02d}/BOCM-{date_str}-{art_num}.PDF"
        )

        articles.append({
            "date":        d.isoformat(),
            "art_num":     art_num,
            "title":       art_title,
            "pdf_url":     pdf_url,
            "article_url": f"{BOCM_BASE}/bocm-{date_str.lower()}-{art_num}",
        })

    return articles


def download_pdf(pdf_url: str, out_path: Path) -> bool:
    if out_path.exists() and out_path.stat().st_size > 1000:
        return True  # ya descargado
    r = fetch(pdf_url)
    if not r or len(r.content) < 500:
        return False
    out_path.write_bytes(r.content)
    return True


def date_range(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", default="2010-02-12")
    parser.add_argument("--to",   dest="date_to",   default=date.today().isoformat())
    args = parser.parse_args()

    start = date.fromisoformat(args.date_from)
    end   = date.fromisoformat(args.date_to)

    state = load_state()
    processed = set(state["processed_dates"])

    total_days  = (end - start).days + 1
    total_pdfs  = state["total_pdfs"]

    print(f"=== BOCM Historical Fetcher ===", flush=True)
    print(f"Rango: {start} → {end}  ({total_days} días)", flush=True)
    print(f"Ya procesados: {len(processed)} días | PDFs acumulados: {total_pdfs}", flush=True)
    print(f"PDFs en: {PDF_DIR}/\n", flush=True)

    index_fh = INDEX_FILE.open("a", encoding="utf-8")

    try:
        for i, d in enumerate(date_range(start, end)):
            d_str = d.isoformat()
            if d_str in processed:
                continue

            # El BOCM no publica los domingos
            if d.weekday() == 6:
                processed.add(d_str)
                continue

            articles = get_articles_for_date(d)

            if articles:
                print(f"[{d_str}]  {len(articles)} artículos relevantes", flush=True)
                for art in articles:
                    year_dir = PDF_DIR / str(d.year)
                    year_dir.mkdir(exist_ok=True)
                    fname    = f"BOCM-{d.strftime('%Y%m%d')}-{art['art_num']}.pdf"
                    out_path = year_dir / fname

                    ok = download_pdf(art["pdf_url"], out_path)
                    status = "ok" if ok else "err"
                    if ok:
                        total_pdfs += 1
                        art["pdf_path"] = str(out_path)
                    print(f"  [{status}] {fname}  ({art['title'][:60]})", flush=True)
                    index_fh.write(json.dumps(art, ensure_ascii=False) + "\n")
                    index_fh.flush()
                    time.sleep(DELAY_BETWEEN_PDFS)
            else:
                # Sin artículos relevantes — loguear solo cada 20 días para no spamear
                if i % 20 == 0:
                    print(f"[{d_str}]  sin artículos relevantes", flush=True)

            processed.add(d_str)
            state["processed_dates"] = list(processed)
            state["total_pdfs"]      = total_pdfs
            state["last_date"]       = d_str
            save_state(state)
            time.sleep(DELAY_BETWEEN_PAGES)

    except KeyboardInterrupt:
        print("\n[interrumpido] progreso guardado, puedes reanudar ejecutando de nuevo.", flush=True)
    finally:
        index_fh.close()
        save_state(state)

    print(f"\n=== Completado: {total_pdfs} PDFs descargados ===", flush=True)


if __name__ == "__main__":
    main()
