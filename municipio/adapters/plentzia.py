"""Plentzia's municipal PGOU document inventory (one instrument, many documents)."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://plentziaplanorokorra.eus/"
HOST = urlparse(SOURCE).hostname
LIMITATIONS = [
    "Cobertura parcial: únicamente el PGOU en elaboración del portal de participación.",
    "No incluye otros instrumentos, obras públicas ni licencias concedidas.",
    "Sin fecha de publicación, acuerdo o aprobación verificada; las rutas de subida no son fechas de actos.",
    "Sin geometría vinculada al instrumento; no se infieren coordenadas.",
    "La actualización vuelve a leer el inventario actual; no reconstruye documentos retirados.",
]


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    """Parse the current plan and group all named download links in its inventory.

    Fail on a new pagination mechanism rather than silently accepting page one.
    The template has an empty link to another town: links outside the named local
    file blocks are deliberately not evidence for this instrument.
    """
    if urlparse(url).hostname != HOST:
        raise ValueError("Unexpected PGOU inventory host")
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.select("a[href], link[href]"):
        href = a["href"].strip()
        label = a.get_text(" ", strip=True).casefold()
        rel = a.get("rel", [])
        if href and not href.startswith("#") and (
            "next" in rel
            or label in {"siguiente", "next", "hurrengoa", "cargar más", "ver más"}
            or re.search(r"[?&](?:paged|page|pagina)=\d+|/page/\d+", href)
        ):
            raise ValueError("PGOU inventory pagination requires crawler review")
    if soup.select_one(".pagination, .nav-links, .wp-block-query-pagination, [data-next-page]"):
        raise ValueError("PGOU inventory pagination requires crawler review")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    text = soup.get_text(" ", strip=True)
    if not re.fullmatch(r"PGOU\s+Plentzia", title, re.I) or "Alcalde de Plentzia" not in text:
        raise ValueError("Missing municipal PGOU identity/provenance")
    inventory = soup.select_one("#documentos")
    phases = soup.select_one("#fases")
    if inventory is None or phases is None:
        raise ValueError("Missing PGOU documents or phases section")
    current = phases.select_one(".eb-progressbar-title")
    match = re.fullmatch(r"FASE ACTUAL:\s*(\d+)", current.get_text(" ", strip=True), re.I) if current else None
    if not match:
        raise ValueError("Missing explicit current phase")
    documents = {}
    for block in inventory.select(".wp-block-file"):
        links = block.select("a[href]")
        named = [a for a in links if a.get_text(" ", strip=True) and not a.has_attr("download")
                 and "wp-block-file__button" not in a.get("class", [])]
        if not named:
            raise ValueError("Document block lacks a named source link")
        for a in named:
            target = urldefrag(urljoin(url, a["href"]))[0]
            parsed = urlparse(target)
            if parsed.scheme != "https" or parsed.hostname != HOST or not parsed.path.lower().endswith(".pdf"):
                raise ValueError("Unexpected PGOU document target; review provenance/format")
            documents.setdefault(target, {
                "titulo": a.get_text(" ", strip=True), "url": target,
                "source_url": url + "#documentos", "formato": "application/pdf",
            })
        # Do not silently lose a second download hidden behind a generic label.
        if any(urldefrag(urljoin(url, a["href"]))[0] not in documents for a in links):
            raise ValueError("Unmatched download URL in PGOU document block")
    if not documents:
        raise ValueError("No usable PGOU source documents")
    for a in inventory.select("a[href]"):
        target = urldefrag(urljoin(url, a["href"]))[0]
        if a.get_text(" ", strip=True) and target not in documents:
            raise ValueError("Unrecognised named link in PGOU inventory; review coverage")
    return [{
        "id": "plentzia-pgou", "municipio": "Plentzia", "codigo_ine": "48077",
        "provincia": "Bizkaia", "titulo": title, "tipo": "planeamiento_urbanistico",
        "url": url, "inventory_url": url + "#documentos", "source": "ayuntamiento",
        "origen": "portal_participacion_pgou", "fase": current.get_text(" ", strip=True),
        "source_provenance": "Portal promovido por el Ayuntamiento; presentación firmada por el alcalde; mantenimiento del equipo redactor.",
        "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
        "documentos": list(documents.values()), "geometry_status": "unavailable",
        "publication_ready": False, "coverage": "pgou_en_elaboracion",
        "limitations": list(LIMITATIONS),
    }]


def _write(path: Path, rows: list[dict]) -> dict:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    temp.replace(path)
    return {"count": len(rows), "written": len(rows)}


class PlentziaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        captures = self.config.get("evidence_dir")
        captures = Path(captures) if captures else None
        sources = []

        def fetch(url: str, filename: str, pdf: bool = False):
            response = requests.get(url, timeout=40, headers={
                "User-Agent": "municipio-plentzia/1.0 (public planning inventory)",
            })
            response.raise_for_status()
            if urlparse(response.url).hostname != HOST:
                raise ValueError("Unexpected source redirect")
            if pdf and not response.content.startswith(b"%PDF-"):
                raise ValueError("PGOU download is not a PDF")
            sources.append(response.url)
            if captures:
                captures.mkdir(parents=True, exist_ok=True)
                (captures / filename).write_bytes(response.content)
            return response

        response = fetch(SOURCE, "pgou.html")
        rows = parse_inventory(response.text, response.url)
        for row in rows:
            for doc in row["documentos"]:
                key = hashlib.sha256(doc["url"].encode()).hexdigest()[:16]
                response = fetch(doc["url"], "documento-" + key + ".pdf", pdf=True)
                doc["sha256"] = hashlib.sha256(response.content).hexdigest()
                doc["bytes"] = len(response.content)
        result = _write(out_jsonl, rows)
        return {**result, "source_urls": sources, "limitations": list(LIMITATIONS),
                "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**_write(out_jsonl, []), "disabled": True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
