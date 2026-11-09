"""Current municipal POM document inventory; no licence or approval inference."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://www.aytoyuncler.com/luis-miguel/"


class YunclerAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        sections = []
        for item in soup.select(".elementor-accordion-item"):
            title = item.select_one(".elementor-accordion-title")
            if title and title.get_text(" ", strip=True).upper() == "URBANISMO":
                sections.append(item.select_one(".elementor-tab-content"))
        if len(sections) != 1 or sections[0] is None:
            raise ValueError("Expected one municipal Urbanismo inventory")
        section = sections[0]
        if "Plan General de Ordenación Municipal" not in section.get_text(" ", strip=True):
            raise ValueError("Municipal plan identity missing")
        # This source is a finite document section, not a search result page.
        # Refuse a newly paginated inventory instead of returning page one.
        for anchor in section.select("a[href]"):
            label = anchor.get_text(" ", strip=True).casefold()
            if ("next" in anchor.get("rel", []) or label in {"siguiente", "next", "»", ">"}
                    or "page-numbers" in anchor.get("class", [])):
                raise ValueError("Paginated planning inventory requires crawler review")
        headings = [h for h in section.select("strong")
                    if h.get_text(" ", strip=True) == "Plan de ordenación"]
        if len(headings) != 1:
            raise ValueError("Expected one Plan de ordenación document group")
        documents = {}
        # Only links after the plan heading and before the next bold heading
        # belong to the instrument. Ordinances, forms and news stay outside.
        for block in headings[0].parent.next_siblings:
            if not getattr(block, "name", None):
                continue
            if block.find("strong"):
                break
            for anchor in block.select("a[href]"):
                url = urljoin(SOURCE, anchor["href"])
                parsed = urlparse(url)
                if (parsed.scheme not in {"http", "https"}
                        or parsed.hostname != "www.aytoyuncler.com"
                        or not parsed.path.startswith("/wp-content/uploads/")):
                    raise ValueError("Unexpected plan document provenance")
                label = anchor.get_text(" ", strip=True)
                if not label:
                    raise ValueError("Untitled plan document")
                documents.setdefault(url, {"titulo": label, "url": url, "source_url": SOURCE})
        if not {"Normas urbanísticas", "Fichas"}.issubset(
                {d["titulo"] for d in documents.values()}):
            raise ValueError("Missing core POM source documents")
        return [{
            "id": "yuncler-pom", "municipio": "Yuncler", "codigo_ine": "45203",
            "provincia": "Toledo", "titulo": "Plan de Ordenación Municipal de Yuncler",
            "tipo": "planeamiento_urbanistico", "url": SOURCE,
            "source": "ayuntamiento", "origen": "inventario_documental_planeamiento",
            "documentos": list(documents.values()),
            "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
            "lat": None, "lon": None, "geometry": None,
            "geometry_status": "unavailable", "publication_ready": False,
            "coverage": "Solo el grupo documental Plan de ordenación de la página municipal; "
                        "sin acreditar vigencia, acuerdos ni modificaciones posteriores. "
                        "Los enlaces se conservan tal como se publican, incluidos los rotos.",
        }]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                             encoding="utf-8")
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=40, stream=True,
                          headers={"User-Agent": "municipio-yuncler/1.0"}) as response:
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 2_000_000:
                    raise ValueError("Planning page exceeds reviewed response size")
            if urlparse(response.url).hostname != "www.aytoyuncler.com":
                raise ValueError("Unexpected source redirect")
        rows = self.parse_projects(bytes(content).decode("utf-8"))
        if self.config.get("evidence_dir"):
            capture = Path(self.config["evidence_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "luis-miguel.html").write_bytes(content)
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": [SOURCE],
                "coverage": "partial", "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Refresh the whole current inventory; there is no dated change feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0,
                "reason": "No verified public granted-licence inventory"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
