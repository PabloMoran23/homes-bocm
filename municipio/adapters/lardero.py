"""Lardero's municipal PGM document inventory: one instrument, many documents."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

INVENTORY_URL = "https://www.aytolardero.org/plan-general-municipal/"
HOST = "www.aytolardero.org"
LIMITATIONS = [
    "Cobertura parcial: solo el inventario documental municipal del PGM; no incluye modificaciones o expedientes de otros portales.",
    "La presencia en el inventario no acredita vigencia consolidada ni aprobación; no se extraen fechas de acuerdo o publicación.",
    "Sin geometría verificada; los planos enlazados no se convierten en coordenadas.",
    "Se conservan todos los enlaces documentales; no se comprueba la disponibilidad de cada PDF durante la extracción.",
    "Sin registro verificado de licencias concedidas.",
]


def parse_inventory(html: str, url: str = INVENTORY_URL) -> list[dict]:
    if urlparse(url).hostname != HOST or urlparse(url).path != "/plan-general-municipal/":
        raise ValueError("Unexpected inventory URL")
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one('[data-elementor-type="wp-page"]')
    if content is None or not any(
        h.get_text(" ", strip=True) == "Plan General Municipal" for h in soup.select("h1")
    ):
        raise ValueError("Missing PGM inventory content/title")
    # This inventory is currently a single page. Refuse a changed paginated
    # layout instead of silently treating its first page as complete.
    if soup.select('a[rel~="next"], link[rel~="next"], .pagination, .page-numbers, .nav-links, .elementor-pagination, .post-page-numbers'):
        raise ValueError("Pagination detected; inventory coverage must be reviewed")
    documents = {}
    for a in content.select("a[href]"):
        target = urljoin(url, a["href"])
        parsed = urlparse(target)
        if parsed.hostname != HOST or not parsed.path.startswith("/Descargar/"):
            continue
        title = a.get_text(" ", strip=True)
        if not title or not re.fullmatch(r"/Descargar/\d+/[^/]+/\d+/[^/]+\.pdf", parsed.path, re.I):
            raise ValueError("Unrecognized PGM document link")
        # Category slug comes from the official download URL and disambiguates
        # repeated labels (e.g. SP-1 appears in two source sections).
        section = parsed.path.split("/")[3]
        documents.setdefault(target, {
            "titulo": title, "url": target, "seccion_fuente": section,
            "source_url": url,
        })
    if not documents:
        raise ValueError("No PGM documents found")
    return [{
        "id": "lardero-pgm", "municipio": "Lardero", "codigo_ine": "26084",
        "provincia": "La Rioja", "titulo": "Plan General Municipal de Lardero",
        "tipo": "instrumento de planeamiento general", "url": url,
        "inventory_url": url, "source": "ayuntamiento",
        "origen": "inventario_documental_pgm", "documentos": list(documents.values()),
        "coverage": "partial_municipal_pgm_inventory",
        "limitations": LIMITATIONS.copy(), "publication_ready": False,
        "geometry_status": "unavailable",
    }]


class LarderoAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(INVENTORY_URL, timeout=45, headers={
            "User-Agent": "municipio-lardero/1.0 (public planning inventory)",
        })
        response.raise_for_status()
        rows = parse_inventory(response.text, response.url)
        capture_dir = self.config.get("capture_dir")
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "pgm-live.html").write_text(response.text, encoding="utf-8")
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        return {
            "count": len(rows), "written": len(rows),
            "document_links": sum(len(r["documentos"]) for r in rows),
            "source_urls": [response.url], "limitations": LIMITATIONS.copy(),
            "coverage": "partial_municipal_pgm_inventory", "publication_ready": False,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the complete current inventory; never claim an incremental history.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"count": 0, "written": 0, "disabled": True,
                "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
