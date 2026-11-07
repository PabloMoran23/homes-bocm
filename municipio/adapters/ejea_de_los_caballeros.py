"""Municipal planning document inventory; no inferred approvals or geometry."""
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

SOURCE_URL = "https://www.ejea.es/areas/urbanismo/"
LIMITATIONS = [
    "Only the current Planeamiento document inventory, not a complete historical register.",
    "No granted licences, procurement notices or news extracted.",
    "Document contents, legal validity and approval/publication dates are not inferred.",
    "No project coordinates; topographic reference points are excluded.",
]


def _norm(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def parse_inventory(html: str, source_url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    headings = [h for h in soup.find_all("h2") if h.get_text(" ", strip=True) == "Planeamiento"]
    if len(headings) != 1:
        raise ValueError("Expected one municipal Planeamiento inventory")
    start = headings[0]
    nodes = []
    for node in start.find_next_siblings():
        if node.name == "h2":
            break
        nodes.append(node)
    # Fail visibly if the reviewed single-page inventory becomes paginated.
    if soup.select('link[rel~=next], a[rel~=next]'):
        raise ValueError("Pagination detected; crawler must be extended")
    section = ""
    subsection = ""
    groups: dict[str, dict] = {}
    seen_sections = set()
    for node in nodes:
        text = node.get_text(" ", strip=True)
        if node.name == "h3":
            section, subsection = text, ""
            if section not in {"Plan general", "Planes parciales", "Planes especiales"}:
                raise ValueError(f"Unreviewed planning section: {section}")
            seen_sections.add(section)
        elif node.name == "h4":
            subsection = text
        for control in [node, *node.find_all(True)]:
            classes = " ".join(control.get("class", []))
            label = _norm(control.get_text(" ", strip=True))
            if (re.search(r"pagin|load.more|load-more", classes, re.I)
                    or (control.name in {"a", "button"} and re.match(
                        r"^(siguiente|next|ver mas|cargar mas|\d+)$", label))):
                raise ValueError("Pagination/load-more detected in planning inventory")
        for a in node.select("a[href]"):
            title = a.get_text(" ", strip=True)
            url = urljoin(source_url, a["href"])
            parsed = urlparse(url)
            if (not title or parsed.scheme != "https"
                    or parsed.hostname not in {"st1.ejea.es", "www.ejea.es", "ejea.es"}
                    or not parsed.path.lower().endswith(".pdf")):
                raise ValueError(f"Unreviewed planning attachment: {url}")
            if section == "Plan general" and subsection != "Modificaciones PGOU":
                instrument = "Plan general de ordenación urbana de Ejea de los Caballeros"
                kind = "plan_general"
            elif section == "Plan general":
                if not re.match(r"^Modificaci[oó]n\b", title, re.I):
                    raise ValueError(f"Unexpected PGOU modification: {title}")
                instrument = re.sub(r"\s+Parte\s+\d+\s*$", "", title, flags=re.I)
                kind = "modificacion_pgou"
            elif section in {"Planes parciales", "Planes especiales"}:
                prefix = "Plan Parcial" if section == "Planes parciales" else "Plan Especial"
                if not title.lower().startswith(prefix.lower() + " "):
                    raise ValueError(f"Unexpected plan title: {title}")
                instrument = re.sub(r"\s+Parte\s+\d+\s*$", "", title, flags=re.I)
                kind = "plan_parcial" if section == "Planes parciales" else "plan_especial"
            else:
                raise ValueError("Attachment outside supported planning section")
            key = _norm(instrument)
            if key not in groups:
                groups[key] = {
                    "id": "ejea-plan-" + hashlib.sha256(key.encode()).hexdigest()[:16],
                    "municipio": "Ejea de los Caballeros", "codigo_ine": "50095",
                    "provincia": "Zaragoza", "titulo": instrument, "tipo": kind,
                    "url": url, "inventory_url": source_url,
                    "source": "ayuntamiento", "origen": "inventario_planeamiento",
                    "publication_ready": False, "geometry_status": "unavailable",
                    "documentos": [],
                }
            docs = groups[key]["documentos"]
            if not any(d["url"] == url for d in docs):
                docs.append({"titulo": title, "url": url, "source_url": source_url,
                             "seccion": section, "apartado": subsection})
    if seen_sections != {"Plan general", "Planes parciales", "Planes especiales"} or not groups:
        raise ValueError("Incomplete or empty planning inventory")
    if not any(row["tipo"] == "plan_general" for row in groups.values()):
        raise ValueError("Missing PGOU documents")
    return list(groups.values())


class EjeaDeLosCaballerosAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(SOURCE_URL, timeout=45, headers={
            "User-Agent": "municipal-planning-inventory/1.0"})
        response.raise_for_status()
        if urlparse(response.url).hostname != "www.ejea.es":
            raise ValueError("Unexpected inventory redirect")
        rows = parse_inventory(response.text, response.url)
        if self.config.get("evidence_dir"):
            capture = Path(self.config["evidence_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "urbanismo.html").write_text(response.text, encoding="utf-8")
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "source_urls": [response.url],
                "coverage": "current_planning_document_inventory", "limitations": LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh: small single-page inventory; no artificial incremental dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified granted-licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
