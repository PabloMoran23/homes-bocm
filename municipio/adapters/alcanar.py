"""Alcanar's public notice board: current published planning instruments.

Wicket pagination is read with an anonymous session; no JavaScript is executed.
This is an active-board snapshot, not a historical planning or licence register.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://alcanar.eadministracio.cat"
SOURCE = BASE + "/board"
LIMITATIONS = [
    "Only planning instruments on the current public notice board; no historical completeness.",
    "General plans and special urban plans only; procurement, forms and unrelated notices excluded.",
    "Publication dates come from board rows; agreement/approval dates are not extracted from PDF bodies.",
    "PDF preview links are stable identities; PDF viewer URLs may expire.",
    "No verified project geometry; coordinates remain null and publication_ready is false.",
    "No granted-licence register extracted; licences and scheduling disabled.",
]


def _text(node):
    return node.get_text(" ", strip=True) if node else ""


def _official(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "alcanar.eadministracio.cat":
        raise ValueError("Unexpected Alcanar source URL")
    return url


def parse_page(html, *, initial=False):
    """Return all notice identities, selected planning documents and next action."""
    soup = BeautifulSoup(html, "html.parser")
    if initial and not soup.select_one("table.AdvertisementBoardListPanel"):
        raise ValueError("Alcanar board table missing (login/error or changed markup)")
    identities, documents = [], []
    for row in soup.select("tr:has(td.class_name)"):
        link = row.select_one("td.class_name a[href]")
        if not link:
            raise ValueError("Notice row has no document link")
        url = _official(urljoin(SOURCE, link["href"]))
        if not re.fullmatch(r"/preview-document/[0-9a-f-]{36}", urlparse(url).path):
            raise ValueError("Notice document identity changed")
        identities.append(url)
        procedure = _text(row.select_one(".class_folderName"))
        title = _text(link)
        supported = procedure == "Planejament General" or procedure.startswith("Aprovació de Pla Especial Urbanístic")
        if not supported:
            continue
        # Require an actual named plan act as well as the procedure category.
        if not re.search(r"(?:modificaci[oó].*pla general|pla especial urban[ií]stic)", title, re.I):
            raise ValueError("Unrecognized planning notice; review before omitting it")
        expediente = _text(row.select_one(".class_folderCode"))
        if not re.fullmatch(r"\d+/\d{4}", expediente):
            raise ValueError("Planning notice lacks a usable expediente")
        publication = datetime.strptime(_text(row.select_one(".class_dateFrom")), "%d/%m/%Y").date().isoformat()
        phase = re.search(r"aprovaci[oó]\s+(inicial|provisional|definitiva)", title, re.I)
        documents.append({
            "titulo": title, "url": url, "expediente": expediente,
            "procedimiento": procedure,
            "descripcion": _text(row.select_one(".class_description")),
            "fecha_publicacion": publication,
            "fase": "aprobación " + phase[1].lower() if phase else None,
        })
    if not identities:
        raise ValueError("No notice rows in Alcanar board response")
    controls = [b for b in soup.select("button") if "més" in _text(b).lower()]
    if len(controls) > 1:
        raise ValueError("Ambiguous board pagination")
    action = None
    if controls:
        match = re.search(r"wicketAjaxGet\('([^']+)'", controls[0].get("onclick", ""))
        if not match or not match[1].startswith("?x="):
            raise ValueError("Unknown board pagination action")
        action = match[1]
    elif initial and not soup.select_one(".more_results"):
        raise ValueError("Cannot verify board pagination termination")
    return identities, documents, action


def ajax_fragment(xml):
    root = ET.fromstring(xml)
    if root.tag != "ajax-response":
        raise ValueError("Expected Wicket board response")
    components = root.findall("component")
    # Wicket always updates the more-results container, including at the end.
    fragments = [BeautifulSoup(c.text or "", "html.parser") for c in components]
    if not any(s.select_one("div.more_results, div[id][style*='display:none']") for s in fragments):
        raise ValueError("Missing pagination state in board response")
    return "".join(c.text or "" for c in components)


def group_documents(documents):
    grouped = {}
    for doc in documents:
        grouped.setdefault(doc["expediente"], {})[doc["url"]] = doc
    rows = []
    for expediente, docs in sorted(grouped.items()):
        docs = sorted(docs.values(), key=lambda d: (d["fecha_publicacion"], d["url"]))
        latest = docs[-1]
        title = re.sub(r"^Anunci\s+(?:d[’']\s*)?aprovaci[oó]\s+(?:inicial|provisional|definitiva)\s+(?:de\s+)?", "", latest["titulo"], flags=re.I)
        rows.append({
            "id": "alcanar-proy-" + expediente.replace("/", "-"),
            "municipio": "Alcanar", "codigo_ine": "43004", "provincia": "Tarragona",
            "expediente": expediente, "titulo": title,
            "tipo": "planeamiento_urbanistico", "fase": latest["fase"],
            "descripcion": latest["descripcion"],
            "fecha": None, "fecha_publicacion": latest["fecha_publicacion"],
            "fecha_acuerdo": None, "fecha_aprob": None,
            "url": latest["url"], "url_documento": latest["url"],
            "source": "ayuntamiento", "source_inventory": SOURCE,
            "origen": "tablon_planeamiento", "documentos": docs,
            "lat": None, "lon": None, "geometry": None, "publication_ready": False,
            "cobertura": "Instrumentos publicados en el tablón vigente; no histórico completo",
        })
    if not rows:
        raise ValueError("No usable planning instruments in current Alcanar board")
    return rows


class AlcanarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug="alcanar", config=None, base_url=""):
        super().__init__(slug, config, base_url or BASE)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get("capture_dir")
        if captures:
            captures = Path(captures)
            captures.mkdir(parents=True, exist_ok=True)
        source_urls = []
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-alcanar/1.0 (public planning inventory)"

            def fetch(url, filename, *, ajax=False, pdf=False):
                _official(url)
                headers = {"Wicket-Ajax": "true", "Wicket-Ajax-BaseURL": "board"} if ajax else {}
                with session.get(url, timeout=40, headers=headers, stream=True) as response:
                    response.raise_for_status()
                    _official(response.url)
                    chunks, size = [], 0
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 10_000_000:
                            raise ValueError("Alcanar response exceeds 10 MB; no partial extraction")
                        chunks.append(chunk)
                    content = b"".join(chunks)
                    if pdf and not content.startswith(b"%PDF-"):
                        raise ValueError("Planning attachment is not a PDF")
                    if captures:
                        (captures / filename).write_bytes(content)
                    if not ajax and url not in source_urls:
                        source_urls.append(url)
                    return content if pdf else content.decode("utf-8")

            html = fetch(SOURCE, "board-000.html")
            seen, documents = set(), []
            for page in range(100):
                ids, selected, action = parse_page(html, initial=page == 0)
                if len(ids) != len(set(ids)) or seen.intersection(ids):
                    raise ValueError("Repeated notice rows; pagination did not advance")
                seen.update(ids)
                documents.extend(selected)
                if action is None:
                    break
                xml = fetch(SOURCE + action, f"board-{page + 1:03}.xml", ajax=True)
                html = ajax_fragment(xml)
            else:
                raise ValueError("Board exceeds 100 pages; refusing truncated output")
            rows = group_documents(documents)
            for row in rows:
                for doc in row["documentos"]:
                    doc_id = doc["url"].rsplit("/", 1)[-1]
                    soup = BeautifulSoup(fetch(doc["url"], doc_id + ".html"), "html.parser")
                    metadata = {_text(dt): _text(dt.find_next_sibling("dd")) for dt in soup.select("dl dt")}
                    iframe = soup.select_one("iframe[src]")
                    if metadata.get("Format") != "PDF" or not metadata.get("Codi CSV") or not iframe:
                        raise ValueError("Planning preview lacks PDF provenance")
                    pdf_url = _official(urljoin(doc["url"], iframe["src"]))
                    pdf = fetch(pdf_url, doc_id + ".pdf", pdf=True)
                    doc.update({"csv": metadata["Codi CSV"],
                                "fecha_creacion_documento_original": metadata.get("Data de creació"),
                                "url_pdf_observada": pdf_url, "sha256": hashlib.sha256(pdf).hexdigest(),
                                "fecha_acuerdo": None, "fecha_aprob": None})
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(path)
        return {"status": "ok", "rows": len(rows), "inventory_rows": len(seen), "pages": page + 1,
                "source_urls": source_urls, "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Refresh the entire active board; withdrawn notices are outside this snapshot.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return {"status": "disabled", "rows": 0, "reason": "No verified granted-licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
