"""La Mojonera: municipal planning instruments in the Junta's EAE inventory.

Environmental procedure dates are not urban-planning approval dates. The public
inventory is partial; no granted licences or geometry are inferred.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

ROOT = "https://www.juntadeandalucia.es/medioambiente/daepu/resolucions"
INVENTORY = ROOT + "/find?" + urlencode({
    "find": "findResolucionesFiltered", "filter5": "MOJONERA", "page": 1, "size": 10,
})
LIMITATIONS = [
    "Inventario parcial de evaluación ambiental de instrumentos urbanísticos; no es el registro municipal completo.",
    "No acredita aprobación urbanística, vigencia, ejecución de obras ni concesión de licencias.",
    "Las fechas de resolución ambiental y de publicación se conservan por documento, sin inferir fecha de aprobación del plan.",
    "La web municipal del PGOU devuelve un control JavaScript en las peticiones directas verificadas.",
    "Sin coordenadas ni geometría verificadas; sin geocodificación.",
]


def text(node):
    return " ".join(node.get_text(" ", strip=True).split())


def norm(value):
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().upper().strip()


def official_url(base, href):
    url = re.sub(r";jsessionid=[^/?#;]+", "", urljoin(base, href), flags=re.I)
    parts = urlparse(url)
    if parts.scheme != "https" or parts.netloc != "www.juntadeandalucia.es" or not parts.path.startswith("/medioambiente/daepu/resolucions/"):
        raise ValueError("Unexpected EAE source URL: " + url)
    return url


def expediente(value):
    match = re.fullmatch(r"\(?\s*(EAE/AL/\d+/\d+)\s*\)?", value.strip(), re.I)
    if not match:
        raise ValueError("Unrecognised environmental expediente: " + value)
    return match[1].upper()


def iso_date(value):
    return datetime.strptime(value, "%d/%m/%Y").date().isoformat()


def parse_inventory(html, url):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None or [text(th) for th in table.select("thead th")] != [
        "Órgano Tramitador", "Actuación", "Provincia", "Otras Provincias", "Municipio",
        "Otros Municipios", "Tipo de Resolución", "Fecha de Resolución",
        "Número de Expediente", "Resoluciones y Otros Documentos (*)",
    ]:
        raise ValueError("EAE inventory structure missing or changed")
    paging = re.search(r"Página\s+(\d+)\s+de\s+(\d+)", text(table))
    if not paging:
        raise ValueError("Missing pagination metadata; refusing partial extraction")
    current, total = map(int, paging.groups())
    if not 1 <= current <= total:
        raise ValueError("Invalid pagination")
    rows = []
    for tr in table.select("tr"):
        if "footer" in tr.get("class", []):
            continue
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != 10:
            raise ValueError("Malformed inventory row")
        values = [text(c) for c in cells]
        if norm(values[2]) != "ALMERIA" or norm(values[4]) != "MOJONERA (LA)":
            raise ValueError("Municipal filter failed")
        link = cells[9].find("a", href=True)
        if not link or not values[1]:
            raise ValueError("Inventory record missing title or detail link")
        detail = official_url(url, link["href"])
        if not re.fullmatch(r"/medioambiente/daepu/resolucions/\d+", urlparse(detail).path):
            raise ValueError("Unexpected detail link")
        rows.append({"actuacion": values[1], "expediente": expediente(values[8]),
                     "tipo_resolucion": values[6], "fecha_resolucion_ambiental": iso_date(values[7]),
                     "url": detail, "organo_tramitador": values[0]})
    if not rows:
        raise ValueError("No planning instruments in EAE inventory")
    return rows, current, total


def parse_detail(html, url, expected_expediente):
    soup = BeautifulSoup(html, "html.parser")
    fields = {}
    for label in soup.select("label"):
        box = label.parent.select_one("div.box")
        if box:
            fields[text(label)] = text(box)
    if norm(fields.get("Provincia:", "")) != "ALMERIA" or norm(fields.get("Municipio:", "")) != "MOJONERA (LA)":
        raise ValueError("Detail is not La Mojonera, Almería")
    if expediente(fields.get("Número de Expediente:", "")) != expected_expediente:
        raise ValueError("Detail expediente mismatch")
    documents = []
    table = soup.find("table")
    if table is None or [text(th) for th in table.select("th")] != ["Tipo", "Fecha de Resolución", "Enlace al documento"]:
        raise ValueError("Missing document table")
    for tr in table.select("tr"):
        if "footer" in tr.get("class", []):
            continue
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != 3:
            raise ValueError("Malformed document row")
        links = cells[2].select("a[href]")
        if not links:
            raise ValueError("Document link missing")
        kind, date = text(cells[0]), iso_date(text(cells[1]))
        for a in links:
            target = official_url(url, a["href"])
            if "/downloadFile/" not in urlparse(target).path:
                raise ValueError("Unexpected document endpoint")
            doc = {"tipo": kind, "url": target, "source_url": url,
                   "fecha_resolucion_fuente": date}
            doc["fecha_publicacion" if kind == "Publicación en BOJA (PB)" else "fecha_resolucion_ambiental"] = date
            documents.append(doc)
    if not documents:
        raise ValueError("No associated documents")
    return documents


def group_instruments(entries):
    grouped = {}
    for entry, docs in entries:
        ref = entry["expediente"]
        if ref not in grouped:
            grouped[ref] = {
                "id": "la-mojonera-eae-" + hashlib.sha256(ref.encode()).hexdigest()[:16],
                "municipio": "La Mojonera", "codigo_ine": "04903", "provincia": "Almería",
                "titulo": entry["actuacion"], "tipo": "instrumento de planeamiento urbanístico",
                "expediente": ref, "expediente_ambiental": ref,
                "url": entry["url"], "inventory_url": INVENTORY,
                "source": "junta_andalucia", "origen": "inventario_evaluacion_ambiental",
                "source_urls": [], "fichas": [], "documentos": [],
                "publication_ready": False, "geometry_status": "unavailable",
                "coverage": "partial_environmental_planning_inventory",
            }
        record = grouped[ref]
        if entry["url"] not in record["source_urls"]:
            record["source_urls"].append(entry["url"])
            record["fichas"].append(entry)
            record["documentos"].extend(docs)
    return [grouped[k] for k in sorted(grouped)]


class LaMojoneraAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        capture = self.config.get("capture_dir")
        if capture:
            Path(capture).mkdir(parents=True, exist_ok=True)
        sources = []
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-la-mojonera/1.0 (public planning inventory)"

            def fetch(url, name):
                r = session.get(url, timeout=45)
                r.raise_for_status()
                official_url(url, r.url)
                sources.append(url)
                if capture:
                    (Path(capture) / name).write_bytes(r.content)
                return r.content

            page, total, seen, entries = 1, None, set(), []
            while total is None or page <= total:
                url = INVENTORY if page == 1 else ROOT + "/find?" + urlencode({
                    "find": "findResolucionesFiltered", "filter5": "MOJONERA", "page": page, "size": 10,
                })
                rows, current, pages = parse_inventory(fetch(url, f"inventory-{page}.html"), url)
                if current != page or (total is not None and total != pages):
                    raise ValueError("Pagination changed or repeated; rerun extraction")
                total = pages
                for row in rows:
                    if row["url"] in seen:
                        raise ValueError("Repeated inventory detail; pagination may be broken")
                    seen.add(row["url"])
                    name = "detail-" + row["url"].rsplit("/", 1)[1] + ".html"
                    docs = parse_detail(fetch(row["url"], name), row["url"], row["expediente"])
                    entries.append((row, docs))
                page += 1
        records = group_instruments(entries)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        # No output is replaced until all pages and details have succeeded.
        output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
        return {"count": len(records), "written": len(records), "live_records": len(records),
                "inventory_entries": len(entries), "pages": total, "source_urls": sources,
                "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"count": 0, "disabled": True, "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
