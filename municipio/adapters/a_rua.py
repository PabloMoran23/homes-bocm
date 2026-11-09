"""A Rúa (32072): municipal planning inventory published by Xunta/SIOTUGA."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://siotuga.xunta.gal/siotuga/"
INVENTORY = BASE + "inventario?inv=1&idconcello=32072"
QUERY = BASE + "assets/inventario/query_document.php"
DETAIL = BASE + "assets/inventario/getIOTPU.php"
CLASSES = {14: "planeamiento_general", 13: "planeamiento_desarrollo",
           16: "planeamiento_historico", 18: "delimitacion_nucleo_rural"}


def parse_inventory(payload):
    # These endpoints return the entire array; DataTables paginates locally.
    # Refuse envelopes (including future server pagination), never take a slice.
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError("Expected complete SIOTUGA array, not pagination envelope")
    result = {}
    for item in payload:
        if not isinstance(item, dict) or not str(item.get("id", "")).isdigit():
            raise ValueError("Invalid planning instrument identity")
        if not item.get("docnome") or not item.get("figura"):
            raise ValueError("Missing planning instrument title/type")
        key = str(item["id"])
        if key in result and result[key] != item:
            raise ValueError("Conflicting inventory entries")
        result[key] = item
    return list(result.values())


def parse_instrument(item, detail, category):
    general = detail["datos_xerais"]
    key = str(item["id"])
    if (str(general["id"]) != key or general["folder"] != "ARUA"
            or general["menutitle"] != "Rúa, A"):
        raise ValueError("Detail does not belong to this A Rúa instrument")
    row = {
        "id": "a-rua-siotuga-" + key, "source_id": key,
        "municipio": "A Rúa", "codigo_ine": "32072", "provincia": "Ourense",
        "titulo": item["docnome"].strip(), "tipo": item["figura"],
        "categoria_inventario": category,
        "url": INVENTORY, "inventory_url": INVENTORY,
        "source": "siotuga_xunta", "organismo_fuente": "Xunta de Galicia",
        "origen": "inventario_planeamiento_municipal",
        "source_entity_type": "documento",
        "provenance": {"inventory_endpoint": QUERY, "inventory_method": "POST",
                       "inventory_parameters": {"id": "32072", "idclase": next(
                           c for c, label in CLASSES.items() if label == category)},
                       "detail_endpoint": DETAIL, "detail_method": "POST",
                       "detail_parameters": {"iddoc": key, "idp": 0, "lang": "gl_ES"}},
        "publication_ready": False, "geometry_status": "unavailable",
        "vigencia_verificada": False,
        "incidencias_juridicas": detail.get("incidencias_iuris"),
        "incidencias_inventario": item.get("incidencias_iuris"),
    }
    # Preserve distinct explicit source meanings; never infer agreement dates.
    for field, target in {"fechaaddef": "fecha_aprob", "fechabop": "fecha_publicacion_bop",
                          "fechadog": "fecha_publicacion_dog",
                          "fechanormativabop": "fecha_publicacion_normativa_bop"}.items():
        value = item.get(field)
        if value:
            row[target] = date.fromisoformat(value).isoformat()
    row["fechas_fuente"] = {k: general.get(k) for k in (
        "fechaaddef", "fechabop", "fechadog", "fechanormativabop", "fechatextodef")}
    docs = {}
    for group in detail["elementos"] or []:
        for component in group["componentes"] or []:
            url = urljoin(BASE, general["filesroot"] + general["folder"]
                          + "/documents/" + component["pathesperado"])
            if (urlparse(url).hostname != "siotuga.xunta.gal" or
                    not urlparse(url).path.startswith("/siotuga/documentos/urbanismo/ARUA/documents/")):
                raise ValueError("Unexpected document origin")
            docs[url] = {"titulo": component["descripcion"], "url": url,
                         "grupo": group["description"], "source_id": str(component["id"])}
    row["documentos"] = list(docs.values())
    row["documentacion_status"] = "enlaces_inventariados" if docs else "sin_documentos_en_plataforma"
    return row


class ARuaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        captures = self.config.get("evidence_dir")
        def capture(name, content):
            if captures:
                dest = Path(captures)
                dest.mkdir(parents=True, exist_ok=True)
                (dest / name).write_bytes(content)

        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-a-rua/1.0 (public planning inventory)"
            def fetch(url, name, data=None):
                response = session.get(url, timeout=40) if data is None else session.post(
                    url, data=data, timeout=40)
                response.raise_for_status()
                if urlparse(response.url).hostname != "siotuga.xunta.gal":
                    raise ValueError("Unexpected source redirect")
                capture(name, response.content)
                return response

            response = fetch(INVENTORY, "inventory.html")
            soup = BeautifulSoup(response.content, "html.parser")
            # Anonymous public form token; no account or credentials involved.
            token = soup.select_one("#token")["value"]
            if not soup.select_one('#idconcello option[value="32072"]'):
                raise ValueError("Municipality missing from source selector")
            rows = {}
            for cls, category in CLASSES.items():
                payload = fetch(QUERY, f"class-{cls}.json", {
                    "id": "32072", "idclase": cls, "token": token}).json()
                for item in parse_inventory(payload):
                    key = str(item["id"])
                    if key in rows:
                        raise ValueError("Instrument repeated across inventory categories")
                    detail = fetch(DETAIL, f"doc-{key}.json", {
                        "iddoc": key, "idp": 0, "lang": "gl_ES", "token": token}).json()
                    rows[key] = parse_instrument(item, detail, category)
        if not rows:
            raise ValueError("No usable A Rúa planning inventory")
        self._write(out_jsonl, list(rows.values()))
        return {"count": len(rows), "written": len(rows),
                "coverage": "SIOTUGA municipal planning categories 14,13,16,18; full snapshot"}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
