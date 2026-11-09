"""Documented planning instruments from two official municipal inventories.

One instrument per record, including all its linked PDFs. Not a licence register
or an assertion that the instruments are currently in force.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.aielodemalferit.es"
PGOU_URL = BASE + "/va/ajuntament/ajuntament/pgou-aielo"
ACTUACIONES_URL = BASE + "/va/ajuntament/ajuntament/actuacions-urbanistiques"
SOURCE_URLS = (PGOU_URL, ACTUACIONES_URL)
HOSTS = {"www.aielodemalferit.es", "aielodemalferit.es"}
LIMITATIONS = [
    "Cobertura parcial: solo PDF enlazados en PGOU y actuaciones urbanísticas.",
    "No incluye el iframe de sede electrónica, DOGV, proyectos e inversiones, "
    "planes de movilidad/emergencias, noticias ni un histórico completo.",
    "El inventario municipal no garantiza vigencia ni recoge todas las modificaciones posteriores.",
    "Fechas de las etiquetas conservadas literalmente; no se interpretan como publicación o acuerdo.",
    "Sin fechas de aprobación verificadas, coordenadas ni licencias concedidas.",
]


def _soup(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one("#preview .box .contenido"):
        raise ValueError("Missing municipal document inventory")
    # These inventories are single HTML pages. Refuse a newly paginated layout
    # until it can be followed completely, instead of returning its first page.
    if soup.select('[rel~=next], .pagination, .paginacion, .paginador, .pager'):
        raise ValueError("Pagination detected: coverage must be reviewed")
    for a in soup.select("a[href]"):
        if re.search(r"[?&](?:page|pagina|offset|start)=", a["href"], re.I):
            raise ValueError("Pagination link detected")
    return soup


def _document(a, url: str, section: str) -> dict | None:
    original = urljoin(url, a["href"])
    parts = urlsplit(original)
    if not parts.path.lower().endswith(".pdf"):
        return None
    if parts.hostname not in HOSTS or not parts.path.startswith("/files/"):
        raise ValueError("Unexpected document origin: " + original)
    # The CMS still emits HTTP links. Keep them as provenance, but use HTTPS.
    target = urlunsplit(("https", parts.netloc, parts.path, parts.query, ""))
    label = a.get_text(" ", strip=True)
    return {
        "url": target,
        "source_url": original,
        "titulo": label or unquote(parts.path.rsplit("/", 1)[-1]),
        "titulo_origen": "anchor_text" if label else "filename",
        "seccion": section,
        "inventory_url": url,
    }


def _record(title: str, url: str, docs: list[dict]) -> dict:
    unique = {doc["url"]: doc for doc in docs}
    if not unique:
        raise ValueError("Instrument without linked documents: " + title)
    key = hashlib.sha256((url + "|" + title.casefold()).encode()).hexdigest()[:20]
    return {
        "id": "aielo-de-malferit-plan-" + key,
        "municipio": "Aielo de Malferit",
        "codigo_ine": "46042",
        "provincia": "Valencia",
        "titulo": title,
        "tipo": "instrumento de planeamiento o actuación urbanística",
        "url": url,
        "inventory_url": url,
        "source": "ayuntamiento",
        "origen": "inventario_documental_urbanismo",
        "documentos": list(unique.values()),
        "publication_ready": False,
        "geometry_status": "unavailable",
    }


def parse_pgou(html: str, url: str = PGOU_URL) -> list[dict]:
    soup = _soup(html)
    title_node = next((n for n in soup.select("#preview strong")
                       if n.get_text(" ", strip=True).startswith("Pla General d'Ordenació Urbana")), None)
    if title_node is None:
        raise ValueError("Missing PGOU instrument name")
    base_title = title_node.get_text(" ", strip=True)
    groups: dict[str, list[dict]] = {base_title: []}
    found = False
    for box in soup.select("#preview .box"):
        heading = box.find("h3")
        if heading is None or not heading.get_text(" ", strip=True).upper().startswith("DOCUMENTS DESCARREGABLES"):
            continue
        found = True
        current = base_title
        content = box.select_one(".contenido")
        if content is None:
            raise ValueError("Missing PGOU documents container")
        for node in content.find_all(["h3", "a"]):
            if node.name == "h3":
                current = node.get_text(" ", strip=True)
                if not re.match(r"MODIFICACIÓ\s+\d+\s+PGOU\b", current, re.I):
                    raise ValueError("Unknown PGOU document grouping: " + current)
                groups.setdefault(current, [])
            elif node.has_attr("href"):
                doc = _document(node, url, current)
                if doc:
                    groups[current].append(doc)
    if not found:
        raise ValueError("Missing PGOU downloadable inventory")
    return [_record(title, url, docs) for title, docs in groups.items()]


def parse_actuaciones(html: str, url: str = ACTUACIONES_URL) -> list[dict]:
    soup = _soup(html)
    rows = []
    for box in soup.select("#preview .box"):
        heading = box.find("h3")
        title = heading.get_text(" ", strip=True) if heading else ""
        if not re.match(r"Programa actuació aïllada\s+\S", title, re.I):
            continue
        content = box.select_one(".contenido")
        if content is None:
            raise ValueError("Missing programme documents container")
        section = title
        docs = []
        for node in content.find_all(["h2", "a"]):
            if node.name == "h2":
                section = node.get_text(" ", strip=True) or section
            elif node.has_attr("href"):
                doc = _document(node, url, section)
                if doc:
                    docs.append(doc)
        rows.append(_record(title, url, docs))
    if not rows:
        raise ValueError("No named isolated action programmes found")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate programme identity")
    return rows


class AieloDeMalferitAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = []
        captures = []
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-document-inventory/1.0"
            for url, parser in ((PGOU_URL, parse_pgou), (ACTUACIONES_URL, parse_actuaciones)):
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if urlsplit(response.url).hostname not in HOSTS:
                    raise ValueError("Unexpected municipal inventory redirect")
                rows.extend(parser(response.text, url))
                captures.append((url, response.content))
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        # Optional local evidence, never required for ordinary adapter use.
        if self.config.get("capture_dir"):
            directory = Path(self.config["capture_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            for url, body in captures:
                (directory / (url.rsplit("/", 1)[-1] + ".html")).write_bytes(body)
        return {"count": len(rows), "written": len(rows), "source_urls": list(SOURCE_URLS),
                "coverage": "partial_current_document_inventories", "limitations": LIMITATIONS,
                "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Current inventory snapshot; no claim to detect deletions or date deltas.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"count": 0, "written": 0, "disabled": True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
