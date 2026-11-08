"""Selected physical/planning proposals in Alfaro's official Agenda Urbana.

This is a current document inventory, not a register of approved instruments.
Dates in upload paths and CMS timestamps are deliberately not agreement dates.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://alfaro.es/agendaurbana/plan-de-accion-alfaro/"
# Deliberately bounded subject coverage. Other Agenda actions include social,
# employment and governance programmes, which are not physical projects.
SUBJECTS = {
    "itinerarios": (r"creacion de itinerarios", "creacion-de-red-de-itinerarios"),
    "convento": (r"rehabilitacion convento", "rehabilitacion-del-convento"),
    "ceramicas": (r"peri ceramicas", "sostenibilidad-economica-del-peri-ceramicas"),
    "palacio": (r"peri palacio", "peri-palacio-remirez"),
    "movilidad": (r"plan de movilidad urbana sostenible", "estrategia-de-mobilidad"),
    "cuevas": (r"peri zona cuevas", None),
}


def normalize(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def official(url):
    parsed = urlparse(url)
    return (parsed.scheme == "https" and parsed.hostname == "alfaro.es"
            and parsed.path.startswith("/agendaurbana/"))


def check_pagination(soup):
    # The reviewed inventory is one page. Fail rather than silently drop a new
    # pagination scheme; numbered controls and next links are both detected.
    for a in soup.select("a[href]"):
        label = normalize(a.get_text(" ", strip=True))
        if ("next" in a.get("rel", []) or label in {"siguiente", "next", "»", "›"}
                or "page-numbers" in a.get("class", [])
                or re.search(r"[?&](?:paged|page)=\d+|/page/\d+", a["href"])):
            raise ValueError("Inventory pagination detected; crawler must be extended")


def parse_inventory(html, url=SOURCE):
    soup = BeautifulSoup(html, "html.parser")
    check_pagination(soup)
    actions, documents = {}, {}
    for a in soup.select("a[href]"):
        target = urljoin(url, a["href"])
        if not official(target):
            continue
        title = a.get_text(" ", strip=True)
        match = re.fullmatch(r"3\.(\d+)\s*[–—-]\s*Acción\s*\((\d+)\)\s*(.+)", title)
        if match:
            number, second, name = match.groups()
            if number != second or not urlparse(target).path.endswith(f"/accion-{number}/"):
                raise ValueError("Action label/URL mismatch")
            previous = actions.get(number)
            action = {"number": number, "titulo": name, "url": target}
            if previous and previous != action:
                raise ValueError("Conflicting action entries")
            actions[number] = action
        if urlparse(target).path.lower().endswith(".pdf"):
            documents[target] = normalize(unquote(urlparse(target).path))
    selected = []
    for action in actions.values():
        for subject, (pattern, doc_token) in SUBJECTS.items():
            if re.search(pattern, normalize(action["titulo"])):
                docs = [{"titulo": unquote(urlparse(u).path.rsplit("/", 1)[-1]),
                         "url": u, "source_url": url, "relacion": "ficha de la actuación"}
                        for u, path in documents.items() if doc_token and doc_token in path]
                if doc_token and not docs:
                    raise ValueError(f"Missing reviewed action document: {subject}")
                selected.append({**action, "subject": subject, "documentos": docs})
                break
    if not selected:
        raise ValueError("No supported physical/planning proposals in inventory")
    return selected, len(actions)


def parse_detail(html, action):
    soup = BeautifulSoup(html, "html.parser")
    heading = soup.select_one("h1")
    if not heading or normalize(heading.get_text(" ", strip=True)) != normalize(action["titulo"]):
        raise ValueError("Action detail title differs from inventory")
    label = soup.find(lambda tag: tag.name in {"h2", "h3"}
                      and tag.get_text(" ", strip=True) == "Descripción de la acción")
    widget = label.find_parent(class_="elementor-widget-heading") if label else None
    sibling = widget.find_next_sibling() if widget else None
    if not sibling or "elementor-widget-text-editor" not in sibling.get("class", []):
        raise ValueError("Missing action description section")
    description = sibling.get_text(" ", strip=True)
    if not description:
        raise ValueError("Empty action description")
    # The detail is itself a source document, even for Cuevas (no separate PDF).
    docs = {action["url"]: {"titulo": action["titulo"], "url": action["url"],
                            "relacion": "ficha HTML de la actuación"}}
    docs.update({d["url"]: d for d in action["documentos"]})
    return {
        "id": "alfaro-agenda-accion-" + action["number"],
        "municipio": "Alfaro", "provincia": "La Rioja", "codigo_ine": "26011",
        "titulo": action["titulo"], "tipo": "actuacion_planificada_agenda_urbana",
        "naturaleza": "propuesta descrita en la Agenda Urbana municipal",
        "descripcion": description, "url": action["url"], "inventory_url": SOURCE,
        "source": "ayuntamiento", "origen": "agenda_urbana_fichas_actuaciones",
        "documentos": list(docs.values()),
        "publication_ready": False, "geometry_status": "unavailable",
    }


class AlfaroAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        if not official(url):
            raise ValueError("Unexpected source URL")
        response = requests.get(url, timeout=40, headers={
            "User-Agent": "municipio-inventory/1.0 (public planning documents)"})
        response.raise_for_status()
        if not official(response.url):
            raise ValueError("Unexpected source redirect")
        if "text/html" not in response.headers.get("Content-Type", ""):
            raise ValueError("Expected HTML source")
        if self.config.get("capture_dir"):
            directory = Path(self.config["capture_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".html"
            (directory / name).write_bytes(response.content)
        response.encoding = "utf-8"
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        actions, total = parse_inventory(self._fetch(SOURCE))
        rows = [parse_detail(self._fetch(a["url"]), a) for a in actions]
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "inventory_actions": total,
                "excluded_actions": total - len(rows), "coverage": "selected_agenda_proposals",
                "source_urls": [SOURCE] + [a["url"] for a in actions]}

    def update_proyectos(self, out_jsonl, state_path):
        # Full refresh: the source has no trustworthy incremental change feed.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
