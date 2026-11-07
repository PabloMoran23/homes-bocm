"""Reviewed urban-planning subset of the municipal Benetússer 2030 catalogue."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = "https://www.benetusser2030.es/documentos/"


def _normal(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


# Scope is deliberately restricted to these four named urban instruments.
# Other catalogue entries cover social policy, emergencies, commerce, etc.
INSTRUMENTS = {
    "agenda-reconstruccion": (
        r"agenda urbana de reconstruccion de benetusser post-dana 2024",
        "agenda_urbana_reconstruccion",
    ),
    "pgou": (r"pgou plan general de ordenacion urbana \(1990\)", "PGOU"),
    "puam": (r"puam plan urbano de actuacion municipal 2022", "PUAM"),
    "emus": (r"emus programa de movilidad urbana sostenible 2018", "movilidad_urbana"),
}


class BenetusserAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or "https://www.benetusser2030.es")

    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        # This catalogue currently renders all entries in HTML accordions.
        # Refuse a changed/paginated inventory rather than publish page one.
        if soup.select('[rel~="next"], .pagination, .page-numbers, .nav-links, [data-next-page]'):
            raise ValueError("Catalogue pagination detected; crawler needs review")
        for control in soup.select("a[href], button"):
            if re.fullmatch(r"(?:siguiente(?: pagina)?|next(?: page)?|cargar mas|ver mas|load more)",
                            _normal(control.get_text(" ", strip=True))):
                raise ValueError("Catalogue continuation detected; crawler needs review")

        records = {}
        for block in soup.select(".toggle"):
            heading = block.select_one(".toggle-title")
            if heading is None:
                continue
            title = heading.get_text(" ", strip=True)
            match = next(((key, kind) for key, (pattern, kind) in INSTRUMENTS.items()
                          if re.fullmatch(pattern, _normal(title))), None)
            if match is None:
                continue
            key, kind = match
            documents = {}
            for anchor in block.select(".inner-toggle-wrap a[href]"):
                href = anchor["href"].strip()
                if not href or href.startswith("#"):
                    continue
                url = urljoin(SOURCE, href)
                parsed = urlparse(url)
                if parsed.scheme != "https" or parsed.hostname not in {
                    "www.benetusser2030.es", "www.benetusser.es",
                }:
                    raise ValueError(f"Unreviewed document origin: {url}")
                documents[url] = {
                    "titulo": anchor.get_text(" ", strip=True) or title,
                    "url": url,
                    "url_origen": SOURCE,
                    "tipo_enlace": "pdf" if parsed.path.lower().endswith(".pdf") else "pagina",
                }
            if not documents:
                raise ValueError(f"Instrument without document links: {title}")
            if key not in records:
                records[key] = {
                    "id": f"benetusser-proy-{key}",
                    "municipio": "Benetússer", "codigo_ine": "46054", "provincia": "Valencia",
                    "titulo": title, "tipo": kind, "fase": None,
                    "fecha": None, "fecha_publicacion": None,
                    "fecha_acuerdo": None, "fecha_aprob": None,
                    "url": SOURCE, "source": "ayuntamiento",
                    "origen": "catalogo_municipal_instrumentos_urbanos",
                    "documentos": [],
                    "cobertura": "Referencia del catálogo municipal; sin verificar vigencia jurídica, "
                                 "acuerdos, modificaciones ni ejecución de actuaciones.",
                    "lat": None, "lon": None, "geometry": None,
                    "publication_ready": False,
                }
            known = {doc["url"] for doc in records[key]["documentos"]}
            records[key]["documentos"].extend(doc for url, doc in documents.items() if url not in known)
        if records.keys() != INSTRUMENTS.keys():
            missing = sorted(INSTRUMENTS.keys() - records.keys())
            raise ValueError(f"Reviewed catalogue instruments missing: {missing}")
        return [records[key] for key in sorted(records)]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=40, stream=True, headers={
            "User-Agent": self.config.get("user_agent", "municipio-benetusser/1.0"),
        }) as response:
            response.raise_for_status()
            if response.url.rstrip("/") != SOURCE.rstrip("/"):
                raise ValueError(f"Unexpected catalogue redirect: {response.url}")
            if "text/html" not in response.headers.get("Content-Type", "").lower():
                raise ValueError("Catalogue did not return HTML")
            payload = bytearray()
            for chunk in response.iter_content(65536):
                payload.extend(chunk)
                if len(payload) > 3_000_000:
                    raise ValueError("Catalogue exceeds reviewed response size")
            html = payload.decode("utf-8")
        rows = self.parse_inventory(html)
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": [SOURCE],
                "coverage": "four reviewed urban instruments in municipal catalogue",
                "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Complete catalogue snapshot; no unsupported date-based incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0, "reason": "No verified granted-licence inventory"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
