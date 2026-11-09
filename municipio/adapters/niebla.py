"""Niebla's live PGOU document inventory; versions are one instrument."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://www.niebla.es/es/descargas/"
GALLERY_ROOT = "/export/sites/niebla/es/.galleries/"
VERSIONS = {
    "PGOU_FIRMADO": "aprobacion_inicial_2023",
    "PGOU_11_2023": "modificaciones_telecomunicaciones_2023",
    "PGOU_APROBACION_PROVISIONAL_2024": "aprobacion_provisional_2024",
}
LIMITATIONS = [
    "Solo documentos del PGOU enlazados en Descargas; no censo completo de obras o planeamiento.",
    "Las versiones son etiquetas del inventario, no prueba de vigencia o aprobación definitiva.",
    "Sin fechas de acuerdo o publicación inferidas de nombres de archivos o fechas del CMS.",
    "Sin coordenadas, licencias concedidas ni extracción del contenido de todos los PDF.",
]


def page_url(number: int) -> str:
    return SOURCE if number == 1 else SOURCE + "?" + urlencode({"pagedownloadgallery": number})


def parse_inventory(html: str, url: str) -> tuple[list[dict], set[int]]:
    """Read all rendered tabs, not only the active tab; discover every page."""
    soup = BeautifulSoup(html, "html.parser")
    if not any("PGOU" in h.get_text().upper() for h in soup.select("h2.title")):
        raise ValueError("PGOU inventory headings missing")
    pages = {1}
    controls = soup.select('.pagination a[href], a[rel~="next"], a.pagelink[href]')
    for a in controls:
        href = a.get("href", "")
        if not href or href.startswith("#"):
            continue
        target = urlparse(urljoin(url, href))
        query = parse_qs(target.query)
        if (target.scheme != "https" or target.netloc != "www.niebla.es"
                or target.path != "/es/descargas/"
                or set(query) != {"pagedownloadgallery"}):
            raise ValueError(f"Unreviewed pagination: {href}")
        values = query["pagedownloadgallery"]
        if len(values) != 1 or not values[0].isdigit():
            raise ValueError(f"Invalid pagination: {href}")
        number = int(values[0])
        if not 1 <= number <= 100:
            raise ValueError("Pagination exceeds safety bound; no partial output written")
        pages.update(range(1, number + 1))
    # Catch newly introduced navigation outside the reviewed pagination widgets.
    for a in soup.select("a[href]"):
        if "pagedownloadgallery=" in a["href"] and a not in controls:
            raise ValueError("Unrecognized gallery pagination control")
    requested = int(parse_qs(urlparse(url).query).get("pagedownloadgallery", ["1"])[0])
    active = soup.select(".pagination .active a[href]")
    if active and not any(
        parse_qs(urlparse(a["href"]).query).get("pagedownloadgallery") == [str(requested)]
        for a in active
    ):
        raise ValueError("Server did not return the requested gallery page")

    documents = []
    for a in soup.select("a[href]"):
        target = urlparse(urljoin(url, a["href"]))
        if not target.path.startswith(GALLERY_ROOT + "PGOU"):
            continue
        if target.scheme != "https" or target.netloc != "www.niebla.es":
            raise ValueError("Unexpected PGOU document host")
        gallery = target.path[len(GALLERY_ROOT):].split("/", 1)[0]
        if gallery not in VERSIONS or not target.path.lower().endswith(".pdf"):
            raise ValueError("Unreviewed PGOU document family or format")
        title = a.get_text(" ", strip=True)
        if not title:
            raise ValueError("Untitled PGOU document")
        # The nearest enclosing section with its own h2 is the document's source label.
        section = next((p for p in a.parents if p.select_one("h2.title")), None)
        heading = section.select_one("h2.title") if section else None
        if heading is None or "PGOU" not in heading.get_text().upper():
            raise ValueError("Document is outside a named PGOU section")
        documents.append({
            "titulo": title,
            "url": urlunparse(target._replace(fragment="")),
            "version": VERSIONS[gallery],
            "ruta_documental": target.path[len(GALLERY_ROOT):],
            "seccion_fuente": heading.get_text(" ", strip=True),
            "inventory_urls": [url],
        })
    if not documents:
        raise ValueError("No supported PGOU documents; refusing an empty snapshot")
    return documents, pages


def group_instrument(documents: list[dict], source_urls: list[str]) -> dict:
    by_url = {}
    for doc in documents:
        if doc["url"] not in by_url:
            by_url[doc["url"]] = {**doc, "inventory_urls": list(doc["inventory_urls"])}
        else:
            existing = by_url[doc["url"]]["inventory_urls"]
            existing.extend(u for u in doc["inventory_urls"] if u not in existing)
    if not by_url:
        raise ValueError("Cannot create an instrument without source documents")
    return {
        "id": "niebla-pgou", "municipio": "Niebla", "provincia": "Huelva",
        "codigo_ine": "21053", "titulo": "Plan General de Ordenación Urbanística de Niebla",
        "tipo": "planeamiento_urbanistico", "source": "ayuntamiento",
        "origen": "inventario_documental_pgou", "url": SOURCE,
        "source_urls": source_urls,
        "documentos": sorted(by_url.values(), key=lambda d: d["url"]),
        "coverage": "inventario_documental_parcial", "limitations": LIMITATIONS,
        "publication_ready": False, "geometry_status": "unavailable",
    }


class NieblaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        pending, visited, documents = {1}, set(), []
        capture_dir = self.config.get("capture_dir")
        verify = self.config.get("tls_verify", True)
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-niebla-inventory/1.0"
            while pending:
                number = min(pending)
                pending.remove(number)
                url = page_url(number)
                response = session.get(url, timeout=45, verify=verify)
                response.raise_for_status()
                if response.url != url:
                    raise ValueError(f"Unexpected inventory redirect: {response.url}")
                if capture_dir:
                    capture = Path(capture_dir)
                    capture.mkdir(parents=True, exist_ok=True)
                    (capture / f"descargas-{number}.html").write_bytes(response.content)
                docs, pages = parse_inventory(response.text, url)
                documents.extend(docs)
                visited.add(number)
                pending.update(pages - visited)
        urls = [page_url(n) for n in sorted(visited)]
        row = group_instrument(documents, urls)
        row["tls_verified"] = verify is not False
        self._write(out_jsonl, [row])
        return {"count": 1, "written": 1, "documents": len(row["documentos"]),
                "source_urls": urls, "limitations": LIMITATIONS,
                "tls_verified": verify is not False, "coverage": row["coverage"]}

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Reconcile the complete current inventory; dates cannot support an incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
