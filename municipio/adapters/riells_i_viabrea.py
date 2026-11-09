"""Document-backed snapshot of Riells i Viabrea's public project inventory."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Comment

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = (
    "https://seu-e.cat/ca/web/riellsiviabrea/govern-obert-i-transparencia/"
    "accio-de-govern-i-normativa/urbanisme/informacio-publica-projectes-199"
)
LIMITATIONS = [
    "Partial coverage: current visible document-backed project inventory only; not a historical register.",
    "No granted licences, ordinances, service regulations or licence suspensions extracted.",
    "Dates are unknown: page-update, filename, partial month/year and parent-plan dates are not instrument dates.",
    "Document links retained; PDF contents, subsequent decisions and geometry are not parsed.",
    "Grouped documentary project records have no verified expediente identifier; entity policy does not mark them activity-eligible.",
    "The unlinked PAa-2 urbanisation paragraph is excluded; the mislabelled PAa-2 Plemen PDF is grouped with PAa-3 using reviewed document identity, retaining both source labels.",
    "No verified coordinates; publication_ready is false. Updates refresh the complete visible snapshot.",
]


def _text(node):
    return " ".join(node.get_text(" ", strip=True).split())


def _kind(title):
    t = title.casefold()
    if t.startswith(("suspensió", "ordenança", "informe", "memòria", "modificació del reglament")):
        return None
    if "reparcel·lació" in t:
        return "reparcelacion"
    if "modificació puntual" in t and "poum" in t:
        return "planeamiento_urbanistico"
    if t.startswith(("projecte", "pojecte", "aprovat inicialment el projecte", "pavimentació")):
        return "proyecto_tecnico"
    return None


class RiellsIViabreaAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug, config=None, base_url=""):
        super().__init__(slug, config, base_url or "https://riellsiviabrea.cat")

    @staticmethod
    def parse_projects(html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
            comment.extract()
        # No pagination in the reviewed static inventory. Fail closed if added.
        if soup.select('a[rel~="next"], .lfr-pagination a[href], .pagination a[href], .paginator a[href]'):
            raise ValueError("Inventory pagination detected; extend traversal before extracting")
        for link in soup.select("a[href]"):
            if _text(link).casefold() in {"següent", "següents", "siguiente", "next", "»"} and link["href"] not in {"", "#"}:
                raise ValueError("Inventory next-page link detected")
        headings = [h for h in soup.select(".journal-content-article h3")
                    if _text(h) == "Projectes en exposició pública"]
        if len(headings) != 1:
            raise ValueError("Missing or ambiguous official project inventory")
        container = headings[0].parent
        groups = []
        current = None
        section = ""

        def start(title):
            nonlocal current
            current = {"title": title, "section": section, "description": [], "docs": {}}
            groups.append(current)

        for block in container.find_all(["h3", "p", "ul"], recursive=False):
            if block.name == "h3":
                section = _text(block)
                current = None
                continue
            strong = block.select_one("li > strong") if block.name == "ul" else None
            if strong and not strong.find_parent("a"):
                start(_text(strong))
            elif block.name == "p":
                text = _text(block)
                # Reparcelling entries use paragraphs rather than strong titles.
                if section == "Projectes de reparcel·lació" or (
                    current is None and section == "Projectes d'urbanització"
                ):
                    start(text)
                elif current is not None and text:
                    current["description"].append(text)
            if current is not None:
                for link in block.select("a[href]"):
                    url = urljoin(SOURCE, link["href"])
                    parsed = urlparse(url)
                    if parsed.scheme != "https" or parsed.hostname not in {"seu-e.cat", "www.seu-e.cat"}:
                        raise ValueError("Unexpected document origin")
                    if not parsed.path.startswith("/documents/663872/13265083/"):
                        raise ValueError("Unexpected municipal document collection")
                    # Host aliases and query strings do not create duplicate documents.
                    url = parsed._replace(netloc="seu-e.cat", query="", fragment="").geturl()
                    current["docs"].setdefault(url, {"titulo": _text(link), "url": url, "source_url": SOURCE})
        # Reviewed primary PDF 33abae7d (cover, July 2024) explicitly identifies
        # PAa-3 Plemen despite its PAa-2 page label. The 3fd9dc10 agreement is
        # for that same reparcelling instrument (29 June 2022). Group versions
        # and component documents; do not create a second PAa-2 project.
        plemen_ids = {"33abae7d-fda3-4af6-b9c3-b4fb0495a269", "3fd9dc10-1147-4b75-9ef0-6a665b2f34ca"}
        merged = []
        plemen = None
        for group in groups:
            group["source_titles"] = [group["title"]]
            if any(url.rsplit("/", 1)[-1] in plemen_ids for url in group["docs"]):
                if plemen is not None:
                    plemen["source_titles"].append(group["title"])
                    plemen["docs"].update(group["docs"])
                    plemen["description"].extend(group["description"])
                    plemen["title"] = group["title"]
                    continue
                plemen = group
            merged.append(group)
        rows = []
        identities = set()
        for group in merged:
            kind = _kind(group["title"])
            if kind is None or not group["docs"]:
                continue
            docs = list(group["docs"].values())
            match = re.search(r"/([0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})$", docs[0]["url"])
            if not match:
                raise ValueError("Document lacks stable official UUID")
            identity = "riells-i-viabrea-proy-" + match[1]
            if identity in identities:
                raise ValueError("Document assigned to multiple instruments")
            identities.add(identity)
            narrative = " ".join([group["title"]] + [d["titulo"] for d in docs]).casefold()
            phase = "aprobación inicial" if re.search(r"aprova(?:ció|r|t) inicial", narrative) else None
            rows.append({
                "id": identity, "municipio": "Riells i Viabrea", "codigo_ine": "17146",
                "provincia": "Girona", "titulo": group["title"], "tipo": kind,
                "fase": phase, "seccion_fuente": group["section"],
                "titulos_fuente": group["source_titles"],
                "nota_fuente": (
                    "PAa-2 label on the inventory conflicts with the linked PDF cover identifying PAa-3 Plemen; versions grouped by reviewed document identity."
                    if group is plemen else None
                ),
                "descripcion": "\n".join(group["description"]) or None,
                "fecha": None, "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
                "url": SOURCE, "url_documento": docs[0]["url"], "documentos": docs,
                "source": "ayuntamiento", "origen": "informacion_publica_proyectos",
                "source_entity_type": "documento",
                "lat": None, "lon": None, "geometry": None, "publication_ready": False,
            })
        if not rows:
            raise ValueError("No document-backed project records found")
        return rows

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        with requests.get(SOURCE, timeout=(15, 60), stream=True, headers={
            "User-Agent": self.config.get("user_agent", "municipio-riells-i-viabrea/1.0")
        }) as response:
            response.raise_for_status()
            if urlparse(response.url).hostname not in {"seu-e.cat", "www.seu-e.cat"}:
                raise ValueError("Unexpected inventory redirect")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 4_000_000:
                    raise ValueError("Inventory exceeds response size limit; no truncated extraction")
            html = data.decode("utf-8")
        rows = self.parse_projects(html)
        if self.config.get("evidence_dir"):
            capture = Path(self.config["evidence_dir"])
            capture.mkdir(parents=True, exist_ok=True)
            (capture / "inventory.html").write_bytes(data)
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": [SOURCE], "limitations": LIMITATIONS}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0, "reason": "Granted-licence extraction outside this adapter's coverage"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)
