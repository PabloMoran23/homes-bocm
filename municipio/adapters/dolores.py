"""Snapshot of the PGOU document inventory published by Dolores (Alicante)."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://www.dolores.es/el-ayuntamiento/departamentos-municipales/urbanismo/"
LIMITATIONS = [
    "Cobertura parcial: únicamente el PGOU enlazado en Urbanismo; no inventario histórico de expedientes u obras.",
    "La publicación documental no acredita vigencia, aprobación ni ejecución; fechas no verificadas.",
    "Sin geometría verificada ni registro de licencias concedidas.",
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article .entry-content")
    if article is None:
        raise ValueError("Missing municipal content container")
    # A changed/paginated inventory must be reviewed rather than silently cut off.
    if soup.select('a[rel~=next], link[rel~=next]') or article.select(
        '.pagination, .page-numbers, .nav-links, .wp-pagenavi'
    ):
        raise ValueError("Unexpected pagination in the single-page PGOU inventory")
    headings = [h for h in article.find_all("h2") if h.get_text(strip=True) == "PGOU"]
    if len(headings) != 1:
        raise ValueError("Expected one PGOU inventory")
    block = headings[0].find_parent("div", class_="et_pb_text_inner")
    if block is None or len(block.find_all("h2")) != 1:
        raise ValueError("Ambiguous PGOU document grouping")
    documents = []
    numbers = []
    complete = None
    seen = set()
    for anchor in block.select("a[href]"):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        url = urljoin(source_url, anchor["href"])
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != "www.dolores.es":
            raise ValueError("Unexpected document origin")
        if not parsed.path.lower().endswith((".pdf", ".zip")):
            raise ValueError("Unexpected PGOU document format")
        if url in seen:
            continue
        seen.add(url)
        if "PLAN GENERAL DE ORDENACIÓN URBANA" in title and "Descarga Completa" in title:
            if complete is not None:
                raise ValueError("Multiple complete PGOU packages")
            complete = url
        else:
            match = re.match(r"^(\d+)\.\s*\S", title)
            if not match:
                raise ValueError("Unidentified document in PGOU inventory")
            numbers.append(int(match[1]))
        documents.append({"titulo": title, "url": url, "source_url": source_url})
    # Require substantive plan documents, not just a heading, form or index.
    titles = [d["titulo"] for d in documents]
    if (not complete or len(numbers) < 3 or sorted(numbers) != list(range(1, max(numbers) + 1))
            or not any(re.fullmatch(r"\d+\. MEMORIA", t) for t in titles)
            or not any(re.fullmatch(r"\d+\. NORMATIVA", t) for t in titles)):
        raise ValueError("Incomplete or unusable PGOU inventory")
    return [{
        "id": "dolores-pgou", "municipio": "Dolores", "codigo_ine": "03064",
        "provincia": "Alicante", "titulo": "Plan General de Ordenación Urbana de Dolores (PGOU)",
        "tipo": "PGOU", "source": "ayuntamiento", "origen": "inventario_planeamiento",
        "url": source_url, "url_documento": complete, "documentos": documents,
        "descripcion": "Instrumento agrupado según la sección PGOU del inventario municipal de Urbanismo.",
        "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None,
        "fecha_aprob": None, "fase": None,
        "lat": None, "lon": None, "geometry": None,
        "geometry_status": "unavailable", "publication_ready": False,
        "coverage": "partial_current_document_inventory", "limitations": LIMITATIONS.copy(),
    }]


class DoloresAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug="dolores", config=None, base_url=""):
        super().__init__(slug, config, base_url or SOURCE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            "User-Agent": "municipio-dolores/1.0 (public planning inventory)"
        })
        response.raise_for_status()
        if response.url != SOURCE:
            raise ValueError("Unexpected municipal inventory redirect")
        rows = parse_inventory(response.text, response.url)
        if self.config.get("evidence_dir"):
            evidence = Path(self.config["evidence_dir"])
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / "urbanismo.html").write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        return {"count": len(rows), "written": len(rows), "source_urls": [SOURCE],
                "coverage": "partial_current_document_inventory", "limitations": LIMITATIONS.copy()}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete snapshot of this unpaginated document page; no date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"count": 0, "disabled": True, "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
