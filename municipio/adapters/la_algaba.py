"""La Algaba's official PGOU document folder, grouped by planning instrument.

Coverage is deliberately the PGOU folder, not the whole transparency tree.
Unexpected documents/pagination fail closed so that an incomplete inventory
cannot silently replace a previous extraction.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = (
    "https://laalgaba.sedelectronica.es/transparency/"
    "5985c8b3-4e2b-44ac-be3d-bd5515df4147/"
)
HOST = "laalgaba.sedelectronica.es"


def normalized(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(text.lower().split())


def parse_inventory(html: str, url: str = SOURCE) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.TransparencyListPanel")
    if table is None or "PLANEAMIENTO URBANÍSTICO/PGOU" not in soup.get_text(" ", strip=True):
        raise ValueError("Missing official PGOU folder/breadcrumb")
    for control in soup.select("button, a, input"):
        label = normalized(" ".join([
            control.get_text(" ", strip=True), control.get("value", ""),
            control.get("aria-label", ""), control.get("title", ""),
        ]))
        if (re.search(r"mostrar mas|siguiente|next|cargar mas", label)
                or "next" in control.get("rel", [])
                or control.get("class") and any("pagin" in c.lower() for c in control["class"])):
            raise ValueError("PGOU folder has pagination; review crawler before extraction")

    groups: dict[str, dict] = {}
    seen = set()
    for anchor in table.select("a[href]"):
        title = anchor.get_text(" ", strip=True)
        target = urljoin(url, anchor["href"])
        parsed = urlparse(target)
        if (parsed.scheme != "https" or parsed.hostname != HOST
                or not re.fullmatch(r"/preview-document/[0-9a-f-]{36}", parsed.path)
                or parsed.query or parsed.fragment):
            raise ValueError(f"Unexpected document or subfolder in PGOU inventory: {title}")
        key_title = normalized(title)
        if key_title in {"normas_urbanisticas", "planos pgou", "memoria general"}:
            key, instrument = "pgou", "Plan General de Ordenación Urbanística de La Algaba"
            kind = "plan_general_ordenacion_urbanistica"
        else:
            modification = re.fullmatch(
                r"documento (?:de )?reformado de modificacion puntual (?:del pgou )?"
                r"n[o.]?\s*(\d+)(?: del pgou)?(?:\.?diligenciado)?", key_title
            )
            if not modification:
                raise ValueError(f"Unclassified PGOU document; review grouping: {title}")
            number = modification.group(1)
            key = f"pgou-modificacion-{number}-reformado"
            instrument = f"Reformado de la Modificación Puntual n.º {number} del PGOU de La Algaba"
            kind = "modificacion_planeamiento"
        if target in seen:
            continue
        seen.add(target)
        if key not in groups:
            groups[key] = {
                "id": f"la-algaba-{key}", "municipio": "La Algaba",
                "codigo_ine": "41007", "provincia": "Sevilla",
                "titulo": instrument, "tipo": kind,
                "url": target, "inventory_url": url,
                "source": "ayuntamiento", "origen": "inventario_documental_pgou",
                "documentos": [], "publication_ready": False,
                "geometry_status": "unavailable",
                "coverage": "carpeta_pgou_parcial_municipal",
            }
        groups[key]["documentos"].append({"titulo": title, "url": target, "inventory_url": url})
    if not groups:
        raise ValueError("Empty PGOU document inventory")
    return list(groups.values())


class LaAlgabaAyuntamientoAdapter(AyuntamientoAdapter):
    SOURCE = SOURCE

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
            self.SOURCE, timeout=40,
            headers={"User-Agent": "municipio-la-algaba/1.0 (public planning inventory)"},
        )
        response.raise_for_status()
        if response.url.rstrip("/") != self.SOURCE.rstrip("/"):
            raise ValueError("Unexpected PGOU folder redirect")
        rows = parse_inventory(response.text, response.url)
        # Optional local capture for reproducible research, configured by the caller.
        if self.config.get("capture_dir"):
            capture = Path(self.config["capture_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "pgou-live.html").write_text(response.text, encoding="utf-8")
        self._write(out_jsonl, rows)
        return {
            "count": len(rows), "written": len(rows),
            "documents": sum(len(row["documentos"]) for row in rows),
            "source_urls": [response.url], "coverage": "carpeta_pgou_parcial_municipal",
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict:
        # Full snapshot of this folder; no inferred incremental watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict:
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified granted-licence inventory"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict:
        return self.backfill_licencias(out_jsonl)
