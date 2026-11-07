"""Bueu's municipal PXOM document inventory (one instrument, many documents)."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://concellodebueu.gal/pxom/"
GROUP_MINIMUMS = {"MEMORIA": 5, "PLANOS": 1, "PLANOS ORDENACIÓN": 7}


class BueuAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_projects(html: str) -> list[dict]:
        soup = BeautifulSoup(html, "html.parser")
        content = soup.select_one("main .page__content")
        if content is None:
            raise ValueError("Missing municipal PXOM content")
        # The reviewed inventory is a single static page. Fail on pagination
        # rather than writing a deceptively complete snapshot of its first page.
        if soup.select('a[rel~=next], .pagination, .page-numbers, .post-nav-links'):
            raise ValueError("PXOM pagination requires crawler review")
        for a in content.select("a[href]"):
            if a.get_text(" ", strip=True).casefold() in {
                "seguinte", "siguiente", "next", "ver máis", "cargar máis"
            }:
                raise ValueError("PXOM continuation requires crawler review")
        headings = [h.get_text(" ", strip=True) for h in content.select("h3")
                    if "PXOM Bueu" in h.get_text(" ", strip=True)]
        if len(headings) != 1:
            raise ValueError("Expected exactly one identified PXOM Bueu instrument")
        match = re.fullmatch(
            r"PXOM Bueu \(Aprobación definitiva orde (\d{2}/\d{2}/\d{4})\)", headings[0]
        )
        if not match:
            raise ValueError("Unrecognised PXOM approval statement")
        approval = datetime.strptime(match[1], "%d/%m/%Y").date().isoformat()
        documents = {}
        counts = {}
        for widget in content.select(".lsvr_document-attachments-widget"):
            heading = widget.select_one(".widget__title")
            if heading is None:
                raise ValueError("Document group lacks title")
            group = heading.get_text(" ", strip=True)
            urls = set()
            for a in widget.select("a[href]"):
                url = urljoin(SOURCE, a["href"])
                parsed = urlparse(url)
                if (parsed.scheme != "https" or parsed.netloc != "concellodebueu.gal"
                        or not parsed.path.startswith("/wp-content/uploads/")
                        or not parsed.path.lower().endswith(".pdf")):
                    raise ValueError("Unexpected PXOM document URL")
                title = a.get_text(" ", strip=True)
                if not title:
                    raise ValueError("PXOM document lacks title")
                urls.add(url)
                document = documents.setdefault(url, {
                    "titulo": title, "url": url, "grupos": [], "source_url": SOURCE,
                })
                if group not in document["grupos"]:
                    document["grupos"].append(group)
            counts.setdefault(group, set()).update(urls)
        # Reviewed lower bounds guard against empty/partially rendered widgets;
        # additions are collected without an upper limit or slicing.
        if any(len(counts.get(group, set())) < minimum
               for group, minimum in GROUP_MINIMUMS.items()):
            raise ValueError("Incomplete PXOM document inventory; review source changes")
        return [{
            "id": "bueu-proy-pxom", "municipio": "Bueu", "codigo_ine": "36004",
            "provincia": "Pontevedra", "titulo": "Plan Xeral de Ordenación Municipal de Bueu (PXOM)",
            "tipo": "planeamiento_urbanistico", "fase": "aprobación definitiva",
            "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None,
            "fecha_aprob": approval, "url": SOURCE, "source": "ayuntamiento",
            "origen": "inventario_documental_pxom", "descripcion": headings[0],
            "documentos": list(documents.values()),
            "provenance": {"fecha_aprob": {"url": SOURCE, "texto": headings[0]}},
            "lat": None, "lon": None, "geometry": None,
            "geometry_status": "unavailable", "publication_ready": False,
            "coverage": "Inventario municipal del PXOM; no incluye otros instrumentos, obras ni licencias.",
        }]

    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        with requests.get(SOURCE, timeout=(10, 40), stream=True,
                          headers={"User-Agent": "municipio-bueu/1.0"}) as response:
            response.raise_for_status()
            if response.url.rstrip("/") != SOURCE.rstrip("/"):
                raise ValueError("PXOM inventory redirected; review source")
            body = bytearray()
            for chunk in response.iter_content(65536):
                body.extend(chunk)
                if len(body) > 4_000_000:
                    raise ValueError("PXOM inventory exceeds response size limit")
        html = body.decode("utf-8")
        if self.config.get("capture_dir"):
            capture = Path(self.config["capture_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "pxom-live.html").write_bytes(body)
        rows = self.parse_projects(html)
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": [SOURCE],
                "documents": sum(len(r["documentos"]) for r in rows)}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
