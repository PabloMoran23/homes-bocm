"""Reinosa's official planning document inventory, not a licence register."""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://www.aytoreinosa.es/normativa/"
HOST = "www.aytoreinosa.es"
LIMITATIONS = [
    "Sólo el inventario documental PGOU de Normativa, no todo el planeamiento ni las obras del municipio.",
    "Los paquetes 02 a 08 y 23 a 29 se conservan agrupados; no se inventan expedientes individuales.",
    "La presencia en el inventario no acredita vigencia, aprobación ni ejecución.",
    "Sin fechas de publicación/acuerdo verificadas, geometría ni registro de licencias concedidas.",
    "Se retienen enlaces documentales; el adaptador no interpreta el texto de los PDF.",
]


def parse_inventory(html: str, source_url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    panel = soup.select_one("#Planifica")
    if panel is None:
        raise ValueError("Missing PGOU inventory panel")
    # This inventory is fully rendered on one page. Refuse pagination rather
    # than silently extracting only its first page if the site changes.
    content = soup.select_one(".entry-content") or panel
    if content.select('.pagination, .page-numbers, [rel="next"], [data-page], [data-total-pages]'):
        raise ValueError("Pagination detected; crawler must be extended")
    for a in content.select("a[href]"):
        if re.search(r"siguiente|next|cargar m[aá]s|ver m[aá]s", a.get_text(" ", strip=True), re.I):
            raise ValueError("Possible additional inventory pages")
    categories = panel.select(".bsk-pdf-category")
    if len(categories) != 3 or any(
        len(panel.select(".cat-" + n)) != 1 for n in ("6", "7", "8")
    ):
        raise ValueError("Planning categories changed; review coverage")
    records = {}
    for category in categories:
        classes = category.get("class", [])
        anchors = category.select("a[href]")
        if not anchors:
            raise ValueError("Empty planning category")
        for a in anchors:
            title = a.get_text(" ", strip=True)
            target = urljoin(source_url, a["href"])
            parsed = urlparse(target)
            if (not title or parsed.scheme != "https" or parsed.hostname != HOST
                    or not parsed.path.startswith("/wp-content/uploads/")
                    or not parsed.path.lower().endswith(".pdf")):
                raise ValueError("Unexpected planning document link")
            agrupado = False
            if "cat-6" in classes:
                key, name = "pgou", "Plan General de Ordenación Urbana de Reinosa"
            elif "cat-7" in classes:
                match = re.fullmatch(r"MODIFICACION(?:ES)? PUNTUAL(?:ES)? (\d+)(?: a (\d+))?", title, re.I)
                if not match:
                    raise ValueError("Unrecognised PGOU modification: " + title)
                start, end = match.groups()
                key = "modificacion-" + str(int(start))
                if end:
                    key += "-a-" + str(int(end))
                    agrupado = True
                name = title + " del PGOU de Reinosa"
            else:
                if title.upper() != "MODIFICACION ORDENANZAS DEL PLAN PARCIAL POLIGONO INDUSTRIAL LA VEGA":
                    raise ValueError("Unrecognised partial plan: " + title)
                key, name = "plan-parcial-la-vega-modificacion-ordenanzas", title
            if key not in records:
                records[key] = {
                    "id": "reinosa-plan-" + key,
                    "municipio": "Reinosa", "codigo_ine": "39059", "provincia": "Cantabria",
                    "titulo": name, "tipo": "planeamiento_urbanistico",
                    "url": SOURCE + "#Planifica" if key == "pgou" else target,
                    "inventory_url": source_url, "source": "ayuntamiento",
                    "origen": "inventario_documental_pgou",
                    "agrupacion_documental": agrupado,
                    "publication_ready": False, "geometry_status": "unavailable",
                    "documentos": [],
                }
            docs = records[key]["documentos"]
            if not any(d["url"] == target for d in docs):
                docs.append({"titulo": title, "url": target, "source_url": source_url})
    if not records:
        raise ValueError("No planning instruments found")
    return list(records.values())


class ReinosaAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> dict:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(path)
        return {"count": len(rows), "written": len(rows)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE, timeout=45, headers={
            "User-Agent": "municipio-reinosa/1.0 (public planning inventory)"})
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST:
            raise ValueError("Unexpected inventory redirect")
        rows = parse_inventory(response.text, response.url)
        # Optional local captures for reproducible review. No database or publication.
        if self.config.get("capture_dir"):
            capture = Path(self.config["capture_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "normativa.html").write_text(response.text, encoding="utf-8")
        result = self._write(out_jsonl, rows)
        return {**result, "source_urls": [response.url], "coverage": "partial_document_inventory",
                "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh: no dates are available for a sound incremental cursor.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        return {**self._write(out_jsonl, []), "disabled": True}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
