"""Current official PGOM documentary inventory; one instrument, many documents.

This deliberately covers the PGOM microsite, not the historical transparency
archive. No legal dates or project coordinates are inferred from file metadata.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = "https://www.islamayor.es/es/pgom/documentacion/"
DOCUMENT_PATH = "/export/sites/islamayor/.galleries/documentacion-pgom/"
LIMITATIONS = [
    "Cobertura parcial: solo inventario documental del nuevo PGOM; no incluye "
    "el archivo histórico paginado de transparencia ni otras obras municipales.",
    "Las secciones y títulos documentales no acreditan aprobación definitiva, "
    "vigencia, ejecución de obras ni concesión de licencias.",
    "El adaptador no extrae fechas de publicación/acuerdo ni geometría del HTML; "
    "el contenido íntegro de los PDF no se analiza automáticamente.",
]


def parse_inventory(html: str, source_url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1.cat-title")
    intro = soup.select_one(".detail-p")
    if (not heading or heading.get_text(" ", strip=True) != "Plan General de Ordenación Municipal"
            or not intro or "Plan General de Ordenación Municipal de Isla Mayor" not in intro.get_text(" ", strip=True)):
        raise ValueError("Missing identified Isla Mayor PGOM inventory")

    # This inventory currently exposes every file (collector rows=10000).
    # Fail explicitly if the site changes to pagination; never return page one.
    if soup.select('[class*="pagin"], [id*="pagin"], a[rel~="next"]') or any(
        re.search(r"[?&](?:page[^=]*|pagina|start|offset)=", a["href"], re.I)
        for a in soup.select("a[href]")
    ):
        raise ValueError("Pagination detected: complete traversal must be implemented before extraction")

    documents: dict[str, dict] = {}
    blocks = soup.select(".download-block")
    if not blocks:
        raise ValueError("Missing document blocks")
    for block in blocks:
        title = block.select_one(".title")
        section = title.get_text(" ", strip=True) if title else ""
        if not section:
            raise ValueError("Missing documentary section title")
        links = block.select("table a[href]")
        expected = [int(m[1]) for c in block.find_all(string=lambda t: isinstance(t, Comment))
                    if (m := re.search(r"listResultSize:\s*(\d+)", str(c)))]
        if expected and (len(expected) != 1 or expected[0] != len(links)):
            raise ValueError(f"Incomplete inventory section: {section}")
        if not links:
            raise ValueError(f"Empty inventory section: {section}")
        for a in links:
            target = urljoin(source_url, a["href"])
            parsed = urlparse(target)
            label = a.get_text(" ", strip=True)
            if (parsed.scheme != "https" or parsed.hostname not in {"www.islamayor.es", "islamayor.es"}
                    or not parsed.path.startswith(DOCUMENT_PATH)
                    or not parsed.path.lower().endswith(".pdf") or not label):
                raise ValueError(f"Unexpected document in PGOM inventory: {target}")
            doc = documents.setdefault(target, {"titulo": label, "url": target,
                                                "secciones": [], "source_url": source_url})
            if section not in doc["secciones"]:
                doc["secciones"].append(section)
    if not documents:
        raise ValueError("No PGOM documents found")
    # Navigation or a generic plan description alone cannot create a record.
    all_links = {urljoin(source_url, a["href"]) for a in soup.select("a[href]")
                 if DOCUMENT_PATH in urlparse(urljoin(source_url, a["href"])).path}
    if all_links != set(documents):
        raise ValueError("PGOM links outside parsed inventory blocks; source layout changed")
    return [{
        "id": "isla-mayor-pgom",
        "municipio": "Isla Mayor", "codigo_ine": "41902", "provincia": "Sevilla",
        "titulo": heading.get_text(" ", strip=True) + " de Isla Mayor (PGOM)",
        "tipo": "instrumento de planeamiento urbanístico",
        "descripcion": intro.get_text(" ", strip=True),
        "url": source_url, "inventory_url": source_url,
        "source": "ayuntamiento", "origen": "inventario_documental_pgom",
        "documentos": list(documents.values()),
        "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
        "lat": None, "lon": None, "geometry": None,
        "geometry_status": "unavailable", "publication_ready": False,
        "coverage": "current_pgom_document_inventory", "limitations": LIMITATIONS.copy(),
    }]


class IslaMayorAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=60, headers={
            "User-Agent": "municipio-isla-mayor/1.0 (official planning inventory)"})
        response.raise_for_status()
        final = urlparse(response.url)
        if (final.scheme != "https" or final.hostname not in {"www.islamayor.es", "islamayor.es"}
                or final.path != urlparse(SOURCE_URL).path or final.query):
            raise ValueError("Unexpected PGOM inventory redirect")
        rows = parse_inventory(response.text, response.url)
        if self.config.get("capture_dir"):
            capture_dir = Path(self.config["capture_dir"])
            capture_dir.mkdir(parents=True, exist_ok=True)
            (capture_dir / "pgom-live.html").write_bytes(response.content)
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(output)
        return {"count": len(rows), "written": len(rows),
                "documents": sum(len(row["documentos"]) for row in rows),
                "source_urls": [response.url], "limitations": LIMITATIONS.copy(),
                "source_sha256": hashlib.sha256(response.content).hexdigest(),
                "coverage": "current_pgom_document_inventory", "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full current snapshot; do not append duplicate instruments on refresh.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"count": 0, "disabled": True, "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
