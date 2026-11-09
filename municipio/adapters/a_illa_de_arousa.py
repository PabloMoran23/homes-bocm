"""Municipal planning inventory linked by the Concello, served by SIOTUGA."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://siotuga.xunta.gal/siotuga/"
MUNICIPAL_SOURCE = "https://www.ailladearousa.es/urbanismo-obras-e-deportes/"
INVENTORY = BASE + "inventario.php?inv=1&idconcello=36901"
QUERY = BASE + "assets/inventario/query_document.php"
DETAIL = BASE + "assets/inventario/getIOTPU.php"
CLASSES = {14: "planeamento_xeral", 13: "planeamento_desenvolvemento"}
LIMITATIONS = [
    "Snapshot of SIOTUGA general and development planning for INE 36901 only; "
    "historical planning, rural delimitations, territorial instruments, pending plans and public works are outside coverage.",
    "Inventory approval/publication metadata is transcribed, not independently certified; "
    "no inference of current legal validity, granted licences or construction activity.",
    "Document links are retained; document contents and geometries are not extracted. "
    "Some identified instruments have no downloadable components in SIOTUGA. "
    "No invented coordinates; publication_ready=false.",
]


def inventory_rows(payload):
    """The official UI receives a complete array and paginates it in the browser."""
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError("Expected complete SIOTUGA array, not a paginated envelope")
    rows = {}
    for row in payload:
        if not isinstance(row, dict) or not str(row.get("id", "")).isdigit():
            raise ValueError("Invalid planning inventory identity")
        key = str(row["id"])
        if key in rows and rows[key] != row:
            raise ValueError("Conflicting planning inventory identities")
        rows[key] = row
    return list(rows.values())


def _date(value):
    if value in (None, ""):
        return None
    return date.fromisoformat(value).isoformat()


def parse_document(row, detail, class_id):
    """One instrument per SIOTUGA id, with all its documentary components."""
    general = detail["datos_xerais"]
    if (str(general["id"]) != str(row["id"])
            or general["menutitle"] != "Illa de Arousa, A"
            or general["folder"] != "ILLADEAROUSA"):
        raise ValueError("Document identity or municipality mismatch")
    title = general.get("denominacion")
    kind = general.get("figura")
    if not title or not kind or kind != row["figura"]:
        raise ValueError("Missing or inconsistent instrument title/type")
    # Prevent a changed API from quietly mixing agreement and publication dates.
    dates = {}
    for field in ("fechaaddef", "fechabop", "fechadog", "fechanormativabop"):
        dates[field] = _date(general.get(field))
        if dates[field] != _date(row.get(field)):
            raise ValueError("Inventory/detail date mismatch: " + field)
    documents = {}
    root = general["filesroot"] + general["folder"] + "/documents/"
    for group in detail["elementos"] or []:
        for component in group["componentes"]:
            target = urljoin(BASE, root + quote(component["pathesperado"], safe="/"))
            parsed = urlparse(target)
            if (parsed.scheme != "https" or parsed.hostname != "siotuga.xunta.gal"
                    or not parsed.path.startswith("/siotuga/documentos/urbanismo/ILLADEAROUSA/documents/")
                    or ".." in parsed.path.split("/")):
                raise ValueError("Unexpected municipal document URL")
            document = {
                "id": str(component["id"]), "titulo": component["descripcion"],
                "grupo": group["description"], "url": target,
                "source_url": DETAIL, "source_id": str(row["id"]),
            }
            key = (document["id"], target)
            if key in documents and documents[key] != document:
                raise ValueError("Conflicting document component")
            documents[key] = document
    return {
        "id": "a-illa-de-arousa-siotuga-" + str(row["id"]),
        "id_origen": str(row["id"]), "municipio": "A Illa de Arousa",
        "codigo_ine": "36901", "provincia": "Pontevedra",
        "titulo": kind + " — " + title if kind.casefold() != title.casefold() else title,
        "denominacion": title, "tipo": kind,
        "fecha": None, "fecha_acuerdo": None,
        "fecha_aprob": dates["fechaaddef"],
        "fecha_publicacion": None,
        "fecha_publicacion_dog": dates["fechadog"],
        "fecha_publicacion_bop": dates["fechabop"],
        "fecha_publicacion_normativa_bop": dates["fechanormativabop"],
        "fecha_texto_refundido": _date(general.get("fechatextodef")),
        "incidencias_iuris": detail.get("incidencias_iuris"),
        "source": "ayuntamiento", "origen": "siotuga_inventario_municipal",
        "source_authority": "Xunta de Galicia", "municipal_source_url": MUNICIPAL_SOURCE,
        "url": INVENTORY, "source_dataset": QUERY,
        "source_request": {"id": "36901", "idclase": class_id},
        "detail_source": {"url": DETAIL, "method": "POST", "iddoc": str(row["id"]), "idp": "0"},
        "inventory_section": CLASSES[class_id], "documentos": list(documents.values()),
        "document_status": "links_available" if documents else "no_components_in_source",
        "lat": None, "lon": None, "geometry": None,
        "publication_ready": False, "geometry_status": "unavailable",
        "coverage": "partial_municipal_planning_inventory",
    }


class AIllaDeArousaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or MUNICIPAL_SOURCE)

    def _capture(self, name, content):
        if self.config.get("evidence_dir"):
            folder = Path(self.config["evidence_dir"])
            folder.mkdir(parents=True, exist_ok=True)
            (folder / name).write_bytes(content)

    def backfill_proyectos(self, out_jsonl: Path):
        records = {}
        source_urls = [MUNICIPAL_SOURCE, INVENTORY, QUERY, DETAIL]
        counts = {}
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-a-illa-de-arousa/1.0"
            response = session.get(INVENTORY, timeout=45)
            response.raise_for_status()
            if urlparse(response.url).hostname != "siotuga.xunta.gal":
                raise ValueError("Unexpected inventory redirect")
            soup = BeautifulSoup(response.content, "html.parser")
            selected = soup.select_one('#idconcello option[value="36901"]')
            if not selected or selected.get_text(strip=True) != "Illa de Arousa, A":
                raise ValueError("Municipality missing from official inventory")
            token = soup.select_one("input#token")
            if not token or not token.get("value"):
                raise ValueError("Public inventory session field missing")
            self._capture("live-inventario.html", response.content)

            def post(url, parameters, capture):
                result = session.post(url, data={**parameters, "token": token["value"]}, timeout=45)
                result.raise_for_status()
                if urlparse(result.url).hostname != "siotuga.xunta.gal":
                    raise ValueError("Unexpected API redirect")
                self._capture(capture, result.content)
                return result.json()

            for class_id in CLASSES:
                rows = inventory_rows(post(QUERY, {"id": "36901", "idclase": class_id}, f"live-class-{class_id}.json"))
                counts[str(class_id)] = len(rows)
                for row in rows:
                    detail = post(DETAIL, {"iddoc": row["id"], "idp": "0", "lang": "gl_ES"}, f'live-detail-{row["id"]}.json')
                    record = parse_document(row, detail, class_id)
                    key = record["id"]
                    if key in records and records[key] != record:
                        raise ValueError("Instrument unexpectedly spans inventory classes")
                    records[key] = record
        if not records:
            raise ValueError("No usable municipal planning instruments found")
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records.values()), encoding="utf-8")
        return {"status": "ok", "rows": len(records), "class_counts": counts,
                "source_urls": source_urls, "limitations": LIMITATIONS,
                "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete refresh: no timestamp cursor can silently hide older instruments.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"status": "disabled", "rows": 0,
                "reason": "No verified granted-licence register; application forms excluded"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
