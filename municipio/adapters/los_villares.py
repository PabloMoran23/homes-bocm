"""Los Villares (Jaén): current municipal planning document inventory."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://www.losvillares.com/ayuntamiento/urbanismo/"


def _normal(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().split())


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    """One instrument per heading, retaining every document and its source label.

    Dates and phase are deliberately absent: table labels describe documents,
    and the CMS does not expose agreement/publication dates in this inventory.
    """
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".entry-content")
    if content is None:
        raise ValueError("Municipal inventory content missing")
    pagination = soup.select('a[rel~="next"], link[rel~="next"], .pagination a[href], .nav-links a[href], a.next[href]')
    pagination += [a for a in content.select("a[href]") if (
        _normal(a.get_text(" ", strip=True)) in {"siguiente", "siguiente pagina", "next", "»", ">"}
        or re.search(r"(?:/page/\d+|[?&](?:page|paged|offset)=)", a["href"])
    )]
    if any(a.get("href") not in {None, "", "#"} for a in pagination):
        raise ValueError("Inventory pagination detected; review crawler before extracting")
    records: dict[str, dict] = {}
    for table in content.select("table"):
        header = table.select_one("th")
        if not header:
            raise ValueError("Inventory table lacks a heading")
        title = header.get_text(" ", strip=True)
        normal = _normal(title)
        if normal in {"modelos", "formularios"}:
            continue
        if not re.match(r"^(?:innovacion de planeamiento|modificacion|estudio de detalle|plan (?:general|especial|parcial)|proyecto de)\b", normal):
            raise ValueError(f"Unreviewed inventory section: {title}")
        key = "los-villares-plan-" + hashlib.sha256(normal.encode()).hexdigest()[:16]
        row = records.setdefault(key, {
            "id": key, "municipio": "Los Villares", "codigo_ine": "23099",
            "provincia": "Jaén", "titulo": title, "tipo": "planeamiento_urbanistico",
            "source": "ayuntamiento", "origen": "inventario_municipal_urbanismo",
            "inventory_url": url, "documentos": [],
            "publication_ready": False, "geometry_status": "unavailable",
            "coverage": "current_document_inventory_partial",
        })
        documents = {doc["url"]: doc for doc in row["documentos"]}
        for a in table.select("td a[href]"):
            target = urljoin(url, a["href"])
            parsed = urlparse(target)
            if (parsed.scheme != "https" or parsed.hostname != "www.losvillares.com"
                    or not parsed.path.startswith("/wp-content/uploads/urbanismo/")
                    or not parsed.path.lower().endswith(".pdf")):
                raise ValueError(f"Unexpected planning document URL: {target}")
            label = a.get_text(" ", strip=True)
            doc = documents.setdefault(target, {"url": target, "titulo": label, "inventory_url": url})
            if label and not doc["titulo"]:
                doc["titulo"] = label
        if not documents or any(not doc["titulo"] for doc in documents.values()):
            raise ValueError(f"Instrument lacks labelled source documents: {title}")
        row["documentos"] = list(documents.values())
        row["url"] = row["documentos"][0]["url"]
    if not records:
        raise ValueError("No usable planning instruments in municipal inventory")
    return list(records.values())


class LosVillaresAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> dict:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)
        return {"count": len(rows), "written": len(rows), "coverage": "current_document_inventory_partial"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=40, headers={"User-Agent": "municipio-inventory/1.0"})
        response.raise_for_status()
        if urlparse(response.url)._replace(query="", fragment="") != urlparse(SOURCE):
            raise ValueError(f"Unexpected inventory redirect: {response.url}")
        return self._write(out_jsonl, parse_inventory(response.text, response.url))

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current snapshot; state is not used as an unsafe date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), "disabled": True,
                "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
