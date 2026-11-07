"""Planning inventory in the POUM viewer linked by the municipality.

The viewer is a consultation copy, not the normative RPUC register. Traverse
the complete public jsTree API; group base-plan pieces and numbered instruments.
No PDF date, filename year or page-update timestamp is an approval date here.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode, urljoin

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

MUNICIPAL = "https://santsadurni.cat/urbanisme"
VIEWER = "https://mapa.psig.es/ssa/"
TREE = VIEWER + "normativas/"
SERVER_PREFIX = "/var/www/mapa/ssa/normativas/"
LATER = "8 Planejament aprovat definitivament a partir del 30 de setembre de 2010 (No refós al SIG del POUM)"
LIMITATIONS = [
    "Partial coverage: municipal-linked viewer inventory, not the complete RPUC or notice-board history.",
    "Viewer documents are consultation copies; normative validity and subsequent court decisions require RPUC verification.",
    "Only POUM, its modifications and special plans; independent agreements, judgments, TUC and acoustic maps excluded.",
    "PDF contents are not parsed: all agreement, approval and publication dates remain null; filename years are documentary labels only.",
    "No verified project geometry or coordinates; publication_ready=false. Licences and scheduling disabled.",
    "The shared entity guard cannot classify inventory-only instrument identities without dossier references; no expediente numbers are invented.",
]


def check_provenance(municipal_html, viewer_html):
    municipal = BeautifulSoup(municipal_html, "html.parser")
    if not any(urljoin(MUNICIPAL, a["href"]).rstrip("/") in
               {VIEWER.rstrip("/"), VIEWER.replace("https:", "http:").rstrip("/")}
               for a in municipal.select("a[href]")):
        raise ValueError("Municipality no longer links the reviewed POUM viewer")
    viewer = BeautifulSoup(viewer_html, "html.parser")
    text = viewer.get_text(" ", strip=True)
    if "POUM" not in text or "valor normatiu" not in text:
        raise ValueError("Viewer no longer exposes reviewed POUM provenance")
    if not any(urljoin(VIEWER, a.get("src", "")) == TREE for a in viewer.select("iframe[src]")):
        raise ValueError("Planning document inventory moved")


def walk_inventory(fetch_json):
    """Visit every lazy folder and inline child; reject limits/cycles, never truncate."""
    leaves, seen = [], set()

    def walk(nodes, depth=0):
        if not isinstance(nodes, list) or depth > 20:
            raise ValueError("Invalid or excessively deep planning tree")
        for node in nodes:
            if not isinstance(node, dict) or not all(k in node for k in ("id", "text", "children")):
                raise ValueError("Invalid planning node")
            key = node["id"]
            if not isinstance(key, str) or not isinstance(node["text"], str):
                raise ValueError("Invalid node identity")
            if key in seen or len(seen) >= 3000:
                raise ValueError("Repeated node or planning inventory exceeds reviewed safety bound")
            seen.add(key)
            children = node["children"]
            if isinstance(children, list):
                walk(children, depth + 1)
            elif children is True:
                walk(fetch_json("get_node", key), depth + 1)
            elif children is False:
                leaves.append(node)
            else:
                raise ValueError("Unknown child/pagination representation")

    root = fetch_json("get_node", "#")
    if (not isinstance(root, list) or len(root) != 1
            or root[0].get("text") != "POUM Sant Sadurní d'Anoia (aprovació definitiva)"):
        raise ValueError("Unexpected municipality or planning root")
    walk(root)
    if not leaves:
        raise ValueError("Empty planning inventory")
    return leaves


def group_instruments(leaves):
    groups = {"poum": {"titulo": "Pla d'ordenació urbanística municipal de Sant Sadurní d'Anoia (POUM)",
                       "tipo": "planeamiento_urbanistico", "nodes": []}}
    excluded = []
    for node in leaves:
        key, title = node["id"], node["text"]
        parts = key.split("/")
        base = re.match(r"^[1-6] ", parts[0])
        if base and title.lower().endswith(".pdf"):
            groups["poum"]["nodes"].append(node)
        elif key.startswith(LATER + "/3 Convenis urbanístics/1 POUM/") and title.lower().endswith(".pdf"):
            groups["poum"]["nodes"].append(node)
        elif len(parts) == 3 and parts[0] == LATER and parts[1] in {"1 Planejament general", "2 Planejament derivat"}:
            match = re.fullmatch(r"(\d+)\s+(\d{4})\s+(Mod POUM|PE)\s+(.+)\.pdf", title, re.I)
            if match:
                number, year, kind, name = match.groups()
                identity = parts[1] + "/" + number + "/" + year
                group = groups.setdefault(identity, {
                    "titulo": ("Modificació del POUM — " if kind.lower() == "mod poum" else "Pla especial — ") + name,
                    "tipo": "modificacion_planeamiento" if kind.lower() == "mod poum" else "plan_especial",
                    "anio_etiqueta_documental": year, "nodes": [],
                })
                group["nodes"].append(node)
            elif "Resolució recurs" in title or "Sentència" in title:
                excluded.append({"id": key, "reason": "Administrative/judicial decision, not a separate planning instrument"})
            else:
                raise ValueError("Unrecognized instrument in reviewed planning category: " + title)
        else:
            excluded.append({"id": key, "reason": "Outside selected planning instruments or non-PDF viewer resource"})
    if not groups["poum"]["nodes"]:
        raise ValueError("Base POUM has no documents")
    return groups, excluded


def document_url(payload):
    if not isinstance(payload, dict) or payload.get("type") != "pdf":
        raise ValueError("Expected a PDF content pointer")
    content = payload.get("content", "")
    if not isinstance(content, str) or not content.startswith(SERVER_PREFIX + "data/") or not content.lower().endswith(".pdf"):
        raise ValueError("Unexpected document provenance")
    relative = content[len(SERVER_PREFIX):]
    if any(p in {"..", "."} for p in relative.split("/")):
        raise ValueError("Unsafe document path")
    return TREE + quote(relative, safe="/")


class SantSadurniDAnoiaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or "https://santsadurni.cat")

    def backfill_proyectos(self, out_jsonl: Path):
        captures = Path(self.config["evidence_dir"]) if self.config.get("evidence_dir") else None
        if captures:
            captures.mkdir(parents=True, exist_ok=True)
        sources = []
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-sant-sadurni-d-anoia/1.0"

            def fetch(url):
                with session.get(url, timeout=(10, 40), stream=True) as response:
                    response.raise_for_status()
                    if response.url != url:
                        raise ValueError("Unexpected source redirect: " + response.url)
                    data = bytearray()
                    for chunk in response.iter_content(65536):
                        data.extend(chunk)
                        if len(data) > 4_000_000:
                            raise ValueError("Inventory response exceeds reviewed bound")
                    sources.append(url)
                    if captures:
                        (captures / (hashlib.sha256(url.encode()).hexdigest() + ".capture")).write_bytes(data)
                    charset = requests.utils.get_encoding_from_headers(response.headers) or "utf-8-sig"
                    return bytes(data).decode(charset)

            check_provenance(fetch(MUNICIPAL), fetch(VIEWER))
            shell = fetch(TREE)
            if "?operation=get_node" not in shell or "?operation=get_content" not in shell:
                raise ValueError("Document tree API changed")

            def api(operation, key):
                return json.loads(fetch(TREE + "?" + urlencode({"operation": operation, "id": key})))

            groups, excluded = group_instruments(walk_inventory(api))
            rows = []
            for identity, group in groups.items():
                documents = {}
                nodes = group.pop("nodes")
                for node in nodes:
                    url = document_url(api("get_content", node["id"]))
                    documents.setdefault(url, {"titulo": node["text"], "url": url,
                                               "id_origen": node["id"], "url_fuente": TREE})
                rows.append({
                    **group,
                    "id": "sant-sadurni-proy-" + hashlib.sha256(identity.encode()).hexdigest()[:16],
                    "id_origen": "/" if identity == "poum" else nodes[0]["id"],
                    "grupo_inventario": identity, "source_entity_type": "instrumento_planeamiento",
                    "municipio": "Sant Sadurní d'Anoia", "codigo_ine": "08240",
                    "provincia": "Barcelona", "source": "ayuntamiento", "origen": "visor_poum_municipal",
                    "url": VIEWER, "url_inventario": TREE, "url_procedencia_municipal": MUNICIPAL,
                    "documentos": list(documents.values()), "url_documento": next(iter(documents)),
                    "fase": "aprobación definitiva (según clasificación del inventario)",
                    "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
                    "lat": None, "lon": None, "geometry": None, "publication_ready": False,
                    "descripcion": "Instrumento publicado en el visor enlazado por el Ayuntamiento. Copia de consulta sin valor normativo; fechas y vigencia jurídica no verificadas en los PDF.",
                })
        path = Path(out_jsonl)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(path)
        report = {"status": "ok", "rows": len(rows), "live_records": len(rows),
                  "checked_at": datetime.now(timezone.utc).isoformat(),
                  "documents": sum(len(r["documentos"]) for r in rows),
                  "source_urls": sources, "excluded_inventory_leaves": excluded,
                  "limitations": LIMITATIONS, "publication_ready": False}
        if captures:
            (captures / "validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Complete snapshot: every lazy folder is refreshed on each update.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        return {"status": "disabled", "rows": 0, "reason": "No verified granted-licence inventory"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
