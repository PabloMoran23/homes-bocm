"""Beniel's public transparency planning inventory (read-only JS literals)."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://sede.beniel.regiondemurcia.es"


def category_url(identifier: str) -> str:
    token = base64.b64encode(f"Ayuntamiento de Beniel@@@{identifier}".encode()).decode()
    return f"{BASE}/web/transparencia/{token}/30010"


INVENTORY = category_url("34")


def document_url(identifier: str) -> str:
    return BASE + "/web/transparencia.do?" + urlencode(
        {"opcion": "6", "entidad": "30010", "idioma": "1", "idDoc": identifier}
    )


def parse_page(html: str) -> tuple[list[dict], list[dict]]:
    """Decode only the portal's quoted HTML strings; never evaluate JavaScript."""
    if "tablaDocumentosEnlaces" not in html or "Ayuntamiento de Beniel" not in html:
        raise ValueError("Missing Beniel transparency inventory")
    folders_html = "".join(json.loads(m) for m in re.findall(
        r'html_epigrafes\s*\+=\s*("(?:[^"\\]|\\.)*")\s*;', html
    ))
    docs_html = "".join(json.loads(m) for m in re.findall(
        r'jQuery\("#tablaDocumentosEnlaces > tbody"\)\.append\(("(?:[^"\\]|\\.)*")\);', html
    ))
    fragment = BeautifulSoup(folders_html + docs_html, "html.parser")
    # The catalogue/search pagination elsewhere in the page is unrelated.
    for a in fragment.select("a"):
        if a.get("rel") == ["next"] or a.get_text(" ", strip=True).lower() in {
            "siguiente", "next", "»", "›"
        }:
            raise ValueError("Planning pagination requires crawler review")
    if re.search(r'html_epigrafes.*(?:pagin|siguiente)', html, re.I):
        raise ValueError("Unreviewed planning pagination")
    folders, docs = [], []
    for a in fragment.select("a"):
        onclick = a.get("onclick", "")
        folder = re.fullmatch(r"pulsaEpigrafe\((\d+)\)", onclick)
        doc = re.fullmatch(r"verDoc\((\d+)\)", onclick)
        if folder:
            heading = a.select_one("h4")
            badge = heading.select_one(".badge") if heading else None
            if not badge or not badge.get_text(strip=True).isdigit():
                raise ValueError("Missing folder inventory count")
            count = int(badge.get_text(strip=True))
            badge.decompose()
            title = re.sub(r"^\d+(?:\.\d+)*\.?\s*", "", heading.get_text(" ", strip=True))
            folders.append({"id": folder[1], "titulo": title, "count": count})
        elif doc:
            docs.append({"id": doc[1], "titulo": a.get_text(" ", strip=True),
                         "url": document_url(doc[1])})
        else:
            raise ValueError("Unrecognized inventory link; refusing partial extraction")
    if len({f['id'] for f in folders}) != len(folders):
        raise ValueError("Duplicate inventory folders")
    if set(re.findall(r'pulsaEpigrafe\((\d+)\)', html)) != {f['id'] for f in folders}:
        raise ValueError("Unparsed planning folders; refusing partial extraction")
    if set(re.findall(r'verDoc\((\d+)\)', html)) != {d['id'] for d in docs}:
        raise ValueError("Unparsed document links; refusing partial extraction")
    return folders, docs


def parse_instrument(folder: dict, html: str) -> dict:
    children, docs = parse_page(html)
    if children or not docs or len(docs) != folder["count"]:
        raise ValueError("Incomplete or changed instrument document inventory")
    if len({d['id'] for d in docs}) != len(docs):
        raise ValueError("Duplicate document IDs")
    if not re.match(r"^(MODIFICACI[ÓO]N PUNTUAL|ESTUDIO DE DETALLE|PLAN GENERAL)\b",
                    folder["titulo"], re.I):
        raise ValueError("Unreviewed planning instrument type")
    return {"id": "beniel-plan-" + folder["id"], "municipio": "Beniel",
            "codigo_ine": "30010", "provincia": "Murcia", "titulo": folder["titulo"],
            "tipo": "planeamiento_urbanistico", "source": "ayuntamiento",
            "origen": "inventario_planeamiento_transparencia", "url": category_url(folder["id"]),
            "inventory_url": INVENTORY, "documentos": docs,
            "publication_ready": False, "geometry_status": "unavailable"}


class BenielAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session: requests.Session, url: str) -> str:
        response = session.get(url, timeout=40)
        response.raise_for_status()
        if urlparse(response.url).hostname != urlparse(BASE).hostname:
            raise ValueError("Unexpected source redirect")
        capture_dir = self.config.get("capture_dir")
        if capture_dir:
            destination = Path(capture_dir)
            destination.mkdir(parents=True, exist_ok=True)
            name = "inventory" if url == INVENTORY else url.split("/")[-2]
            (destination / (name + ".html")).write_text(response.text, encoding="utf-8")
        return response.text

    @staticmethod
    def _write(out_jsonl: Path, rows: list[dict]) -> None:
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-beniel/1.0 (public planning inventory)"
            folders, docs = parse_page(self._fetch(session, INVENTORY))
            if not folders or docs:
                raise ValueError("Changed planning inventory structure")
            rows = [parse_instrument(f, self._fetch(session, category_url(f["id"]))) for f in folders]
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "coverage": "current_transparency_planning_inventory",
                "documents": sum(len(r["documentos"]) for r in rows), "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified public granted-licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
