"""Andratx's official planning inventory; documents grouped by instrument.

This is a complete snapshot of the reviewed current-planning sections, not a
licence register. Dates in headings can refer to the underlying NNSS rather than
the amendment, so retain source text without assigning instrument dates.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://transparencia.andratx.es/t/planeamiento"
LIMITATIONS = [
    "Partial municipal coverage: official planning inventory only; no licence grants, procurement or news.",
    "NNSS 2007 section explicitly marked Derogades is excluded; no claim of complete historical coverage.",
    "Documents and translations are grouped under the inventory's instrument headings; NNSS refos and 2023 are one record.",
    "Inventory Fecha labels have unspecified meaning; all instrument publication/agreement/approval dates remain null.",
    "PDF contents are linked, not parsed; source headings are not independent verification of legal validity or execution.",
    "No verified vector geometry; the municipal viewer warns its planning regulations are no longer current.",
    "Updates refresh the complete inventory snapshot; no deletion or historical state tracking.",
]


def _norm(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _text(tag):
    return tag.get_text(" ", strip=True)


def _documents(table, section, heading):
    docs = []
    for cell in table.select("tbody td"):
        # The live source has tbody > td without tr; do not rely on browser repair.
        pending = []
        for tag in cell.find_all(["p", "a"]):
            if tag.name == "p":
                pending.append(_text(tag))
                continue
            url = requests.utils.requote_uri(urljoin(SOURCE, tag.get("href", "")))
            parts = urlsplit(url)
            if parts.hostname != "transparencia.andratx.es" or not parts.path.startswith("/storage/uploads/"):
                raise ValueError("Unexpected document link in planning table: " + url)
            titles = [p for p in pending if not p.startswith("Fecha :")]
            dates = [p for p in pending if p.startswith("Fecha :")]
            if not titles:
                raise ValueError("Document missing its source title")
            docs.append({"titulo": " ".join(titles), "url": url,
                         "fecha_fuente_texto": " ".join(dates) or None,
                         "seccion_fuente": section, "grupo_fuente": heading})
            pending = []
    if not docs:
        raise ValueError("Planning table has no source documents: " + heading)
    return docs


class AndratxAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html):
        soup = BeautifulSoup(html, "html.parser")
        title = soup.select_one("h1")
        if not title or _norm(_text(title)) != "planejament":
            raise ValueError("Missing official planning inventory")
        # No pagination exists in the reviewed inventory. Fail if one is added,
        # rather than silently returning just the first page.
        if soup.select(".pagination, .pager, a[rel~=next], [data-total-pages]"):
            raise ValueError("Pagination requires review before accepting a snapshot")
        for a in soup.select("a[href]"):
            if _norm(_text(a)) in {"siguiente", "seguent", "next", "mes", "cargar mas", "veure mes"}:
                raise ValueError("Possible inventory continuation requires review")
        records = {}
        seen = set()
        for panel in soup.select(".panel"):
            h = panel.select_one(".panel-title")
            if not h:
                raise ValueError("Planning panel without title")
            section = _text(h)
            match = re.match(r"7\.1\.1\.([A-E])\b", section)
            code = match[1] if match else None
            management = bool(re.match(r"7\.2\.", section))
            if not code and not management:
                raise ValueError("Unreviewed planning section: " + section)
            seen.add(code or "management")
            if code == "D":
                if "derogades" not in _norm(section):
                    raise ValueError("Historical section no longer labelled repealed")
                continue
            tables = panel.select("table")
            if not tables:
                raise ValueError("Planning section lost its tables")
            for table in tables:
                heading_cell = table.select_one("tbody td")
                if heading_cell is None:
                    raise ValueError("Planning table lost heading")
                heading = _text(heading_cell)
                if code in {"A", "B"}:
                    key, name, kind = "nnss-2023", "Normes Subsidiàries de Planejament d'Andratx — 2023 i refós", "normas_subsidiarias"
                elif code == "C":
                    m = re.match(r"modificacio[n]? puntual num\.\s*(\d+)(?:\.([ab]))?(?:/(\d{4}))?\b", _norm(heading))
                    if not m:
                        raise ValueError("Unrecognised amendment grouping: " + heading)
                    number = m[1] + (m[2] or "")
                    key, name, kind = "mp-" + number, heading, "modificacion_planeamiento"
                elif code == "E":
                    key, name, kind = "ed-sant-elm-jaume-i-pantaleu", section, "estudio_detalle"
                else:
                    m = re.match(r"7\.2\.(\d+)\.\s*(.+)", heading)
                    if not m:
                        raise ValueError("Unrecognised management instrument: " + heading)
                    normalized = _norm(m[2])
                    if "expropiacio" in normalized:
                        kind = "proyecto_expropiacion"
                    elif "estudi de detall" in normalized:
                        kind = "estudio_detalle"
                    elif "junta de compensacio" in normalized:
                        kind = "instrumento_gestion_urbanistica"
                    else:
                        raise ValueError("Unreviewed management instrument: " + heading)
                    key, name = "gestion-" + m[1], heading
                row = records.setdefault(key, {
                    "id": "andratx-proy-" + key, "municipio": "Andratx",
                    "codigo_ine": "07005", "provincia": "Illes Balears",
                    "titulo": name, "tipo": kind, "fase": None,
                    "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None,
                    "fecha_aprob": None, "url": SOURCE, "source": "ayuntamiento",
                    "origen": "inventario_planeamiento_municipal",
                    "documentos": [], "grupos_fuente": [], "lat": None, "lon": None,
                    "geometry": None, "geometry_status": "unavailable", "publication_ready": False,
                })
                if row["tipo"] != kind:
                    raise ValueError("Instrument identifier reused with a different type")
                group = {"seccion": section, "titulo": heading}
                if group not in row["grupos_fuente"]:
                    row["grupos_fuente"].append(group)
                for doc in _documents(table, section, heading):
                    if doc["url"] not in {d["url"] for d in row["documentos"]}:
                        row["documentos"].append(doc)
        if seen != {"A", "B", "C", "D", "E", "management"} or not records:
            raise ValueError("Incomplete or changed planning inventory")
        return list(records.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=45, headers={"User-Agent": "municipio-andratx/1.0"})
        response.raise_for_status()
        if urlsplit(response.url).hostname != "transparencia.andratx.es":
            raise ValueError("Planning inventory redirected off the official host")
        response.encoding = "utf-8"
        rows = self.parse_projects(response.text)
        capture_dir = self.config.get("capture_dir")
        if capture_dir:
            capture = Path(capture_dir)
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "planeamiento.html").write_bytes(response.content)
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": [SOURCE],
                "documents": sum(len(r["documentos"]) for r in rows), "limitations": LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0, "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
