"""Sant Llorenç planning dossiers in the official CAIB environmental inventory.

Only strategic (E) planning instruments are covered. An environmental document
publication is neither a municipal approval nor evidence of a granted licence.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPIO = "Sant Llorenç des Cardassar"
ROOT = "https://www.caib.es/sites/serveiassessoramentambiental/ca/"
SOURCES = (
    (ROOT + "publicacio_de_documents_ambientals_en_tramitacia_davaluacia_simplificada/", "simplificada"),
    (ROOT + "publicacia_de_documents_inicials_en_tramitacia_davaluacia_ordinaria/", "ordinaria"),
)
LIMITATIONS = [
    "Cobertura parcial: instrumentos urbanísticos estratégicos (expedientes E) de los dos inventarios CAIB; no registro municipal completo.",
    "Publicación de documentación ambiental, no prueba de aprobación urbanística ni de vigencia o de consulta todavía abierta.",
    "Fechas de publicación y acuerdo no expuestas en estas páginas: se dejan nulas; el año del expediente no es una fecha de aprobación.",
    "Sin geometría vectorial vinculada verificada; planos documentales conservados, sin coordenadas inferidas.",
    "Licencias deshabilitadas; formularios, contratos y proyectos de evaluación de impacto (A) excluidos.",
]


def _norm(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _reference(title):
    match = re.match(r"^(\d+)e/(\d{4})\b", title, re.I)
    return f"{int(match[1])}e/{match[2]}" if match else None


def _municipal(title):
    return bool(re.search(r"\bsant llorenc des cardassar\b", _norm(title)))


def _official(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname == "www.caib.es"


def _content(html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main .imc--contenido-html")
    if main is None or main.select_one("h1") is None:
        raise ValueError("CAIB content container/title missing")
    # Reviewed inventories are complete single pages, without a row cap. Fail
    # rather than silently accepting page 1 if the publisher adds pagination.
    if soup.select_one('[rel~="next"], .pagination, .paginacion, .paginacio, .pager, [class*="paginador"]'):
        raise ValueError("CAIB pagination requires crawler review")
    for a in main.select("a[href]"):
        if _norm(a.get_text(" ", strip=True)) in {"seguent", "siguiente", "next", "mes", ">", "»"}:
            raise ValueError("CAIB pagination requires crawler review")
    return main


def parse_inventory(html, source_url):
    main = _content(html)
    if not any(word in _norm(main.h1.get_text(" ", strip=True)) for word in ("simplificada", "ordinaria")):
        raise ValueError("Unexpected CAIB inventory title")
    found = {}
    for a in main.select("a[href]"):
        title = a.get_text(" ", strip=True)
        ref = _reference(title)
        if not ref or not _municipal(title):
            continue
        if not re.search(r"\b(?:mp|m\.p\.|delimitacio|modificacio|pla|planejament)\b", _norm(title)):
            raise ValueError(f"Unreviewed strategic instrument: {title}")
        url = urljoin(source_url, a["href"])
        if not _official(url):
            raise ValueError("Planning detail points outside official host")
        item = {"expediente": ref, "titulo_inventario": title, "url_descubrimiento": url}
        if ref in found and found[ref] != item:
            raise ValueError(f"Conflicting inventory entries for {ref}")
        found[ref] = item
    return list(found.values())


def parse_detail(html, detail_url, item, source_url, procedure):
    main = _content(html)
    title = main.h1.get_text(" ", strip=True)
    if _reference(title) != item["expediente"] or not _municipal(title):
        raise ValueError("Detail municipality/reference differs from inventory")
    documents = {}
    for a in main.select("a[href]"):
        url = urljoin(detail_url, a["href"])
        parsed = urlparse(url)
        # Only attachments inside the dossier content, never navigation links.
        is_document = (parsed.path.endswith("/archivopub.do")
                       or "/f/" in parsed.path or parsed.path.lower().endswith(".pdf"))
        if not is_document:
            raise ValueError(f"Unreviewed detail link: {url}")
        if not _official(url):
            raise ValueError("Document points outside official host")
        query = parse_qs(parsed.query)
        document_id = query.get("id", [None])[0]
        key = document_id or url
        documents.setdefault(key, {"id_origen": document_id,
                                   "titulo": a.get_text(" ", strip=True), "url": url,
                                   "url_procedencia": detail_url})
    if not documents:
        raise ValueError("Planning dossier has no source documents")
    ref = item["expediente"]
    return {
        "id": "sant-llorenc-des-cardassar-plan-" + ref.replace("/", "-"),
        "municipio": MUNICIPIO, "codigo_ine": "07051", "provincia": "Illes Balears",
        "titulo": title, "titulo_inventario": item["titulo_inventario"],
        "discrepancia_titulo": _norm(title) != _norm(item["titulo_inventario"]),
        "tipo": "planeamiento urbanístico", "expediente": ref,
        "fase": None, "procedimiento_ambiental": procedure,
        "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
        "url": detail_url, "url_inventario": source_url,
        "url_descubrimiento": item["url_descubrimiento"],
        "source": "caib", "organismo_fuente": "Govern de les Illes Balears — Servei d'Avaluació Ambiental",
        "origen": "inventario_documentacion_ambiental_planeamiento",
        "documentos": list(documents.values()),
        "lat": None, "lon": None, "geometry": None,
        "geometry_status": "unavailable", "publication_ready": False,
        "limitaciones": LIMITATIONS,
    }


class SantLlorencDesCardassarAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or "https://www.caib.es")

    def _fetch(self, session, url):
        if not _official(url):
            raise ValueError("Unexpected source host")
        with session.get(url, timeout=(15, 45), stream=True) as response:
            response.raise_for_status()
            if not _official(response.url):
                raise ValueError("Unexpected redirect host")
            payload = bytearray()
            for chunk in response.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > 5_000_000:
                    raise ValueError("CAIB HTML response exceeds size bound")
            html = payload.decode("utf-8-sig")
            capture_dir = self.config.get("capture_dir")
            if capture_dir:
                directory = Path(capture_dir)
                directory.mkdir(parents=True, exist_ok=True)
                name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".html"
                (directory / name).write_text(html, encoding="utf-8")
            return html, response.url

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl):
        rows = {}
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-sant-llorenc-des-cardassar/1.0"
            for source_url, procedure in SOURCES:
                html, effective_source = self._fetch(session, source_url)
                for item in parse_inventory(html, effective_source):
                    time.sleep(0.3)
                    detail, effective_url = self._fetch(session, item["url_descubrimiento"])
                    row = parse_detail(detail, effective_url, item, effective_source, procedure)
                    ref = row["expediente"]
                    if ref in rows:
                        # Avoid merging distinct versions/procedures without review.
                        raise ValueError(f"Instrument appears in multiple inventories: {ref}")
                    rows[ref] = row
        if not rows:
            raise ValueError("No municipal planning dossiers found; review source coverage")
        self._write(out_jsonl, sorted(rows.values(), key=lambda row: row["id"]))
        return {"status": "ok", "rows": len(rows), "source_urls": [url for url, _ in SOURCES],
                "limitations": LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh both complete inventories; no date watermark assumptions."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
