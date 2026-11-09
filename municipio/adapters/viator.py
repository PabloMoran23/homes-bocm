"""Viator's municipal planning document inventory (partial historical coverage)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://ayuntamientoviator.es/category/normativa/"
HOST = "ayuntamientoviator.es"
LIMITATIONS = [
    "Only the municipal Normativa urbanística category; not a complete planning register or works inventory.",
    "Historical documents currently linked by the website; legal validity and subsequent amendments are not established.",
    "CMS publication dates are not agreement or approval dates; no inferred approval dates or coordinates.",
    "Document links are retained; availability and contents of every PDF are not verified by the adapter.",
    "No granted-licence register extracted; licences disabled.",
]


def official_url(base: str, href: str) -> str:
    url = urldefrag(urljoin(base, href))[0]
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in {HOST, "www." + HOST}:
        raise ValueError(f"Unexpected municipal source URL: {url}")
    return url


def parse_inventory(html: str, url: str = SOURCE) -> tuple[list[dict], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    articles = soup.select("article.category-normativa")
    if not articles:
        raise ValueError("Missing municipal planning inventory articles")
    entries = {}
    for article in articles:
        anchor = article.select_one("h2 a[href]")
        if not anchor:
            raise ValueError("Planning inventory article missing title link")
        title = anchor.get_text(" ", strip=True)
        # Instruments, never licence forms, tax ordinances or general news.
        if not re.match(r"^(?:NN\.SS\.|Normas Subsidiarias|Adaptación parcial|Plan General|Plan Parcial|Plan Especial|Estudio de Detalle|Modificación (?:puntual|del))(?=\s|$)", title, re.I):
            continue
        target = official_url(url, anchor["href"])
        entries[target] = {"titulo": title, "url": target, "inventory_url": url}
    pages = set()
    for anchor in soup.select(".pagination a[href], .page-numbers[href], .navigation a[href], a[rel~=next], link[rel~=next]"):
        target = official_url(url, anchor["href"])
        if not urlparse(target).path.startswith("/category/normativa/"):
            raise ValueError("Unrecognised inventory pagination")
        if target != url:
            pages.add(target)
    return list(entries.values()), sorted(pages)


def parse_instrument(html: str, entry: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("article .single-entry-summary")
    heading = soup.select_one("h1.single-title")
    if content is None or heading is None or heading.get_text(" ", strip=True) != entry["titulo"]:
        raise ValueError("Unexpected planning document page")
    if content.select(".page-links a[href]") or soup.select(".page-links a[href]"):
        raise ValueError("Multipage instrument requires explicit traversal")
    documents = {}
    for anchor in content.select("a[href]"):
        target = urljoin(entry["url"], anchor["href"])
        if not urlparse(target).path.lower().endswith(".pdf"):
            continue
        target = official_url(entry["url"], anchor["href"])
        documents.setdefault(target, {"titulo": anchor.get_text(" ", strip=True),
                                      "url": target, "source_url": entry["url"]})
    if not documents:
        raise ValueError("Instrument has no linked planning documents")
    record = {
        **entry,
        "id": "viator-plan-" + hashlib.sha256(entry["url"].encode()).hexdigest()[:16],
        "municipio": "Viator", "codigo_ine": "04101", "provincia": "Almería",
        "tipo": "planeamiento_urbanistico", "source": "ayuntamiento",
        "origen": "inventario_normativa_urbanistica", "documentos": list(documents.values()),
        "publication_ready": False, "geometry_status": "unavailable",
        "coverage": "partial_historical_document_inventory",
    }
    parts = [content.select_one(".posted-date-" + p) for p in ("year", "month", "day")]
    if any(parts):
        if not all(parts):
            raise ValueError("Incomplete CMS publication date")
        year, month, day = [p.get_text(strip=True) for p in parts]
        months = {m: i for i, m in enumerate(
            ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"), 1)}
        record["fecha_publicacion"] = date(int(year), months[month.lower().rstrip(".")], int(day)).isoformat()
    return record


class ViatorAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        sources = []
        capture_dir = self.config.get("evidence_dir")

        def fetch(url):
            response = requests.get(url, timeout=40, headers={"User-Agent": "municipal-planning-inventory/1.0"})
            response.raise_for_status()
            official_url(url, response.url)
            if urlparse(response.url).path != urlparse(url).path:
                raise ValueError("Unexpected source redirect")
            sources.append(response.url)
            if capture_dir:
                path = Path(capture_dir)
                path.mkdir(parents=True, exist_ok=True)
                (path / (hashlib.sha256(url.encode()).hexdigest()[:16] + ".html")).write_text(response.text, encoding="utf-8")
            return response.text

        pending, visited, entries = [SOURCE], set(), {}
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            visited.add(url)
            found, pages = parse_inventory(fetch(url), url)
            entries.update((entry["url"], entry) for entry in found)
            pending.extend(page for page in pages if page not in visited)
        if not entries:
            raise ValueError("No supported planning instruments found")
        rows = [parse_instrument(fetch(url), entry) for url, entry in entries.items()]
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "source_urls": sources,
                "inventory_pages": len(visited), "limitations": LIMITATIONS}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # A complete inventory refresh; no date watermark can hide older documents.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
