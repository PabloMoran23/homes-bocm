"""Snapshot of the two official Huétor Vega planning document inventories.

Inventory labels are evidence of documents, not of a plan's present legal status.
PDF contents, including agreement dates, are not automatically interpreted.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


BASE = "https://huetorvega.org"
NNSS = BASE + "/normas-subsidiarias-nnss/"
ADAPTACION = BASE + "/pgou-adaptacion-parcial-nnss/"
SOURCES = (NNSS, ADAPTACION)
MONTHS = dict(zip(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(),
    range(1, 13),
))
LIMITATIONS = [
    "Partial coverage: only the two municipal planning document inventories; not all municipal projects or the complete planning history.",
    "PDF links retained with municipal labels; PDF agreement dates and current legal validity are not inferred.",
    "BOP dates in inventory labels are publication dates, never agreement dates or upload dates.",
    "No verified granted-licence inventory or project vector geometry; coordinates remain null.",
]


def _publication(label: str) -> str | None:
    match = re.search(r"BOP\b.*?\bde\s+(\d{1,2})\s+(?:de\s+)?(\w+)\s+(?:de\s+)?(\d{4})", label, re.I)
    if not match:
        return None
    return date(int(match[3]), MONTHS[match[2].lower()], int(match[1])).isoformat()


def _record(key: str, title: str, source: str, docs: list[dict], **extra) -> dict[str, Any]:
    return {
        "id": "huetor-vega-proy-" + hashlib.sha256(key.encode()).hexdigest()[:16],
        "municipio": "Huétor Vega", "codigo_ine": "18101", "provincia": "Granada",
        "titulo": title, "tipo": "planeamiento_urbanistico",
        "url": source, "url_documento": docs[0]["url"], "documentos": docs,
        "source": "ayuntamiento", "origen": "inventario_municipal_planeamiento",
        "source_entity_type": "documento",
        "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None,
        "fecha_aprob": None, "fase": None,
        "lat": None, "lon": None, "geometry": None, "publication_ready": False,
        "geometry_status": "No verified project geometry extracted",
        **extra,
    }


class HuetorVegaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or BASE)

    @staticmethod
    def parse_inventory(html: str, source: str) -> list[dict[str, Any]]:
        if source not in SOURCES:
            raise ValueError("Unsupported municipal inventory")
        soup = BeautifulSoup(html, "html.parser")
        if soup.select('[rel~="next"], .pagination a[href], a.page-numbers[href], .post-page-numbers, .wp-block-query-pagination a[href]') or any(
            a.get_text(" ", strip=True).lower() in {"siguiente", "siguiente página", "next"}
            and a.get("href") not in {None, "", "#"} for a in soup.select("a[href]")
        ):
            raise ValueError("Pagination detected: extend traversal before extracting this inventory")
        content = soup.select_one(".entry-content")
        heading = soup.select_one("h2.entry-title")
        expected = "Normas Subsidiarias" if source == NNSS else "PGOU Adaptación parcial NNSS"
        if not content or not heading or expected not in heading.get_text(" ", strip=True):
            raise ValueError("Missing verified municipal planning content")
        groups: dict[str, list[dict]] = {}
        section = None
        nnss_sections = {"DOCUMENTACIÓN INICIAL 2002", "PLANOS INICIALES 2002", "MODIFICACIONES NNSS 2002", "PLANOS ACTUALES NN.SS. 2002"}
        allowed = nnss_sections if source == NNSS else {"DOCUMENTACIÓN", "PLANOS"}
        seen = set()
        for table in content.select("table"):
            headers = table.select("th")
            if headers:
                section = " ".join(headers[0].get_text(" ", strip=True).split())
            if section not in allowed:
                raise ValueError("Unrecognized planning section")
            for anchor in table.select("a[href]"):
                label = " ".join(anchor.get_text(" ", strip=True).split())
                url = urljoin(source, anchor["href"])
                parsed = urlparse(url)
                if not label or parsed.scheme != "https" or parsed.hostname != "huetorvega.org" or not parsed.path.startswith("/wp-content/uploads/") or not parsed.path.lower().endswith(".pdf"):
                    raise ValueError("Unrecognized planning attachment")
                doc = {"titulo": label, "url": url, "seccion": section, "url_procedencia": source}
                if (section, url, label) not in seen:
                    groups.setdefault(section, []).append(doc)
                    seen.add((section, url, label))
        # Every link in the content must be accounted for, including new layouts.
        if len(content.select("a[href]")) != sum(len(t.select("a[href]")) for t in content.select("table")):
            raise ValueError("Planning links outside reviewed table layout")
        if set(groups) != allowed:
            raise ValueError("Incomplete municipal planning inventory")
        title = " ".join(heading.get_text(" ", strip=True).split())
        if source == ADAPTACION:
            docs = [doc for group in groups.values() for doc in group]
            return [_record(source, title, source, docs)]
        docs = [doc for section, group in groups.items() if section != "MODIFICACIONES NNSS 2002" for doc in group]
        rows = [_record(source, title, source, docs)]
        for doc in groups["MODIFICACIONES NNSS 2002"]:
            label = doc["titulo"]
            if not re.match(r"(?:Modificaci[oó]n|Innovaci[oó]n)", label, re.I):
                raise ValueError("Unsupported modification label")
            publication = _publication(label)
            if publication is None:
                raise ValueError("Modification lacks explicit BOP publication date")
            # One BOP contains three separate instruments. Share the document,
            # but preserve each numbered modification as a distinct record.
            numbers = re.search(r"Modificaciones puntuales nº\s*(\d+(?:-\d+)+)\.", label, re.I)
            suffixes = numbers[1].split("-") if numbers else [None]
            for number in suffixes:
                instrument_title = f"Modificación puntual nº {number} de las NN.SS. 2002" if number else label.split(" BOP")[0].strip()
                rows.append(_record(
                    doc["url"] + ("#modificacion-" + number if number else ""),
                    instrument_title, source, [doc], fecha_publicacion=publication,
                    descripcion=label,
                ))
        return rows

    def _fetch(self, url: str) -> str:
        with requests.get(url, timeout=40, stream=True, headers={
            "User-Agent": self.config.get("user_agent", requests.utils.default_user_agent()),
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname != "huetorvega.org":
                raise ValueError("Unexpected inventory redirect")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError("Municipal inventory exceeds response size limit")
            if self.config.get("capture_dir"):
                capture = Path(self.config["capture_dir"])
                capture.mkdir(parents=True, exist_ok=True)
                (capture / (urlparse(url).path.strip("/") + ".html")).write_bytes(data)
            return data.decode("utf-8-sig")

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = []
        for source in SOURCES:
            rows.extend(self.parse_inventory(self._fetch(source), source))
        ids = [row["id"] for row in rows]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate planning instrument identities")
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)
        return {"status": "ok", "rows": len(rows), "source_urls": list(SOURCES), "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        """Refresh both complete inventories; no time window or page limit."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return {"status": "disabled", "rows": 0, "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
