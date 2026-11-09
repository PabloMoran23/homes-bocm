"""Snapshot of Sotillo's municipal planning inventory, grouped by instrument.

This is not the larger regional planning archive or a granted-licence register.
Article creation/update timestamps are deliberately not project dates.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.sotillo.net"
INVENTORY = BASE + "/ayuntamiento/urbanismo.html"
PLAN_TITLE = re.compile(
    r"^(Estudio de detalle\b|Modificación puntual\b|Normas Urbanísticas Municipales\b|"
    r"Plan (?:parcial|especial|general)\b|Proyecto de (?:urbanización|actuación)\b)", re.I
)
MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()
LIMITATIONS = [
    "Cobertura del inventario municipal de Urbanismo; no del archivo autonómico completo ni del tablón.",
    "No acredita vigencia consolidada; modificación 14 y estudio de detalle sin fase o fechas en sus páginas.",
    "Documentos enlazados conservados como procedencia; su contenido no se extrae ni georreferencia.",
    "Sin registro verificado de licencias concedidas ni coordenadas o geometría de los instrumentos.",
]


def municipal_url(href: str, base: str = BASE) -> str:
    parts = urlsplit(urljoin(base, href))
    if parts.hostname not in {"sotillo.net", "www.sotillo.net"} or parts.scheme not in {"http", "https"}:
        raise ValueError("Unexpected non-municipal inventory/detail link")
    return urlunsplit(("https", "www.sotillo.net", parts.path, parts.query, ""))


def parse_inventory(html: str) -> list[tuple[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    section = soup.select_one("section#seccion")
    if not section or not section.h1 or section.h1.get_text(strip=True) != "Urbanismo":
        raise ValueError("Missing municipal Urbanismo inventory")
    # The verified inventory is a single unpaginated list. Fail visibly if this
    # changes, instead of silently processing only its first page.
    if section.select('[rel~=next], .pagination, .paginacion') or any(
        re.search(r"siguiente|última|página\s+\d", a.get_text(" ", strip=True), re.I)
        or re.search(r"[?&](?:page|pagina|pag|offset)=", a.get("href", ""), re.I)
        for a in section.select("a[href]")
    ):
        raise ValueError("Pagination appeared in municipal inventory; traversal needs review")
    found = {}
    for icon in section.select("a[href] h6 i.fa-arrow-circle-right"):
        a = icon.find_parent("a")
        title = a.get_text(" ", strip=True)
        if PLAN_TITLE.match(title):
            found[municipal_url(a["href"], INVENTORY)] = title
    if not found:
        raise ValueError("No named instruments in municipal inventory")
    return [(title, url) for url, title in found.items()]


def parse_project(html: str, url: str, expected_title: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one(".noticia")
    heading = article.select_one("h1.titulo") if article else None
    body = article.select_one("#cuerpo") if article else None
    if not heading or not body or heading.get_text(" ", strip=True) != expected_title:
        raise ValueError("Instrument detail missing or inconsistent with inventory")
    description = body.get_text(" ", strip=True)
    documents = {}
    for a in soup.select("#cuerpo a[href], .contenedorarchivos a[href]"):
        target = urljoin(url, a["href"])
        parts = urlsplit(target)
        if parts.scheme not in {"http", "https"} or parts.hostname not in {
            "sotillo.net", "www.sotillo.net", "bocyl.jcyl.es", "servicios.jcyl.es"
        }:
            raise ValueError("Unexpected document provenance")
        if parts.hostname in {"sotillo.net", "www.sotillo.net"}:
            target = municipal_url(target)
        documents[target] = {"titulo": a.get_text(" ", strip=True), "url": target,
                             "source_page": url}
    if not description or not documents:
        raise ValueError("Instrument has no description or supporting documents")
    agreement = re.search(r"aprobadas definitivamente por Acuerdo de (\d{1,2}) de (\w+) de (\d{4})", description, re.I)
    approved = None
    if agreement:
        approved = date(int(agreement[3]), MONTHS.index(agreement[2].lower()) + 1, int(agreement[1])).isoformat()
    return {
        "id": "sotillo-plan-" + hashlib.sha256(url.encode()).hexdigest()[:16],
        "municipio": "Sotillo de la Adrada", "provincia": "Ávila", "codigo_ine": "05240",
        "titulo": expected_title, "tipo": "instrumento de planeamiento urbanístico",
        "fase": "aprobación definitiva" if approved else None,
        "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": approved,
        "fecha_aprob": approved, "descripcion": description,
        "url": url, "inventory_url": INVENTORY, "documentos": list(documents.values()),
        "source": "ayuntamiento", "origen": "inventario_municipal_urbanismo",
        "lat": None, "lon": None, "geometry": None,
        "publication_ready": False, "geometry_status": "unavailable",
    }


class SotilloDeLaAdradaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or BASE)

    def _fetch(self, session, url):
        with session.get(url, timeout=40, stream=True) as response:
            response.raise_for_status()
            if municipal_url(response.url) != municipal_url(url):
                raise ValueError("Unexpected municipal redirect")
            if "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("Expected HTML municipal inventory/detail")
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 3_000_000:
                    raise ValueError("Municipal HTML response exceeds size bound")
            if self.config.get("evidence_dir"):
                capture = Path(self.config["evidence_dir"])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / (urlsplit(url).path.rsplit("/", 1)[-1])).write_bytes(content)
            return content.decode("utf-8")

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-sotillo-inventory/1.0"
            inventory = parse_inventory(self._fetch(session, INVENTORY))
            rows = [parse_project(self._fetch(session, url), url, title) for title, url in inventory]
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return {"status": "ok", "rows": len(rows), "source_urls": [INVENTORY] + [u for _, u in inventory],
                "coverage": "municipal_planning_inventory_snapshot", "limitations": LIMITATIONS,
                "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # A full snapshot also reflects removals from the current inventory.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"status": "disabled", "rows": 0, "reason": "No verified granted-licence inventory"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
