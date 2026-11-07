"""Document inventories for two named municipal planning instruments.

This is a current snapshot, not a complete municipal planning/licence register.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.lascabezasdesanjuan.es"
SOURCES = (
    ("pgom", BASE + "/es/pgom/", "Plan General de Ordenación Municipal"),
    ("ranchillo", BASE + "/es/plan-parcial-sector-subs-r.2.-ranchillo/",
     "PLAN PARCIAL SECTOR SUBS-R.2. RANCHILLO"),
)
LIMITATIONS = [
    "Cobertura parcial: solo las dos secciones documentales PGOM y Ranchillo; no incluye el PGOU histórico del portal de transparencia ni todas sus modificaciones.",
    "Inventario documental actual, sin acreditar vigencia, aprobación definitiva ni ejecución de obras.",
    "Sin fechas de publicación o acuerdo verificadas, sin geometría y sin licencias concedidas.",
    "Se conservan enlaces documentales; no se analiza íntegramente el contenido de los PDF ni se presupone que todos sean accesibles.",
]


def parse_inventory(html: str, url: str) -> dict:
    """One record per instrument, preserving all distinct gallery links."""
    source = next((s for s in SOURCES if s[1] == url), None)
    if source is None:
        raise ValueError("Unknown municipal instrument source")
    key, _, expected_title = source
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".detail-t")
    if title is None or title.get_text(" ", strip=True).casefold() != expected_title.casefold():
        raise ValueError("Instrument heading missing or changed")
    # These inventories currently render every document in one HTML table.
    # Refuse partial output if the CMS introduces pagination (including disabled
    # controls, which require a fresh review of the inventory's behaviour).
    if soup.select('.pagination, .pager, [class*="pagin"], [rel="next"]'):
        raise ValueError("Pagination detected; extend crawler before extracting")
    for a in soup.select("a[href]"):
        if re.search(r"(?:[?&])[^=&]*(?:page|pagina)[^=&]*=", a["href"], re.I):
            raise ValueError("Pagination query detected")
    tables = [t for t in soup.select("table.table")
              if [h.get_text(strip=True) for h in t.select("th")] == ["Nombre", "Tamaño", "Tipo"]]
    if not tables:
        raise ValueError("Document inventory missing")
    documents = {}
    for table in tables:
        for tr in table.select("tr"):
            if tr.select("th"):
                continue
            a = tr.select_one("td a[href]")
            if a is None:
                raise ValueError("Document row without a link")
            target = urljoin(url, a["href"])
            parsed = urlparse(target)
            label = a.get_text(" ", strip=True)
            # One genuine PDF has no .pdf extension; the gallery path and PDF
            # type supplied by the inventory establish its documentary role.
            if (parsed.scheme != "https" or parsed.netloc != urlparse(BASE).netloc
                    or not parsed.path.startswith(("/export/sites/lascabezasdesanjuan/.galleries/", "/.galleries/"))
                    or "PDF" not in tr.get_text(" ", strip=True).upper() or not label):
                raise ValueError("Unexpected document row; review source format")
            documents.setdefault(target, {"titulo": label, "url": target, "inventory_url": url})
    if not documents:
        raise ValueError("No instrument documents found")
    return {
        "id": "las-cabezas-de-san-juan-plan-" + key,
        "municipio": "Las Cabezas de San Juan", "codigo_ine": "41020",
        "provincia": "Sevilla", "titulo": title.get_text(" ", strip=True),
        "tipo": "planeamiento_urbanistico", "source": "ayuntamiento",
        "origen": "inventario_documental_planeamiento", "url": url,
        "documentos": list(documents.values()), "coverage": "partial_current_document_inventory",
        "publication_ready": False, "geometry_status": "unavailable",
    }


def _write(path: Path, rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    temp.replace(path)


class LasCabezasDeSanJuanAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        rows = []
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-planning-inventory/1.0"
            for key, url, _ in SOURCES:
                response = session.get(url, timeout=45)
                response.raise_for_status()
                if response.url != url:
                    raise ValueError("Unexpected source redirect")
                row = parse_inventory(response.text, url)
                capture_dir = self.config.get("capture_dir")
                if capture_dir:
                    destination = Path(capture_dir)
                    destination.mkdir(parents=True, exist_ok=True)
                    (destination / (key + ".html")).write_text(response.text, encoding="utf-8")
                rows.append(row)
        # Write only after every source was retrieved and validated.
        _write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows),
                "documents": sum(len(r["documentos"]) for r in rows),
                "source_urls": [s[1] for s in SOURCES], "limitations": LIMITATIONS,
                "coverage": "partial_current_document_inventory", "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of both bounded inventories; no date cutoff or checkpoint.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        _write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified granted-licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
