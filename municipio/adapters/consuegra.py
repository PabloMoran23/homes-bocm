"""Municipal NNSS document inventory; one instrument, not one project per map."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://aytoconsuegra.es/normas-subsidiarias/"


class ConsuegraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        main = soup.select_one("main")
        if main is None:
            raise ValueError("Missing municipal inventory content")
        if main.select(".pagination, .page-links, a[rel~=next], a[rel~=prev]"):
            raise ValueError("Paginated inventory requires crawler review")
        for a in main.select("a[href]"):
            if a.get_text(" ", strip=True).lower() in {"siguiente", "anterior", "next", "previous"}:
                raise ValueError("Paginated inventory requires crawler review")
        inventories = [ol for ol in main.select("ol")
                       if "Normas Subsidiarias Consuegra" in ol.get_text(" ", strip=True)]
        if len(inventories) != 1:
            raise ValueError("Missing or ambiguous NNSS document inventory")
        documents = []
        for item in inventories[0].find_all("li", recursive=False):
            anchors = item.select("a[href]")
            labelled = [a for a in anchors if a.get_text(" ", strip=True)]
            if not labelled:
                raise ValueError("Inventory document lacks a descriptive link")
            title = labelled[0].get_text(" ", strip=True)
            if not title.startswith(("Normas Subsidiarias Consuegra", "Plano")):
                raise ValueError("Unreviewed document type in NNSS inventory")
            urls = []
            # Text links take precedence over icon links. Retain distinct icon
            # targets too: the municipal-boundary map has a Dropbox alternative.
            for a in labelled + anchors:
                url = urljoin(SOURCE, a["href"])
                parsed = urlparse(url)
                if parsed.scheme != "https" or parsed.hostname not in {
                    "drive.google.com", "www.dropbox.com", "aytoconsuegra.es"
                }:
                    raise ValueError("Unreviewed document host in municipal inventory")
                if url not in urls:
                    urls.append(url)
            document = {"titulo": title, "url": urls[0], "urls": urls,
                        "source_url": SOURCE, "provenance": "enlace del inventario municipal"}
            if document not in documents:
                documents.append(document)
        texts = [d for d in documents if d["titulo"].startswith("Normas Subsidiarias Consuegra")]
        if len(texts) != 1 or not any(d["titulo"].startswith("Plano") for d in documents):
            raise ValueError("NNSS inventory lacks its text or supporting maps")
        return [{
            "id": "consuegra-planeamiento-normas-subsidiarias",
            "municipio": "Consuegra", "provincia": "Toledo", "codigo_ine": "45053",
            "titulo": texts[0]["titulo"], "tipo": "planeamiento_urbanistico",
            "source_entity_type": "normativa",
            "url": SOURCE, "url_documento": texts[0]["url"],
            "source": "ayuntamiento", "origen": "inventario_municipal_nnss",
            "documentos": documents,
            "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
            "geometry": None, "lat": None, "lon": None,
            "geometry_status": "unavailable", "publication_ready": False,
            "cobertura": "Parcial: inventario municipal de NNSS y planos; no incluye modificaciones ni otros expedientes.",
            "notas": "La referencia 9/2014 es la etiqueta de versión del texto refundido, no una fecha de aprobación o publicación. Vigencia jurídica no comprobada.",
        }]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={"User-Agent": "municipio-consuegra/1.0"})
        response.raise_for_status()
        if response.url.rstrip("/") != SOURCE.rstrip("/"):
            raise ValueError("Municipal inventory redirected to a different page")
        rows = self.parse_inventory(response.text)
        capture_dir = self.config.get("capture_dir")
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "normas-subsidiarias.html").write_text(response.text, encoding="utf-8")
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": [SOURCE], "coverage": "partial"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
