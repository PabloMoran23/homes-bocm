"""Municipal initial-planning notices in the official DOE search inventory.

Deliberately partial: municipal publisher, title contains planeamiento, initial
approval only, since 2026. Neither procurement nor licence applications qualify.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://doe.juntaex.es"
SEARCH = BASE + "/busquedas/disposiciones.php"
PUBLISHER = "AYUNTAMIENTO DE VILLAFRANCA DE LOS BARROS"
MONTHS = dict(zip("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), range(1, 13)))
DATE_RE = r"(\d{1,2}) de (\w+) de (\d{4})"


def spanish_date(text):
    match = re.search(DATE_RE, text.lower())
    if not match:
        return None
    return date(int(match[3]), MONTHS[match[2]], int(match[1])).isoformat()


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "doe.juntaex.es":
        raise ValueError("Unexpected DOE source URL")
    return url


def parse_inventory(html, url=SEARCH):
    """Require the advertised total; pagination is never silently discarded."""
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    match = re.search(r"Resultado de la búsqueda:\s*(\d+) disposici[oó]n(?:es)?", text, re.I)
    if not match:
        raise ValueError("DOE search result count missing")
    links = set()
    for anchor in soup.select('a[href]'):
        target = urljoin(url, anchor["href"])
        if urlparse(target).path == "/otrosFormatos/html.php":
            official_url(target)
            query = parse_qs(urlparse(target).query)
            if not all(query.get(key) for key in ("xml", "anio", "doe")):
                raise ValueError("Incomplete DOE document identity")
            links.add(target)
    # The current scoped inventory fits on one page. If DOE introduces a second
    # page or omits HTML versions, stop before writing an incomplete snapshot.
    if len(links) != int(match[1]):
        raise ValueError("DOE pagination or missing formats: result count differs from discovered documents")
    return sorted(links)


def parse_notice(html, url):
    official_url(url)
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one(".Contenido_principal")
    if main is None:
        raise ValueError("DOE notice content missing")
    heading = main.select_one(".tablabordecolor")
    body = main.select_one(".xml")
    metadata = main.select_one(".tablaborde")
    if heading is None or body is None or metadata is None:
        raise ValueError("DOE notice structure changed")
    fields = {}
    for label in metadata.select("span.negrita"):
        fields[label.get_text(" ", strip=True).rstrip(":")] = str(label.next_sibling or "").strip()
    if fields.get("Organismo") != PUBLISHER:
        raise ValueError("Notice is not issued by the exact municipality")
    headline = heading.get_text(" ", strip=True)
    if not re.search(r"sobre aprobación inicial de la modificación puntual .*planeamiento", headline, re.I):
        raise ValueError("Outside initial-planning notice coverage")
    paragraphs = [p.get_text(" ", strip=True) for p in body.select(".Txt")]
    narrative = " ".join(paragraphs)
    instrument = next((match for paragraph in paragraphs
                       if "según texto redactado" in paragraph
                       if (match := re.search(r"(modificación puntual (?:de las |del ).*?), según texto redactado", paragraph, re.I))), None)
    dossier = re.search(r"\bExpte\.\s*(\d{4}/\d+/S\d+)\b", narrative)
    if not instrument or not dossier:
        raise ValueError("Named planning instrument or municipal expediente missing")
    agreement = re.search(r"sesión celebrada con fecha\s+" + DATE_RE, narrative, re.I)
    resolution = re.search(r"Resolución de la Alcaldía[^,]+, de fecha\s+" + DATE_RE, narrative, re.I)
    formats = {"html": url}
    for anchor in metadata.select("a[href]"):
        label = anchor.get_text(" ", strip=True).lower()
        if label in ("pdf", "xml"):
            formats[label] = official_url(urljoin(url, anchor["href"]))
    if "pdf" not in formats:
        raise ValueError("Authentic DOE PDF link missing")
    publication = spanish_date(fields.get("Fecha Publicación", ""))
    if publication is None:
        raise ValueError("Explicit publication date missing")
    return {
        "expediente": dossier[1], "titulo": instrument[1],
        "fase": "aprobación inicial", "fecha_publicacion": publication,
        "fecha_acuerdo": spanish_date(agreement[0]) if agreement else None,
        "fecha_resolucion": spanish_date(resolution[0]) if resolution else None,
        "fecha_anuncio": spanish_date(headline),
        "fecha_aprob": None, "descripcion": "\n".join(paragraphs),
        "url": url, "formatos": formats, "titulo_anuncio": headline,
        "organismo": fields["Organismo"],
    }


def group_notices(notices):
    """One instrument per actual municipal expediente, retaining every notice."""
    grouped = {}
    for notice in notices:
        grouped.setdefault(notice["expediente"], {})[notice["url"]] = notice
    rows = []
    for dossier, documents in sorted(grouped.items()):
        ordered = sorted(documents.values(), key=lambda n: (n["fecha_publicacion"], n["url"]))
        latest = ordered[-1]
        row = {key: latest[key] for key in ("titulo", "fase", "fecha_publicacion", "fecha_acuerdo", "fecha_resolucion", "fecha_anuncio", "fecha_aprob", "descripcion", "url")}
        row.update({
            "id": "villafranca-de-los-barros-plan-" + dossier.replace("/", "-"),
            "expediente": dossier, "municipio": "Villafranca de los Barros",
            "codigo_ine": "06149", "provincia": "Badajoz",
            "tipo": "modificación de planeamiento", "source": "ayuntamiento",
            "origen": "anuncio_municipal_doe", "inventory_url": SEARCH,
            "url_documento": latest["formatos"]["pdf"], "documentos": ordered,
            "fecha": None, "lat": None, "lon": None, "geometry": None,
            "geometry_status": "unavailable", "publication_ready": False,
        })
        rows.append(row)
    return rows


class VillafrancaDeLosBarrosAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug="villafranca-de-los-barros", config=None, base_url=""):
        super().__init__(slug, config, base_url or BASE)

    def _capture(self, response):
        official_url(response.url)
        response.raise_for_status()
        if self.config.get("capture_dir"):
            directory = Path(self.config["capture_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256((response.request.method + response.url + str(response.request.body or "")).encode()).hexdigest()[:20]
            (directory / (name + ".html")).write_bytes(response.content)
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        start = date.fromisoformat(self.config.get("start_date", "2026-01-01"))
        end = date.fromisoformat(self.config.get("end_date", date.today().isoformat()))
        if start > end:
            raise ValueError("Invalid coverage dates")
        query = {
            "fecha1": start.isoformat(), "fecha2": end.isoformat(),
            "orgabus": "VILLAFRANCA DE LOS BARROS", "rango": "00",
            "descriptor": "00", "yuo": "0", "textobus": "planeamiento",
            "buscardesc": "nodesc", "tipo": " ",
        }
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-villafranca-de-los-barros/1.0"
            response = session.post(SEARCH, data=query, timeout=40)
            urls = parse_inventory(self._capture(response), response.url)
            notices = [parse_notice(self._capture(session.get(url, timeout=40)), url) for url in urls]
        rows = group_notices(notices)
        if not rows:
            raise ValueError("No usable municipal planning instruments found")
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return {"status": "ok", "count": len(rows), "written": len(rows),
                "source_urls": [SEARCH, *urls], "search_parameters": query,
                "coverage": "municipal initial-planning notices with planeamiento in title",
                "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full refresh of the explicit coverage window; no advancing cursor can
        # lose late-indexed or revised notices. State is intentionally untouched.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"count": 0, "disabled": True, "reason": "No verified granted-licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
