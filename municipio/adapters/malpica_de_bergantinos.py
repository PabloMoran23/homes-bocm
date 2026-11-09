"""Municipal planning instruments from the Xunta's public SIOTUGA inventory.

The inventory uses complete JSON arrays and client-side DataTables pagination.
No licence grants or current legal validity are inferred from this catalogue.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://siotuga.xunta.gal/siotuga/"
SOURCE = BASE + "inventario.php?inv=1&idconcello=15043"
CLASSES = {14: "planeamiento_general", 13: "planeamiento_desarrollo",
           16: "planeamiento_historico", 18: "delimitacion_nucleo_rural"}
LIMITATIONS = [
    "Cobertura parcial: sólo el inventario urbanístico SIOTUGA del INE 15043, "
    "incluido su apartado histórico; no es un registro de obras ni de licencias.",
    "No incluye planeamiento en tramitación fuera del inventario: la modificación "
    "puntual nº 4 publicada en DOG 21/07/2025 no figura en esta consulta.",
    "La aprobación catalogada no acredita vigencia actual. Fechas BOP, DOG y "
    "normativa conservadas separadamente; no se resuelven discrepancias del catálogo.",
    "Algunas fichas carecen de documentos digitalizados. Enlaces conservados "
    "según la ficha; no se verifica en cada ejecución cada archivo enlazado.",
    "Sin geometría vectorial verificada por instrumento; no se asignan coordenadas.",
]


def _date(value):
    if value is None or value == "":
        return None
    return date.fromisoformat(value).isoformat()


def parse_inventory(payload):
    """Reject pagination envelopes/errors rather than accepting a partial page."""
    if payload is None:
        return []  # SIOTUGA's explicit empty-category response
    if not isinstance(payload, list):
        raise ValueError("Expected complete SIOTUGA array, not a page/envelope")
    rows = {}
    for row in payload:
        if not isinstance(row, dict) or not str(row.get("id", "")).isdigit():
            raise ValueError("Invalid instrument identity")
        if not row.get("docnome") or not row.get("figura"):
            raise ValueError("Missing planning title/type")
        for key in ("fechaaddef", "fechabop", "fechadog", "fechanormativabop"):
            _date(row.get(key))
        identity = str(row["id"])
        if identity in rows and rows[identity] != row:
            raise ValueError("Conflicting duplicate instrument")
        rows[identity] = row
    return list(rows.values())


def parse_instrument(row, detail, category):
    if not isinstance(detail, dict) or not isinstance(detail.get("datos_xerais"), dict):
        raise ValueError("Missing SIOTUGA instrument detail")
    info = detail["datos_xerais"]
    if str(info.get("id")) != str(row["id"]) or info.get("menutitle") != "Malpica de Bergantiños":
        raise ValueError("Detail municipality/identity mismatch")
    if info.get("denominacion", "").strip() != row["docnome"].strip() or info.get("figura") != row["figura"]:
        raise ValueError("Inventory/detail title or type mismatch")
    for key in ("fechaaddef", "fechabop", "fechadog", "fechanormativabop"):
        if _date(info.get(key)) != _date(row.get(key)):
            raise ValueError("Inventory/detail date mismatch")
    if "elementos" not in detail:
        raise ValueError("Missing document inventory")
    elements = detail["elementos"]
    if elements is not None and not isinstance(elements, list):
        raise ValueError("Invalid document inventory")
    docs = {}
    for element in elements or []:
        if not isinstance(element.get("componentes"), list):
            raise ValueError("Invalid document group")
        for item in element["componentes"]:
            filename = item.get("pathesperado", "")
            if not re.fullmatch(r"[\w.-]+\.(?:pdf|jpg|jpeg|png|zip)", filename, re.I):
                raise ValueError("Unexpected document path")
            root = urljoin(BASE, info.get("filesroot", ""))
            url = urljoin(root, info.get("folder", "") + "/documents/" + filename)
            if urlparse(url).hostname != "siotuga.xunta.gal" or "/MALPICADEBERGANTINOS/documents/" not in url:
                raise ValueError("Document provenance changed")
            doc = {"id_origen": str(item["id"]), "titulo": item["descripcion"],
                   "grupo": element["description"], "url": url}
            # Historical catalogues can reuse a file for distinct component IDs
            # and captions. Retain both catalogue entries without losing labels.
            component_key = (doc["id_origen"], url)
            if component_key in docs and docs[component_key] != doc:
                raise ValueError("Conflicting document metadata")
            docs[component_key] = doc
    return {
        "id": "malpica-de-bergantinos-siotuga-" + str(row["id"]),
        "id_origen": str(row["id"]), "municipio": "Malpica de Bergantiños",
        "codigo_ine": "15043", "provincia": "A Coruña",
        "titulo": row["docnome"].strip(), "tipo": row["figura"],
        "categoria_inventario": CLASSES[category], "historico": category == 16,
        "fecha": None, "fecha_acuerdo": None,
        "fecha_aprob": _date(row.get("fechaaddef")),
        "fecha_aprob_tipo": "aprobacion_definitiva_segun_catalogo",
        "fecha_publicacion": None,
        "fecha_publicacion_bop": _date(row.get("fechabop")),
        "fecha_publicacion_dog": _date(row.get("fechadog")),
        "fecha_publicacion_normativa_bop": _date(row.get("fechanormativabop")),
        "fecha_texto_refundido": _date(info.get("fechatextodef")),
        "incidencias_juridicas": detail.get("incidencias_iuris"),
        "incidencias_inventario": row.get("incidencias_iuris"),
        "url": SOURCE, "source": "siotuga", "origen": "inventario_urbanistico_xunta",
        "source_dataset": BASE + "assets/inventario/query_document.php",
        "source_request": {"method": "POST", "id": "15043", "idclase": category},
        "detail_source": {"url": BASE + "assets/inventario/getIOTPU.php",
                          "method": "POST", "iddoc": str(row["id"]), "idp": 0, "lang": "es_ES"},
        "documentos": list(docs.values()),
        "documentos_status": "enlaces_catalogados" if docs else "sin_documentos_digitalizados_en_ficha",
        "lat": None, "lon": None, "geometry": None,
        "geometry_status": "unavailable", "publication_ready": False,
    }


class MalpicaDeBergantinosAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        tmp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        captures = Path(self.config["evidence_dir"]) if self.config.get("evidence_dir") else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        source_urls = [SOURCE]
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-malpica-inventory/1.0"
            response = session.get(SOURCE, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")
            selected = soup.select_one('#idconcello option[value="15043"]')
            if not selected or selected.get_text(strip=True) != "Malpica de Bergantiños":
                raise ValueError("Municipal inventory identity missing")
            # Public anonymous form nonce, obtained only from the public page.
            nonce = soup.select_one("#token")
            if not nonce or not nonce.get("value"):
                raise ValueError("Public inventory form changed")
            form_nonce = nonce["value"]
            nonce["value"] = "REDACTED_PUBLIC_FORM_NONCE"
            if captures:
                (captures / "live-inventario.html").write_text(str(soup), encoding="utf-8")

            def fetch(endpoint, params, name):
                url = BASE + "assets/inventario/" + endpoint
                time.sleep(.15)
                result = session.post(url, data={**params, "token": form_nonce}, timeout=30)
                result.raise_for_status()
                payload = result.json()
                source_urls.append(url)
                if captures:
                    (captures / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                return payload

            inventory = {}
            for category in CLASSES:
                payload = fetch("query_document.php", {"id": "15043", "idclase": category}, f"live-class-{category}.json")
                for row in parse_inventory(payload):
                    identity = str(row["id"])
                    if identity in inventory:
                        raise ValueError("Instrument appears in multiple inventory categories")
                    inventory[identity] = (row, category)
            if not inventory:
                raise ValueError("Empty municipal planning inventory requires review")
            rows = []
            for identity, (row, category) in sorted(inventory.items()):
                detail = fetch("getIOTPU.php", {"iddoc": identity, "idp": 0, "lang": "es_ES"}, f"live-detail-{identity}.json")
                rows.append(parse_instrument(row, detail, category))
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": sorted(set(source_urls)),
                "limitations": LIMITATIONS, "publication_ready": False}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh the complete catalogue; never use an approval-date watermark."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
