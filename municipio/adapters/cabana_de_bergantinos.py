"""Physical expropriation projects in Cabana's public-information inventory.

This is a complete refresh of this one inventory, not municipal-wide coverage.
The technical documents are retained together; no PDF dates imply an agreement.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


BASE_URL = "https://sede.cabana.gal"
SOURCE_URL = BASE_URL + (
    "/sxc/gl/portal_transparencia/Relevancia_Juridica/"
    "Proyectos_Normativos/Proyectos_Normativos.html"
)
DOCUMENT_PATH = "/sxc/export/sites/cabana/recursos/downloads/portal_transparencia/"


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#fondoderecha")
    if (not content or "Concello de Cabana de Bergantiños" not in soup.get_text(" ", strip=True)
            or "Información pública" not in content.get_text(" ", strip=True)):
        raise ValueError("Missing Cabana public-information inventory")
    # This source currently has no pagination. A changed paged inventory must be
    # investigated, rather than returning just its first page as complete.
    if (soup.select('[rel~=next], .pagination, .pager, [class*=pagin], [id*=pagin]')
            or any(re.search(r"[?&](?:page|pagina|offset|start)=", a["href"], re.I)
                   for a in content.select("a[href]"))):
        raise ValueError("Inventory now exposes pagination; coverage requires review")

    records = {}
    seen_rows = set()
    for anchor in content.select("li a[href]"):
        title = anchor.get_text(" ", strip=True)
        # Only named physical expropriation projects, never generic regulatory
        # consultations, applications, procurement notices or navigation links.
        if not re.match(r"^Proxecto de expropiación\b.*\bexecución\b", title, re.I):
            continue
        row = anchor.find_parent("li")
        if id(row) in seen_rows:
            continue
        seen_rows.add(id(row))
        context = row.find_parent("li")
        if not context or "Información pública" not in context.get_text(" ", strip=True):
            raise ValueError("Project no longer under public information")
        primary = urldefrag(urljoin(SOURCE_URL, anchor["href"]))[0]
        documents = {}
        for link in row.select("a[href]"):
            target = urldefrag(urljoin(SOURCE_URL, link["href"]))[0]
            parsed = urlparse(target)
            if not parsed.path.lower().endswith(".pdf"):
                continue
            if (parsed.scheme != "https" or parsed.netloc != "sede.cabana.gal"
                    or not parsed.path.startswith(DOCUMENT_PATH)):
                raise ValueError("Unexpected project document origin")
            documents[target] = {
                "url": target, "titulo": link.get_text(" ", strip=True),
                "source_url": SOURCE_URL,
            }
        if primary not in documents:
            raise ValueError("Project lacks a municipal technical PDF")
        key = "cabana-de-bergantinos-proy-" + hashlib.sha256(primary.encode()).hexdigest()[:16]
        if key in records:
            continue
        records[key] = {
            "id": key, "municipio": "Cabana de Bergantiños", "codigo_ine": "15014",
            "provincia": "A Coruña", "titulo": title,
            "tipo": "proyecto de expropiación urbanística",
            "fase": "información pública", "fase_source_url": SOURCE_URL,
            "fecha": None, "fecha_publicacion": None,
            "fecha_acuerdo": None, "fecha_aprob": None,
            "url": SOURCE_URL, "inventory_url": SOURCE_URL, "url_documento": primary,
            "documentos": list(documents.values()),
            "source": "ayuntamiento", "origen": "inventario_informacion_publica",
            "lat": None, "lon": None, "geometry": None,
            "publication_ready": False,
            "geometry_status": "No verified machine-readable project geometry extracted",
            "coverage": "Physical expropriation projects linked in this municipal inventory only",
        }
    if not records:
        raise ValueError("No usable physical expropriation projects in inventory")
    return list(records.values())


class CabanaDeBergantinosAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or BASE_URL)

    def _fetch(self, url: str, limit: int, pdf: bool = False) -> bytes:
        with requests.get(
            url, timeout=(15, 60), stream=True,
            headers={"User-Agent": "municipio-cabana-de-bergantinos/1.0"},
        ) as response:
            response.raise_for_status()
            if response.url != url:
                raise ValueError("Unexpected source redirect: " + response.url)
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > limit:
                    raise ValueError("Source exceeds response size limit")
            if pdf and not data.startswith(b"%PDF-"):
                raise ValueError("Technical document did not return a PDF")
            if not pdf and "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("Inventory did not return HTML")
            return bytes(data)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        html = self._fetch(SOURCE_URL, 2_000_000)
        records = parse_inventory(html.decode("utf-8"))
        captures = self.config.get("capture_dir")
        capture_dir = Path(captures) if captures else None
        if capture_dir:
            capture_dir.mkdir(parents=True, exist_ok=True)
            (capture_dir / "proyectos-normativos.html").write_bytes(html)
        fetched = {}
        for record in records:
            for document in record["documentos"]:
                url = document["url"]
                if url not in fetched:
                    body = self._fetch(url, 32_000_000, pdf=True)
                    fetched[url] = {
                        "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                        "media_type": "application/pdf",
                    }
                    if capture_dir:
                        (capture_dir / (fetched[url]["sha256"] + ".pdf")).write_bytes(body)
                document.update(fetched[url])
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        return {
            "status": "ok", "rows": len(records), "source_urls": [SOURCE_URL, *fetched],
            "publication_ready": False, "coverage": "single public-information inventory",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"status": "disabled", "rows": 0, "reason": "No verified public granted-licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
