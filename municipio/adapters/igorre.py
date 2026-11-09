"""Igorre's official PGOU document collection; one instrument across all stages.

This deliberately excludes the general notice board, contracts and news. Dates
in folder/file names are not agreement or publication dates.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.igorre.net"
PAGE_PREFIX = "/es-ES/Servicios/Urbanismo/Paginas/"
SOURCE = BASE + PAGE_PREFIX + "PlanGeneraldeOrdenacionUrbana.aspx"
LIMITATIONS = [
    "Cobertura parcial: solo la colección documental del PGOU; no todo el planeamiento ni las obras municipales.",
    "Fechas no extraídas de los PDF: fecha_publicacion y fecha_acuerdo son nulas; los años de carpetas no se usan como fechas.",
    "Documentos enlazados con página y fase de procedencia; no se descarga ni interpreta todo su contenido.",
    "Sin geometría verificada del instrumento ni coordenadas; licencias deshabilitadas.",
]


def canonical(url: str) -> str:
    url = urldefrag(url)[0]
    return url[:-7] if url.endswith("?page=1") else url


def parse_page(html: str, url: str) -> tuple[list[dict], list[dict]]:
    """Return content and all paging links; attach per-list completeness totals."""
    soup = BeautifulSoup(html, "html.parser")
    pages, docs = {}, {}
    for a in soup.select("a[href], input[type=submit]"):
        label = " ".join((a.get_text(" ", strip=True), a.get("title", ""),
                          a.get("aria-label", ""), a.get("value", ""))).lower()
        if a.find_parent(class_="pagination"):
            target = canonical(urljoin(url, a.get("href", "")))
            parsed = urlparse(target)
            query = parse_qs(parsed.query)
            if (parsed.scheme != "https" or parsed.hostname != "www.igorre.net" or
                    parsed.path != urlparse(url).path or
                    (parsed.query and (set(query) != {"page"} or len(query["page"]) != 1 or
                                       not re.fullmatch(r"[1-9]\d*", query["page"][0])))):
                raise ValueError(f"Unrecognized pagination: {target}")
            pages.setdefault(target, {"titulo": "Paginación", "url": target, "pagina_origen": url})
        elif (set(a.get("rel", [])) & {"next"} or
                re.search(r"\b(siguiente|next|hurrengoa)\b", label) or
                a.get_text(strip=True) in {">", "»", "›"}):
            raise ValueError(f"Pagination requires review before extraction: {url}")
    for a in soup.select(".link-item a[href], .CSPFileName a[href], .ms-rtestate-field a[href]"):
        target = canonical(urljoin(url, a["href"]))
        parsed = urlparse(target)
        title = a.get_text(" ", strip=True)
        if not title:
            raise ValueError(f"Untitled content link: {url}")
        if parsed.scheme != "https" or parsed.hostname != "www.igorre.net":
            raise ValueError(f"Unexpected content origin: {target}")
        item = {"titulo": title, "url": target, "pagina_origen": url}
        if parsed.path.startswith(PAGE_PREFIX) and parsed.path.lower().endswith(".aspx"):
            if parsed.query:
                raise ValueError(f"Unexpected query on collection page: {target}")
            pages.setdefault(target, item)
        elif parsed.path.lower().endswith((".pdf", ".zip")):
            block = a.find_parent(class_="ms-WPBody")
            totals = re.findall(r"Resultados\s+(\d+)\s*[-–]\s*(\d+)\s+de\s+(\d+)",
                                block.get_text(" ", strip=True) if block else "", re.I)
            if totals:
                if len(set(totals)) != 1:
                    raise ValueError(f"Ambiguous totals within document list: {url}")
                zone = block.find_parent(id=True)
                if not zone:
                    raise ValueError(f"Document list lacks stable zone: {url}")
                item["inventory_id"] = url.split("?")[0] + "#" + zone["id"]
                item["inventory_total"] = int(totals[0][2])
            docs.setdefault(target, item)
        else:
            raise ValueError(f"Unrecognized content link: {target}")
    if not pages and not docs:
        raise ValueError(f"PGOU collection page has no content: {url}")
    return list(pages.values()), list(docs.values())


def parse_stages(html: str) -> list[dict]:
    pages, docs = parse_page(html, SOURCE)
    if docs:
        raise ValueError("PGOU index structure changed; review direct documents")
    stages = {}
    for page in pages:
        match = re.fullmatch(r"Aprobación (inicial|provisional|definitiva) del PGOU",
                             page["titulo"], re.I)
        if not match:
            raise ValueError(f"Unrecognized PGOU stage: {page['titulo']}")
        stage = match[1].lower()
        if stage in stages and stages[stage]["url"] != page["url"]:
            raise ValueError(f"Ambiguous PGOU stage: {stage}")
        stages[stage] = {**page, "fase": "aprobación " + stage}
    if "inicial" not in stages or "provisional" not in stages:
        raise ValueError("Reviewed initial/provisional PGOU stages missing")
    return list(stages.values())


class IgorreAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get("capture_dir")
        sources = []
        cache = {}
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-igorre/1.0 (public PGOU inventory)"

            def fetch(url):
                if url in cache:
                    return cache[url]
                if len(sources) >= 100:
                    raise ValueError("PGOU collection exceeded page guard; no partial output written")
                time.sleep(0.15)
                response = session.get(url, timeout=35)
                response.raise_for_status()
                if canonical(response.url) != url or "text/html" not in response.headers.get("Content-Type", ""):
                    raise ValueError(f"Unexpected collection response: {url}")
                if len(response.content) > 5_000_000:
                    raise ValueError(f"Oversized collection page: {url}")
                if captures:
                    directory = Path(captures)
                    directory.mkdir(parents=True, exist_ok=True)
                    name = "page-" + hashlib.sha256(url.encode()).hexdigest()[:12] + ".html"
                    (directory / name).write_bytes(response.content)
                sources.append(url)
                cache[url] = response.text
                return response.text

            stages = parse_stages(fetch(SOURCE))
            documents = {}
            inventories = {}
            for stage in stages:
                queue = deque([stage["url"]])
                visited = set()
                stage_docs = set()
                while queue:
                    url = queue.popleft()
                    if url in visited:
                        continue
                    visited.add(url)
                    pages, docs = parse_page(fetch(url), url)
                    queue.extend(p["url"] for p in pages if p["url"] not in visited)
                    for doc in docs:
                        if "inventory_id" in doc:
                            inv = inventories.setdefault(doc["inventory_id"], {"total": doc["inventory_total"], "urls": set()})
                            if inv["total"] != doc["inventory_total"]:
                                raise ValueError("Inventory total changed during extraction; retry snapshot")
                            inv["urls"].add(doc["url"])
                        stage_docs.add(doc["url"])
                        record = documents.setdefault(doc["url"], {"titulo": doc["titulo"], "url": doc["url"], "procedencias": []})
                        provenance = {"pagina_origen": url, "fase": stage["fase"], "titulo_en_fuente": doc["titulo"]}
                        if provenance not in record["procedencias"]:
                            record["procedencias"].append(provenance)
                if not stage_docs:
                    raise ValueError(f"PGOU stage has no documents: {stage['url']}")
                stage["document_count"] = len(stage_docs)
            for key, inventory in inventories.items():
                if len(inventory["urls"]) != inventory["total"]:
                    raise ValueError(f"Incomplete document inventory: {key}: {len(inventory['urls'])}/{inventory['total']}")
        latest = max(stages, key=lambda s: {
            "aprobación inicial": 0, "aprobación provisional": 1, "aprobación definitiva": 2
        }[s["fase"]])["fase"]
        row = {
            "id": "igorre-proy-pgou", "municipio": "Igorre", "codigo_ine": "48094",
            "provincia": "Bizkaia", "titulo": "Plan General de Ordenación Urbana de Igorre (PGOU)",
            "tipo": "planeamiento_urbanistico", "fase": latest,
            "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
            "url": SOURCE, "source": "ayuntamiento", "origen": "coleccion_documental_pgou",
            "descripcion": "Instrumento municipal del PGOU; documentos de sus fases agrupados en un único registro.",
            "fases_documentadas": stages,
            "documentos": sorted(documents.values(), key=lambda d: d["url"]),
            "source_urls": sources, "limitaciones": LIMITATIONS,
            "lat": None, "lon": None, "geometry": None,
            "geometry_status": "unavailable", "publication_ready": False,
        }
        self._write(out_jsonl, [row])
        return {"status": "ok", "rows": 1, "documents": len(documents), "source_urls": sources,
                "pagination_validation": {k: {"expected": v["total"], "extracted": len(v["urls"])} for k, v in inventories.items()},
                "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current document snapshot; no date-based incremental cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
