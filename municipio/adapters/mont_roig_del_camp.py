"""Snapshot of the municipality's two public-information project inventories.

HTML headings identify projects; their attached documents are children, not
separate projects. PDF contents, dates and geometry are not inferred from links.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://mont-roig.cat"
ROOT = BASE + "/lajuntament/arees/urbanisme-i-territori/ordenacio-urbanistica-del-municipi/"
SOURCES = {
    ROOT + "documents-en-tramit/informacio-publica/projectes-municipals/": "Projectes municipals",
    ROOT + "documents-en-tramit/informacio-publica/planejament-urbanistic/": "Planejament urbanístic",
}
LIMITATIONS = [
    "Partial coverage: current listings on two public-information pages, not a historical register or all municipal planning.",
    "Dates remain null: HTML inventories do not state agreement/publication dates; linked PDF contents are not parsed.",
    "No verified geometry or coordinates; publication_ready=false.",
    "Public-information status is as listed by the municipality; no claim that consultation periods remain legally open.",
    "No granted-licence register extracted; licence forms, tenders and news excluded.",
]


def parse_inventory(html: str, source_url: str) -> list[dict]:
    if source_url not in SOURCES:
        raise ValueError("Unknown municipal inventory")
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    if h1 is None or h1.get_text(" ", strip=True) != SOURCES[source_url]:
        raise ValueError("Unexpected inventory title (redirect or changed markup)")
    # These are unpaginated static pages. Fail closed if pagination appears,
    # rather than returning only the first page of a changed inventory.
    if soup.select('a[rel~="next"], link[rel~="next"], .pagination, .page-numbers, .page-links, .vc_grid-pagination'):
        raise ValueError("Inventory pagination requires explicit implementation")
    containers = soup.select(".wpb_text_column > .wpb_wrapper")
    records = []
    for container in containers:
        headings = container.find_all("h4", recursive=False)
        for heading in headings:
            title = heading.get_text(" ", strip=True)
            match = re.fullmatch(r"(?:(\d+/\d{4})\s+)?(Projecte\s+d[’']urbanització\b.+)", title, re.I)
            if not match:
                raise ValueError(f"Unrecognized inventory heading: {title}")
            nodes = []
            for sibling in heading.next_siblings:
                if getattr(sibling, "name", None) == "h4":
                    break
                if getattr(sibling, "name", None):
                    nodes.append(sibling)
            documents = {}
            for node in nodes:
                for anchor in node.select("a[href]"):
                    target = urljoin(source_url, anchor["href"])
                    parsed = urlsplit(target)
                    if parsed.scheme != "https" or parsed.hostname != "mont-roig.cat" or not parsed.path.startswith("/wp-content/") or not parsed.path.lower().endswith(".pdf"):
                        raise ValueError(f"Unexpected project document URL: {target}")
                    # A split anchor in the live HTML shares one li and URL.
                    label = " ".join((anchor.find_parent("li") or anchor).get_text().split())
                    documents[target] = {"titulo": label, "url": target, "source_url": source_url}
            if not documents:
                raise ValueError(f"Project without document provenance: {title}")
            narrative = " ".join(node.get_text(" ", strip=True) for node in nodes if node.name == "p")
            if "Aprovació inicial:" not in narrative and "Exposició pública:" not in narrative and "exposició pública" not in container.get_text(" ", strip=True):
                raise ValueError("Missing explicit public-information/approval context")
            phase = "aprobación inicial" if "Aprovació inicial:" in narrative else "exposición pública"
            # Identity is independent of document ordering or file replacements.
            identity = match[1] or " ".join(match[2].casefold().split())
            records.append({
                "id": "mont-roig-del-camp-proy-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
                "municipio": "Mont-roig del Camp", "codigo_ine": "43092", "provincia": "Tarragona",
                "titulo": title, "expediente": match[1], "tipo": "proyecto de urbanización",
                "fase": phase, "fecha": None, "fecha_publicacion": None,
                "fecha_acuerdo": None, "fecha_aprob": None,
                "url": source_url, "url_documento": next(iter(documents)),
                "documentos": list(documents.values()), "source_urls": [source_url],
                "source": "ayuntamiento", "origen": "inventario_informacion_publica",
                "lat": None, "lon": None, "geometry": None,
                "geometry_status": "unavailable", "publication_ready": False,
            })
    if not records:
        raise ValueError("No documented project headings in inventory")
    return records


class MontRoigDelCampAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        records = {}
        captures = self.config.get("capture_dir")
        for index, url in enumerate(SOURCES):
            with requests.get(url, timeout=45, stream=True, headers={
                "User-Agent": "municipio-mont-roig-del-camp/1.0",
            }) as response:
                response.raise_for_status()
                if response.url.rstrip("/") != url.rstrip("/"):
                    raise ValueError("Unexpected inventory redirect")
                data = bytearray()
                for chunk in response.iter_content(65536):
                    data.extend(chunk)
                    if len(data) > 4_000_000:
                        raise ValueError("Inventory response exceeds size limit")
                html = data.decode("utf-8")
            if captures:
                folder = Path(captures)
                folder.mkdir(parents=True, exist_ok=True)
                (folder / f"inventory-{index}.html").write_bytes(data)
            for row in parse_inventory(html, url):
                previous = records.get(row["id"])
                if previous:
                    if previous["titulo"] != row["titulo"] or previous["fase"] != row["fase"]:
                        raise ValueError("Conflicting project identity across inventories")
                    docs = {d["url"]: d for d in previous["documentos"] + row["documentos"]}
                    previous["documentos"] = list(docs.values())
                    previous["source_urls"] = sorted(set(previous["source_urls"] + row["source_urls"]))
                else:
                    records[row["id"]] = row
        # Write only after every inventory has been fetched and parsed.
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records.values()), encoding="utf-8")
        return {"status": "ok", "rows": len(records), "source_urls": list(SOURCES),
                "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        """Full snapshot refresh; never infer incremental dates from page metadata."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"status": "disabled", "rows": 0, "reason": "No verified granted-licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
