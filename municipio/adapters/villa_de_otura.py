"""Municipal consultation-document inventory; no inference of planning approval."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://ayuntamientodeotura.es/transparencia/nuevo-planeamiento-urbanistico-de-otura/"
HOST = urlparse(SOURCE).hostname


def normalized(text):
    return " ".join(unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().upper().split())


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(".post-content")
    if content is None:
        raise ValueError("Municipal planning content missing")
    # This is a single document inventory. Fail explicitly if navigation appears.
    for a in soup.select("a[href]"):
        label = normalized(a.get_text(" ", strip=True))
        if ("next" in a.get("rel", []) or label in {"SIGUIENTE", "NEXT", "SIGUIENTE PAGINA"}
                or "page-numbers" in a.get("class", [])
                or re.search(r"/page/\d+|[?&](?:paged|page)=\d+", a["href"])):
            raise ValueError("Inventory pagination detected; crawler needs review")
    records = {}
    for a in content.select("a[href]"):
        title = a.get_text(" ", strip=True)
        name = normalized(title)
        match = re.match(
            r"^CONSULTA PREVIA DEL (PLAN (?:GENERAL DE ORDENACION MUNICIPAL|DE ORDENACION URBANA)) DE LA VILLA DE OTURA\b",
            name,
        )
        if not match:
            continue
        target = urljoin(url, a["href"]).split("#")[0]
        parsed = urlparse(target)
        if parsed.scheme != "https" or parsed.hostname != HOST or not parsed.path.lower().endswith(".pdf"):
            raise ValueError("Unexpected consultation document URL")
        code = "pgom" if "GENERAL" in match[1] else "pou"
        if code not in records:
            records[code] = {
                "id": "villa-de-otura-plan-" + code,
                "municipio": "Villa de Otura", "codigo_ine": "18149", "provincia": "Granada",
                "titulo": match[1].capitalize() + " de la Villa de Otura",
                "tipo": "planeamiento_urbanistico", "url": target, "inventory_url": url,
                "source": "ayuntamiento", "origen": "inventario_consultas_previas_planeamiento",
                "fase_documentada": "consulta previa",
                "descripcion": "Instrumento documentado mediante consulta previa; esta fuente no acredita su aprobación ni su fase actual.",
                "publication_ready": False, "geometry_status": "unavailable", "documentos": [],
            }
        docs = records[code]["documentos"]
        if target not in {d["url"] for d in docs}:
            docs.append({"titulo": title, "url": target, "tipo": "consulta_previa", "source_url": url})
    if not records:
        raise ValueError("No supported planning consultation documents found")
    return list(records.values())


class VillaDeOturaAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        response = requests.get(url, timeout=45, headers={"User-Agent": "municipal-planning-inventory/1.0"})
        response.raise_for_status()
        if urlparse(response.url).hostname != HOST or urlparse(response.url).scheme != "https":
            raise ValueError("Unexpected source redirect")
        capture_dir = self.config.get("capture_dir")
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            name = Path(urlparse(url).path).name if urlparse(url).path.lower().endswith(".pdf") else "inventory.html"
            (folder / name).write_bytes(response.content)
        return response

    @staticmethod
    def _write(out_jsonl, rows):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        temp = output.with_suffix(output.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(output)
        return {"count": len(rows), "written": len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = parse_inventory(self._fetch(SOURCE).text)
        checked = set()
        for row in rows:
            for doc in row["documentos"]:
                if doc["url"] not in checked:
                    response = self._fetch(doc["url"])
                    if not response.content.startswith(b"%PDF-"):
                        raise ValueError("Consultation attachment is not a PDF")
                    checked.add(doc["url"])
        return {**self._write(out_jsonl, rows), "coverage": "municipal_consultation_inventory", "source_urls": [SOURCE, *sorted(checked)]}

    def update_proyectos(self, out_jsonl, state_path):
        # Re-read the entire small inventory; no timestamp-based omissions.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        return {**self._write(out_jsonl, []), "disabled": True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
