"""Complete snapshot of Membrilla's published planning-document inventory.

This is a document inventory, not a register of granted licences or completed
works. Scanned PDF dates and map geometry are deliberately not inferred.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://membrilla.es/planeamiento-urbanistico/"
SECTIONS = {"normas de planeamiento urbanistico", "instrumentos de desarrollo urbanistico"}
LIMITATIONS = [
    "Partial municipal coverage: only the current planning-document inventory, not a historical register.",
    "Published documents do not establish granted licences, completed works or current procedural status.",
    "Dates remain null: scanned PDF dates are not parsed; upload paths are not publication dates.",
    "No verified coordinates or vector geometry; publication_ready is false.",
    "Shared entity policy may leave instruments pending: no invented expediente references are supplied.",
]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


class MembrillaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or "https://membrilla.es")

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        heading = soup.find("h1")
        if not heading or _norm(heading.get_text(" ", strip=True)) != "planeamiento urbanistico":
            raise ValueError("Missing municipal planning inventory heading")
        # This source is one unpaginated page. Fail explicitly if that changes.
        for a in soup.select("a[href]"):
            if ("next" in a.get("rel", []) or
                _norm(a.get_text(" ", strip=True)) in {"siguiente", "next", "cargar mas", "ver mas"} or
                re.search(r"/page/\d|[?&](?:paged|page)=", a["href"])):
                raise ValueError("Pagination detected; inventory cannot be silently truncated")
        if soup.select('[class*="pagination"], [class*="load-more"], link[rel="next"]'):
            raise ValueError("Pagination detected; review crawler")

        rows = {}
        seen_docs = {}
        section = None
        sections_seen = set()
        current = None
        current_container = None
        for node in soup.select("h2, .elementor-icon-box-title a[href]"):
            title = node.get_text(" ", strip=True)
            norm = _norm(title)
            if node.name == "h2":
                section = norm if norm in SECTIONS else None
                if section:
                    sections_seen.add(section)
                current = current_container = None
                continue
            if section is None:
                continue
            url = urljoin(SOURCE, node["href"])
            parsed = urlsplit(url)
            if (parsed.scheme != "https" or parsed.netloc != "membrilla.es" or
                not parsed.path.startswith("/wp-content/uploads/") or
                not parsed.path.lower().endswith(".pdf") or parsed.query or parsed.fragment):
                raise ValueError("Unexpected planning-document URL: " + url)
            container = node.find_parent(attrs={"data-element_type": "container"})
            if norm.startswith("normas urbanisticas de membrilla"):
                kind = "normas_subsidiarias"
            elif norm.startswith("modificacion puntual"):
                kind = "modificacion_planeamiento"
            elif norm.startswith("estudio de detalle"):
                kind = "estudio_detalle"
            elif norm.startswith("proyecto de reparcelacion"):
                kind = "reparcelacion"
            elif norm.startswith("proyecto obra publica ordinaria de urbanizacion"):
                kind = "proyecto_urbanizacion"
            elif norm == "oficio diferentes organismos" or re.fullmatch(r"planos \d+", norm):
                if (current is None or current["tipo"] != "modificacion_planeamiento" or
                    container is None or container is not current_container):
                    raise ValueError("Annex without unambiguous parent planning instrument")
                if url in seen_docs:
                    if seen_docs[url] != current["url_documento"]:
                        raise ValueError("Document shared by conflicting instruments")
                    continue
                current["documentos"].append({"titulo": title, "url": url, "rol": "anexo"})
                seen_docs[url] = current["url_documento"]
                continue
            else:
                raise ValueError("Unclassified planning inventory item: " + title)
            if url in seen_docs:
                if url not in rows or rows[url]["titulo"] != title:
                    raise ValueError("Conflicting document identity")
                current = rows[url]
                current_container = container
                continue
            current = {
                "id": "membrilla-proy-" + hashlib.sha256(url.encode()).hexdigest()[:16],
                "municipio": "Membrilla", "codigo_ine": "13054", "provincia": "Ciudad Real",
                "titulo": title, "tipo": kind, "fase": None,
                "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
                "url": SOURCE, "url_documento": url, "source": "ayuntamiento",
                "origen": "inventario_documental_planeamiento", "seccion_fuente": section,
                "documentos": [{"titulo": title, "url": url, "rol": "principal"}],
                "lat": None, "lon": None, "geometry": None, "publication_ready": False,
                "coverage": "Inventario documental municipal; estado de tramitación no extraído",
            }
            rows[url] = current
            seen_docs[url] = url
            current_container = container
        if sections_seen != SECTIONS or not rows:
            raise ValueError("Missing planning inventory sections or records")
        return list(rows.values())

    def _fetch(self, url: str, limit: int) -> bytes:
        with requests.get(url, timeout=(15, 60), stream=True, headers={
            "User-Agent": self.config.get("user_agent", "Mozilla/5.0 (municipio-membrilla/1.0)"),
            "Referer": SOURCE,
        }) as response:
            response.raise_for_status()
            if urlsplit(response.url).netloc != "membrilla.es":
                raise ValueError("Unexpected redirect away from municipal source")
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > limit:
                    raise ValueError("Source exceeds response size limit: " + url)
        return bytes(content)

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict[str, Any]]) -> None:
        out_jsonl = Path(out_jsonl)
        out_jsonl.parent.mkdir(parents=True, exist_ok=True)
        temp = out_jsonl.with_suffix(out_jsonl.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        html = self._fetch(SOURCE, 2_000_000)
        rows = self.parse_projects(html.decode("utf-8"))
        capture = self.config.get("capture_dir")
        if capture:
            capture = Path(capture)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "planeamiento.html").write_bytes(html)
        sources = [SOURCE]
        for row in rows:
            for doc in row["documentos"]:
                body = self._fetch(doc["url"], 30_000_000)
                if not body.startswith(b"%PDF-"):
                    raise ValueError("Linked planning document is not a PDF: " + doc["url"])
                doc["sha256"] = hashlib.sha256(body).hexdigest()
                doc["bytes"] = len(body)
                sources.append(doc["url"])
                if capture:
                    (capture / urlsplit(doc["url"]).path.rsplit("/", 1)[-1]).write_bytes(body)
        # Do not replace a previous successful snapshot if any request fails.
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": sources,
                "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        """Refresh the entire current inventory, including replaced PDF content."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0, "reason": "No verified granted-licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
