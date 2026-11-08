"""Pinos Puente: municipal PGOU and named planning instrument inventories."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote, unquote, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = "https://www.pinos-puente.org/ayuntamiento/"
PAGES = ("plan-general-de-ordenacion-urbana", "instrumentos-de-ordenacion")
HOSTS = {"pinos-puente.org", "www.pinos-puente.org"}
LIMITATIONS = [
    "Partial coverage: PGOU and the municipal Instrumentos de ordenación inventory only; "
    "not a complete historical planning or public works register.",
    "Normas subsidiarias and Plan Especial de Protección de la Vega are outside this extraction.",
    "Document links are retained; PDF contents and current legal validity are not inferred.",
    "No granted licences, agreement/publication dates or coordinates are inferred.",
]


def canonical(url):
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or parts.hostname not in HOSTS:
        raise ValueError("Unexpected municipal source URL")
    return urlunsplit(("https", "pinos-puente.org", quote(unquote(parts.path), safe="/"), parts.query, ""))


def content(html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main")
    if main is None:
        raise ValueError("Municipal content container missing")
    # These are single-page inventories. Fail explicitly if pagination is introduced.
    for a in soup.select("a[href]"):
        text = a.get_text(" ", strip=True).casefold()
        href = a["href"]
        if (a.get("rel") and "next" in a["rel"]) or text in {
            "siguiente", "siguiente página", "next", "next page", "»", "›"
        } or re.search(r"[?&](?:page|paged)=|/page/\d", href) or a.select_one(".fa-angle-right"):
            raise ValueError("Pagination detected; review crawler before extracting partial results")
    if soup.select(".pagination a[href], .page-numbers[href], .nav-links a[href]"):
        raise ValueError("Pagination detected")
    return main


def documents(panel, page_url):
    docs = {}
    for a in panel.select(".wgl-accordion_content a[href]"):
        raw = urljoin(page_url, a["href"])
        path = unquote(urlsplit(raw).path)
        if not path.lower().endswith(".pdf"):
            continue
        url = canonical(raw)
        if not path.startswith("/documentos/"):
            raise ValueError("Unexpected document location")
        docs.setdefault(url, {"titulo": a.get_text(" ", strip=True), "url": url})
    if not docs:
        raise ValueError("Instrument section has no source PDF documents")
    return list(docs.values())


def record(title, key, page_url, docs):
    return {
        "id": "pinos-puente-plan-" + hashlib.sha256(key.encode()).hexdigest()[:16],
        "municipio": "Pinos Puente", "codigo_ine": "18158", "provincia": "Granada",
        "titulo": title, "tipo": "planeamiento_urbanistico", "url": canonical(page_url),
        "inventory_url": canonical(page_url), "source": "ayuntamiento",
        "origen": "inventario_documental_planeamiento", "documentos": docs,
        "publication_ready": False, "geometry_status": "unavailable",
    }


def parse_inventory(html, page_url, kind):
    main = content(html)
    panels = main.select(".wgl-accordion_panel")
    if not panels:
        raise ValueError("Planning accordion inventory missing")
    if kind == "plan-general-de-ordenacion-urbana":
        docs = {}
        for panel in panels:
            heading = panel.select_one(".wgl-accordion_header")
            if heading is None:
                raise ValueError("PGOU section title missing")
            section = heading.get_text(" ", strip=True)
            for doc in documents(panel, page_url):
                if not unquote(urlsplit(doc["url"]).path).startswith("/documentos/PGOU/"):
                    raise ValueError("Document does not belong to PGOU")
                docs.setdefault(doc["url"], {**doc, "seccion": section})
        return [record("Plan General de Ordenación Urbana de Pinos Puente", "pgou", page_url, list(docs.values()))]
    if kind != "instrumentos-de-ordenacion":
        raise ValueError("Unsupported inventory")
    rows = {}
    for panel in panels:
        heading = panel.select_one(".wgl-accordion_header")
        title = heading.get_text(" ", strip=True) if heading else ""
        if not re.search(r"PLAN PARCIAL|ESTUDIO (?:DE )?DETALLE|PLAN ESPECIAL|PROYECTO|MODIFICACI[OÓ]N", title, re.I):
            raise ValueError("Unrecognized planning section; review inventory")
        docs = documents(panel, page_url)
        # The document directory identifies the instrument, independent of CMS element IDs.
        folders = {urlsplit(d["url"]).path.rsplit("/", 1)[0] for d in docs}
        if len(folders) != 1:
            raise ValueError("Ambiguous instrument document grouping")
        key = folders.pop()
        if key in rows:
            raise ValueError("Duplicate instrument sections")
        rows[key] = record(title, key, page_url, docs)
    return list(rows.values())


class PinosPuenteAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url, capture):
        # Both hostnames are official aliases; availability differs at the site's edge.
        canonical_url = canonical(url)
        candidates = [url, canonical_url] if url != canonical_url else [url, url.replace("https://pinos-puente.org/", "https://www.pinos-puente.org/", 1)]
        failure = None
        for candidate in candidates:
            try:
                response = requests.get(candidate, timeout=40, headers={"User-Agent": "Mozilla/5.0"})
                response.raise_for_status()
                break
            except requests.RequestException as exc:
                failure = exc
        else:
            raise failure
        canonical(response.url)
        if self.config.get("evidence_dir"):
            directory = Path(self.config["evidence_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            (directory / capture).write_text(response.text, encoding="utf-8")
        return response.text, response.url

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        html, directory_url = self._fetch(ROOT, "ayuntamiento.html")
        main = content(html)
        links = {urlsplit(urljoin(directory_url, a["href"])).path.rstrip("/"): urljoin(directory_url, a["href"])
                 for a in main.select("a[href]")}
        rows, sources = [], [directory_url]
        for kind in PAGES:
            url = links.get("/ayuntamiento/" + kind)
            if not url:
                raise ValueError("Official directory no longer links to " + kind)
            # www entry point currently redirects to the canonical non-www site.
            url = canonical(url).replace("https://pinos-puente.org/", "https://www.pinos-puente.org/", 1)
            html, final_url = self._fetch(url, kind + ".html")
            rows.extend(parse_inventory(html, final_url, kind))
            sources.append(final_url)
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "source_urls": sources,
                "coverage": "partial_current_document_inventories", "limitations": LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified public granted-licence register"}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
