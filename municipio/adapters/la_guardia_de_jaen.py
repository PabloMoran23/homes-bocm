"""Municipal planning inventory: one record per instrument, not per PDF."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://laguardiadejaen.com/portal-transparencia/planeamiento-de-ordenacion-urbana/"
SUPPORTED = {
    "NN.SS. - Normas Subsidiarias (Revisión)",
    "Adaptación Parcial de NN.SS. a LOUA",
    "NN.SS. - Normas Subsidiarias (Modificación)",
    "Plan Parcial", "Plan Parcial (Modificación)", "Estudios de detalle",
}


def clean(node):
    return " ".join(node.get_text(" ", strip=True).split())


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article .entry-content")
    if article is None:
        raise ValueError("Missing municipal inventory content")
    if article.select('[rel="next"], .pagination, .page-links, .wp-pagenavi'):
        raise ValueError("Pagination detected; review crawler before extracting")
    for a in article.select("a[href]"):
        if clean(a).casefold() in {"siguiente", "next", "»", "›"} and a["href"] not in {"", "#"}:
            raise ValueError("Pagination detected")
    inventories = article.select(".et_pb_tabs")
    if len(inventories) != 1:
        raise ValueError("Expected one planning tab inventory")
    inventory = inventories[0]
    controls = inventory.select(".et_pb_tabs_controls > li")
    tabs = inventory.select(".et_pb_all_tabs > .et_pb_tab")
    if not controls or len(controls) != len(tabs):
        raise ValueError("Incomplete planning tab inventory")
    rows = []
    identities = set()
    for control, tab in zip(controls, tabs):
        category = clean(control)
        if category not in SUPPORTED:
            raise ValueError(f"Unreviewed planning category: {category}")
        current = None
        for node in tab.descendants:
            if not isinstance(node, Tag):
                continue
            if "et-bio" in node.get("class", []):
                text = clean(node)
                match = re.fullmatch(
                    r"Ámbito:\s*(.+?)\s+Fecha de aprobación:\s*(.*?)\s+Fecha de publicación:\s*(.*)", text
                )
                if not match:
                    raise ValueError(f"Unrecognized instrument metadata: {text}")
                area, approval, publication = match.groups()
                identity = category + "|" + area
                if identity in identities:
                    raise ValueError(f"Duplicate instrument identity: {identity}")
                identities.add(identity)
                key = hashlib.sha256(identity.encode()).hexdigest()[:20]
                current = {
                    "id": "la-guardia-de-jaen-plan-" + key,
                    "municipio": "La Guardia de Jaén", "codigo_ine": "23038",
                    "provincia": "Jaén", "titulo": category + " — " + area,
                    "tipo": "planeamiento_urbanistico", "ambito": area,
                    "categoria_fuente": category, "url": url, "inventory_url": url,
                    "source": "ayuntamiento", "origen": "inventario_planeamiento",
                    "metadata_fuente": text, "documentos": [],
                    "publication_ready": False, "geometry_status": "unavailable",
                    "vigencia_verificada": False, "avisos": [],
                }
                for field, value in (("fecha_aprob", approval), ("fecha_publicacion", publication)):
                    current[field + "_fuente"] = value
                    if value in {"", "–", "-", "—"}:
                        continue
                    try:
                        current[field] = datetime.strptime(value, "%d/%m/%Y").date().isoformat()
                    except ValueError:
                        current["avisos"].append(f"{field}: fecha inválida en fuente ({value})")
                if current.get("fecha_publicacion", "9999") < current.get("fecha_aprob", "0000"):
                    current["avisos"].append("Publicación anterior a aprobación según la fuente; sin corregir")
                rows.append(current)
            elif node.name == "a" and node.get("href"):
                target = urljoin(url, node["href"])
                title = clean(node)
                if urlparse(target).path.lower().endswith(".pdf") and title:
                    if current is None:
                        raise ValueError("Document precedes instrument metadata")
                    if urlparse(target).hostname != "laguardiadejaen.com":
                        raise ValueError("Unexpected document host")
                    if target not in {d["url"] for d in current["documentos"]}:
                        current["documentos"].append({"titulo": title, "url": target, "source_url": url})
        if current is None:
            raise ValueError(f"Empty category: {category}")
    if not rows or any(not r["documentos"] for r in rows):
        raise ValueError("Missing instruments or instrument documents")
    return rows


class LaGuardiaDeJaenAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        response = requests.get(SOURCE, timeout=45, headers={"User-Agent": "municipal-inventory/1.0"})
        response.raise_for_status()
        if urlparse(response.url).hostname != "laguardiadejaen.com":
            raise ValueError("Unexpected inventory redirect")
        if self.config.get("capture_dir"):
            capture = Path(self.config["capture_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "inventory.html").write_text(response.text, encoding="utf-8")
        rows = parse_inventory(response.text, response.url)
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "source_urls": [response.url],
                "coverage": "current municipal planning document inventory", "publication_ready": False}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: removals and revised document bundles must be visible.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified public granted-licence register"}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
