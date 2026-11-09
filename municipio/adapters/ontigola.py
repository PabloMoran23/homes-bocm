"""Ontígola: current JCCM agreement inventory, grouped by planning instrument.

This is a partial regional documentary inventory, not a municipal licence register.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://urbanismo.castillalamancha.es"
SOURCE = BASE + "/acuerdos-expedientes?title=Ont%C3%ADgola"
LIMITATIONS = [
    "Inventario autonómico parcial: acuerdos cuyo título contiene Ontígola; no todo el planeamiento municipal.",
    "Sin registro de licencias concedidas ni comprobación de vigencia o ejecución de las actuaciones.",
    "Fechas del inventario: acuerdo, no publicación ni aprobación definitiva.",
    "TAGUS 1 y TAGUS 2 abarcan también Ocaña; sin geometría ni coordenadas verificadas.",
]


def norm(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def official_url(href, page):
    url = urljoin(page, href).split("#")[0]
    if urlparse(url).scheme != "https" or urlparse(url).netloc != urlparse(BASE).netloc:
        raise ValueError("Unexpected non-official source URL")
    return url


def parse_page(html, page_url):
    """Return documentary notices, advertised total and next page; fail on drift."""
    soup = BeautifulSoup(html, "html.parser")
    view = soup.select_one(".view-buscador-expedientes")
    if view is None:
        raise ValueError("Missing agreement inventory")
    summary = view.select_one(".view-header")
    match = re.search(r"Mostrando\s+\d+\s*-\s*\d+\s+de\s+(\d+)", summary.get_text(" ", strip=True) if summary else "")
    if not match:
        raise ValueError("Missing result count; coverage cannot be verified")
    notices = []
    for article in view.select(".view-content article.node"):
        title_node = article.select_one("h3.article__title")
        date_node = article.select_one(".field--name-field-expediente-fecha")
        population = article.select_one(".field--name-field-poblacion")
        if not title_node or not date_node or not article.get("about"):
            raise ValueError("Incomplete agreement card")
        title = title_node.get_text(" ", strip=True)
        if not re.search(r"\bontigola\b", norm(title).replace("_", " ")):
            raise ValueError("Title filter did not restrict to Ontígola")
        if population and norm(population.get_text(" ", strip=True)) != "ontigola":
            raise ValueError("Unexpected municipality in filtered inventory")
        date = datetime.strptime(date_node.get_text(strip=True), "%d/%m/%Y").date().isoformat()
        docs = {}
        for anchor in article.select(".field--name-field-expediente-fichero a.file-download[href]"):
            url = official_url(anchor["href"], page_url)
            if not urlparse(url).path.startswith("/sites/default/files/expedientes/") or not urlparse(url).path.lower().endswith(".pdf"):
                raise ValueError("Unexpected agreement document URL")
            label = anchor.select_one(".file--title")
            docs[url] = {"titulo": label.get_text(" ", strip=True) if label else title, "url": url}
        if not docs:
            raise ValueError("Agreement without source PDF")
        notices.append({"titulo": title, "url": official_url(article["about"], page_url),
                        "fecha_acuerdo": date, "documentos": list(docs.values()), "inventory_url": page_url})
    if not notices:
        raise ValueError("No usable Ontígola agreements")
    next_links = view.select(".pager__item--next a[href], a[rel~=next][href]")
    next_urls = {official_url(a["href"], page_url) for a in next_links}
    if len(next_urls) > 1:
        raise ValueError("Ambiguous pagination")
    return notices, int(match.group(1)), next(iter(next_urls), None)


def group_notices(notices):
    rows = {}
    for notice in notices:
        title = notice["titulo"]
        n = norm(title)
        # An agreement/report is evidence about the project, not a licence grant.
        if re.search(r"\b(?:licitacion|contratacion|pliego|formulario|solicitud|modelo)\b", n):
            continue
        if not re.search(r"proyecto|calificacion (?:planta|subestacion)|\bpau\b|res\.pau|modificaci|\bmp1\b", n):
            continue
        key = notice["url"]
        if "albardiales iii" in n and re.search(r"\bmp1\b|modificacion puntual (?:numero|n[ºo.]*)\s*1\b", n):
            key = "mp1-plan-parcial-los-albardiales-iii"
        row = rows.setdefault(key, {
            "id": "ontigola-proy-" + hashlib.sha256(key.encode()).hexdigest()[:16],
            "municipio": "Ontígola", "codigo_ine": "45123", "provincia": "Toledo",
            "titulo": title, "tipo": "instrumento o proyecto urbanístico",
            "url": notice["url"], "source": "jccm", "origen": "inventario_acuerdos_urbanismo",
            "organismo_fuente": "Junta de Comunidades de Castilla-La Mancha",
            "inventory_url": SOURCE, "acuerdos": [], "documentos": [],
            "publication_ready": False, "geometry_status": "unavailable",
            "cobertura": "parcial; filtro por título en inventario autonómico",
        })
        if key == "mp1-plan-parcial-los-albardiales-iii" and "modificacion" in n:
            row["titulo"] = title
        row["acuerdos"].append(notice)
        for doc in notice["documentos"]:
            if doc not in row["documentos"]:
                row["documentos"].append(doc)
    if not rows:
        raise ValueError("No supported instruments or physical projects")
    for row in rows.values():
        dates = {a["fecha_acuerdo"] for a in row["acuerdos"]}
        if len(dates) == 1:
            row["fecha_acuerdo"] = next(iter(dates))
    return list(rows.values())


class OntigolaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        url = SOURCE
        visited, notices, seen_notices = set(), [], set()
        expected = None
        while url:
            parsed = urlparse(url)
            if parsed.path != "/acuerdos-expedientes" or parse_qs(parsed.query).get("title") != ["Ontígola"]:
                raise ValueError("Pagination lost municipality filter")
            if url in visited:
                raise ValueError("Pagination cycle")
            visited.add(url)
            response = requests.get(url, timeout=45, headers={"User-Agent": "Mozilla/5.0 (compatible; municipal-inventory/1.0)"})
            response.raise_for_status()
            if response.url != url:
                raise ValueError("Unexpected inventory redirect")
            capture = self.config.get("capture_dir")
            if capture:
                path = Path(capture)
                path.mkdir(parents=True, exist_ok=True)
                (path / f"live-inventory-{len(visited)}.html").write_text(response.text, encoding="utf-8")
            page_notices, total, url = parse_page(response.text, response.url)
            if expected is not None and total != expected:
                raise ValueError("Result count changed during extraction")
            expected = total
            for notice in page_notices:
                if notice["url"] in seen_notices:
                    raise ValueError("Duplicate notice across pages")
                seen_notices.add(notice["url"])
                notices.append(notice)
        if len(notices) != expected:
            raise ValueError("Incomplete pagination: notice count differs from advertised total")
        rows = group_notices(notices)
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "source_notices": len(notices),
                "excluded_notices": len(notices) - sum(len(row["acuerdos"]) for row in rows),
                "source_urls": sorted(visited), "limitations": LIMITATIONS, "publication_ready": False}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        tmp.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Reconcile the full current inventory, including removals; no date watermark.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified public register of granted licences"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
