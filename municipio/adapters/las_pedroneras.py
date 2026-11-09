"""Official JCCM PAU register: municipality-scoped, complete inventory traversal."""
from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://urbanismo.castillalamancha.es"
INVENTORY = BASE + "/registros/pau-cu"
LIMITATIONS = [
    "Cobertura parcial: solo PAU inscritos en el registro autonómico de Cuenca; no todos los planes ni obras municipales.",
    "La inscripción y la aprobación no acreditan ejecución, vigencia actual ni licencia concedida.",
    "Sin fecha de publicación ni fecha de acuerdo verificadas; aprobación tomada exclusivamente del campo de la ficha.",
    "Sin coordenadas; la ficha observada no ofrece documentos adjuntos ni geometría.",
]


def official_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != urlparse(BASE).netloc:
        raise ValueError("Unexpected source outside official JCCM host")
    return url


def parse_inventory(html, url=INVENTORY):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("main table")
    if table is None or not table.select("th.views-field-municipios-clm"):
        raise ValueError("PAU register table/municipality column missing")
    entries = {}
    for tr in table.select("tbody tr"):
        municipality = tr.select_one("td.views-field-municipios-clm")
        if municipality is None:
            raise ValueError("Unrecognised register row")
        if municipality.get_text(" ", strip=True) != "Pedroñeras, Las":
            continue
        anchor = tr.select_one("td.views-field-title a[href]")
        if anchor is None:
            raise ValueError("Municipal PAU lacks detail link")
        target = official_url(urljoin(url, anchor["href"]))
        if not urlparse(target).path.startswith("/registros/pau/"):
            raise ValueError("Unexpected PAU detail path")
        entries[target] = anchor.get_text(" ", strip=True)
    # Traverse every numbered/next/last Drupal pager link, deduplicated by URL.
    pages = set()
    for anchor in soup.select("main .pager a[href], main a[rel~=next]"):
        pages.add(official_url(urljoin(url, anchor["href"])))
    for target in pages:
        if urlparse(target).path != urlparse(INVENTORY).path:
            raise ValueError("Unexpected PAU pagination path")
    return entries, sorted(pages)


def parse_detail(html, url, inventory_title):
    official_url(url)
    soup = BeautifulSoup(html, "html.parser")
    article = soup.select_one("article.node--type-programa-actuacion-urbanizadora")
    if article is None:
        raise ValueError("PAU detail article missing")
    places = [li.get_text(" ", strip=True) for li in article.select(".field--name-municipios-clm li")]
    if places != ["CUENCA", "Pedroñeras, Las"]:
        raise ValueError("PAU detail municipality/province mismatch")
    title = article.select_one("h1")
    if title is None or title.get_text(" ", strip=True) != inventory_title:
        raise ValueError("PAU inventory/detail title mismatch")
    row = {
        "id": "las-pedroneras-pau-" + hashlib.sha256(url.encode()).hexdigest()[:16],
        "municipio": "Las Pedroñeras", "codigo_ine": "16154", "provincia": "Cuenca",
        "titulo": inventory_title, "tipo": "programa_actuacion_urbanizadora",
        "url": url, "inventory_url": INVENTORY,
        "source": "jccm", "origen": "registro_autonomico_pau_cuenca",
        "publication_ready": False, "geometry_status": "unavailable",
    }
    time = article.select_one(".field--name-field-fecha-aprobacion time[datetime]")
    if time is not None:
        row["fecha_aprob"] = date.fromisoformat(time["datetime"][:10]).isoformat()
        row["fecha_aprob_fuente"] = "Ficha JCCM: Fecha de aprobación"
    for source, dest in [("field-datos-inscripcion", "datos_inscripcion"),
                         ("field-agente-urbanizador", "agente_urbanizador"),
                         ("field-uso", "uso")]:
        field = article.select_one(f".field--name-{source} .field__item")
        if field is not None:
            row[dest] = field.get_text(" ", strip=True)
    # Attachments stay with their PAU; navigation/footer documents are excluded.
    documents = {}
    for anchor in article.select("a[href]"):
        target = urljoin(url, anchor["href"])
        if "/sites/default/files/" in urlparse(target).path:
            official_url(target)
            documents[target] = {"titulo": anchor.get_text(" ", strip=True), "url": target,
                                 "source_url": url}
    row["documentos"] = list(documents.values())
    return row


class LasPedronerasAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, session, url):
        official_url(url)
        response = session.get(url, timeout=40)
        response.raise_for_status()
        official_url(response.url)
        self.source_urls.append(url)
        capture_dir = self.config.get("capture_dir")
        if capture_dir:
            folder = Path(capture_dir)
            folder.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".html"
            (folder / name).write_text(response.text, encoding="utf-8")
        return response.text

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        self.source_urls = []
        pending, visited, entries = [INVENTORY], set(), {}
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-las-pedroneras/1.0 (public planning inventory)"
            while pending:
                url = pending.pop(0)
                if url in visited:
                    continue
                visited.add(url)
                found, pages = parse_inventory(self._fetch(session, url), url)
                for target, title in found.items():
                    if target in entries and entries[target] != title:
                        raise ValueError("Conflicting PAU titles across register pages")
                    entries[target] = title
                pending.extend(page for page in pages if page not in visited)
            if not entries:
                raise ValueError("No Las Pedroñeras PAU found; review live register")
            rows = [parse_detail(self._fetch(session, url), url, title)
                    for url, title in sorted(entries.items())]
        self._write(out_jsonl, rows)
        return {"count": len(rows), "written": len(rows), "inventory_pages": len(visited),
                "source_urls": self.source_urls, "limitations": LIMITATIONS,
                "coverage": "registro_autonomico_pau_cuenca", "publication_ready": False}

    def update_proyectos(self, out_jsonl, state_path):
        """Refresh the entire small register; no date cutoff or append duplicates."""
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
