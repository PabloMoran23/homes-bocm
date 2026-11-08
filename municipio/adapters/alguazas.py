"""Named planning instrument in Alguazas' municipal document inventory."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE_URL = "https://alguazas.es/ordenanzas-municipales/"


def official_document(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"alguazas.es", "www.alguazas.es"}
        and parsed.path.startswith("/wp-content/uploads/")
        and parsed.path.lower().endswith((".zip", ".pdf"))
    )


def parse_inventory(html: str, url: str = SOURCE_URL) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    if soup.select('.pagination a[href], .avia_pagination a[href], a[rel~="next"], .page-links a[href]'):
        raise ValueError("Inventory pagination detected; review before extracting partial output")
    documents = {}
    title = None
    for block in soup.select(".av_promobox"):
        heading = block.select_one(".avia-promocontent")
        if heading is None:
            continue
        label = heading.get_text(" ", strip=True)
        if " ".join(label.upper().split()) not in {
            "NORMAS SUBSIDIARIAS", "NORMAS SUBSIDIARIAS DE ALGUAZAS"
        }:
            continue
        title = label
        links = block.select("a[href]")
        if not links:
            raise ValueError("Normas Subsidiarias entry has no documents")
        for link in links:
            target = urljoin(url, link["href"])
            if not official_document(target):
                raise ValueError(f"Unexpected planning document URL: {target}")
            documents.setdefault(target, {
                "titulo": link.get_text(" ", strip=True) or label,
                "url": target,
                "source_url": url,
            })
    if not documents:
        raise ValueError("No documented Normas Subsidiarias in municipal inventory")
    return [{
        "id": "alguazas-planeamiento-normas-subsidiarias",
        "municipio": "Alguazas",
        "codigo_ine": "30007",
        "provincia": "Murcia",
        "titulo": title,
        "tipo": "planeamiento_urbanistico",
        "url": url,
        "inventory_url": url,
        "source": "ayuntamiento",
        "origen": "inventario_documental_municipal",
        "documentos": list(documents.values()),
        "coverage": "partial_named_planning_instrument",
        "publication_ready": False,
        "geometry_status": "unavailable",
    }]


class AlguazasAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path: Path, rows: list[dict]) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )
        temporary.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict:
        response = requests.get(
            SOURCE_URL, timeout=45,
            headers={"User-Agent": "municipio-alguazas/1.0 (public planning inventory)"},
        )
        response.raise_for_status()
        if response.url.rstrip("/") != SOURCE_URL.rstrip("/"):
            raise ValueError("Unexpected inventory redirect")
        rows = parse_inventory(response.text, response.url)
        capture = self.config.get("evidence_dir")
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "inventory.html").write_text(response.text, encoding="utf-8")
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows),
                "source_urls": [SOURCE_URL], "coverage": "partial_named_planning_instrument"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full refresh of this single-page inventory; no synthetic incremental dates.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True,
                "reason": "No verified register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
