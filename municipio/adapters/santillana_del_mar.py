"""Complete snapshot of the municipal PGOU revision document inventory."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

HOST = "santillanadelmar.sedelectronica.es"
SOURCE = f"https://{HOST}/transparency/7d237b45-2517-4279-9e49-8dbe643f3208/"
LIMITATIONS = [
    "Partial municipal coverage: only the dedicated PGOU revision inventory; "
    "the existing PGOU, its modifications and Castío detail study are outside this snapshot.",
    "Document inventory and preview metadata only; PDF contents and geometry are not extracted.",
    "The phase describes the published advance documents, not a verified current approval status.",
    "No granted licence register, approval date or verified coordinates extracted.",
]


def parse_inventory(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#content")
    if content is None or "REVISION PGOU SANTILLANA DEL MAR" not in content.get_text(" ", strip=True):
        raise ValueError("Missing dedicated municipal PGOU revision inventory")
    # The verified inventory is unpaginated. Fail closed if paging or child
    # folders appear, rather than silently exporting only the first visible page.
    for element in content.select("a, button, select, [class], [id]"):
        marker = " ".join(element.get("class", [])) + " " + element.get("id", "")
        rel = element.get("rel", [])
        if re.search(r"pagin|paging|navigator", marker, re.I) or any(r in rel for r in ("next", "last")):
            raise ValueError("Inventory pagination requires explicit traversal")
        if element.name in ("a", "button") and re.search(
            r"^(siguiente|next|últim[ao]|last|[»›])$", element.get_text(" ", strip=True), re.I
        ):
            raise ValueError("Inventory pagination requires explicit traversal")
    tables = content.select("table.TransparencyListPanel")
    if len(tables) != 1:
        raise ValueError("Ambiguous document inventory")
    documents = {}
    for cell in tables[0].select("td.class_name"):
        links = cell.select("a[href]")
        if len(links) != 1:
            raise ValueError("Unsupported inventory row or nested folder")
        anchor = links[0]
        title = anchor.get_text(" ", strip=True)
        url = urljoin(SOURCE, anchor["href"])
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.netloc != HOST or parsed.query or parsed.fragment
                or not re.fullmatch(r"/preview-document/[0-9a-f-]{36}", parsed.path) or not title):
            raise ValueError("Unexpected document link")
        if url in documents and documents[url]["titulo"] != title:
            raise ValueError("Conflicting document titles")
        documents[url] = {"titulo": title, "url": url, "inventory_url": SOURCE}
    titles = " ".join(d["titulo"] for d in documents.values())
    if not all(re.search(rf"TOMO_{n}_", titles) for n in ("I", "II", "III")) or "AVANCE" not in titles:
        raise ValueError("Missing technical advance volumes")
    notices = [d for d in documents.values() if re.search(r"PUBLICACI[ÓO]N ANUNCIO AVANCE BOC", d["titulo"])]
    if len(notices) != 1:
        raise ValueError("Missing or ambiguous publication notice")
    match = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4}|\d{2})\b", notices[0]["titulo"])
    publication = None
    if match:
        day, month, year = map(int, match.groups())
        publication = date(year + 2000 if year < 100 else year, month, day).isoformat()
    return [{
        "id": "santillana-del-mar-plan-" + hashlib.sha256(SOURCE.encode()).hexdigest()[:16],
        "municipio": "Santillana del Mar", "codigo_ine": "39076", "provincia": "Cantabria",
        "titulo": "Revisión del PGOU de Santillana del Mar — documentación de avance",
        "tipo": "revisión del Plan General de Ordenación Urbana",
        "fase": "avance (documentación publicada)",
        "fecha": None, "fecha_publicacion": publication, "fecha_acuerdo": None, "fecha_aprob": None,
        "fecha_publicacion_fuente": notices[0]["url"] if publication else None,
        "url": SOURCE, "inventory_url": SOURCE, "documentos": list(documents.values()),
        "source": "ayuntamiento", "origen": "inventario_revision_pgou",
        "lat": None, "lon": None, "geometry": None, "geometry_status": "unavailable",
        "publication_ready": False, "limitations": LIMITATIONS,
    }]


class SantillanaDelMarAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url, capture_name):
        with session.get(url, timeout=40, stream=True) as response:
            response.raise_for_status()
            if urlparse(response.url).netloc != HOST or urlparse(response.url).scheme != "https":
                raise ValueError("Unexpected source redirect")
            if "text/html" not in response.headers.get("Content-Type", ""):
                raise ValueError("Expected source HTML")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError("Source exceeds HTML size bound")
        if self.config.get("evidence_dir"):
            directory = Path(self.config["evidence_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture_name).write_bytes(data)
        return bytes(data).decode("utf-8")

    def backfill_proyectos(self, out_jsonl: Path):
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-santillana-del-mar/1.0"
            rows = parse_inventory(self._fetch(session, SOURCE, "revision-inventory.html"))
            for document in rows[0]["documentos"]:
                preview = self._fetch(session, document["url"], document["url"].rsplit("/", 1)[-1] + ".html")
                soup = BeautifulSoup(preview, "html.parser")
                info = soup.select_one("#validationPageInfoDocument")
                # Preview creation dates are metadata, never plan agreement dates.
                if info is None or document["titulo"] not in info.get_text(" ", strip=True):
                    raise ValueError("Document preview missing expected public metadata")
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return {"status": "ok", "count": len(rows), "written": len(rows),
                "coverage": "dedicated_pgou_revision_inventory", "publication_ready": False,
                "source_urls": [SOURCE] + [d["url"] for d in rows[0]["documentos"]],
                "limitations": LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"count": 0, "disabled": True, "reason": "No verified granted licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
