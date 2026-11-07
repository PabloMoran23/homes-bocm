"""Bergara's municipal Urbanismo book: a partial documentary inventory."""
from __future__ import annotations

import json
import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = "https://www.bergara.eus/es/node/517"
MONTHS = dict(zip("enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), range(1, 13)))
LIMITATIONS = [
    "Partial coverage: special plans, detail studies, urbanisation and reparcelling projects in the Urbanismo book; not all municipal works or planning.",
    "The index mixes historical and recent documents; listing does not establish current legal validity or approval.",
    "Municipal publication dates are unavailable. Only unambiguous decree dates in HTML are extracted as agreement dates; PDF dates are not parsed.",
    "Attachments are retained as links, not downloaded or independently verified; source may include ancillary documents for other parcels.",
    "No granted licences or verified project geometries; no invented coordinates.",
]


def canonical(url, base=SOURCE):
    parts = urlsplit(urljoin(base, url))
    if parts.hostname in {"bergara.eus", "www.bergara.eus"}:
        return urlunsplit(("https", "www.bergara.eus", parts.path, parts.query, ""))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, parts.query, ""))


def check_pagination(soup):
    # Drupal book .page-next is a sibling chapter, NOT result pagination.
    if soup.select(".pager a[href], a[rel~=next], .pagination a[href]"):
        raise ValueError("Pagination detected: review crawler before accepting a partial inventory")


def agreement_date(text):
    matches = re.findall(
        r"mediante\s+(?:un\s+)?decreto\s+(?:del?|de alcaldía de)\s+"
        r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", text.lower()
    )
    dates = set()
    for day, month, year in matches:
        if month in MONTHS:
            dates.add(date(int(year), MONTHS[month], int(day)).isoformat())
    return next(iter(dates)) if len(dates) == 1 else None


class BergaraAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_inventory(html):
        soup = BeautifulSoup(html, "html.parser")
        check_pagination(soup)
        menu = soup.select_one("article #book-navigation-517 > ul.menu")
        if menu is None:
            raise ValueError("Urbanismo book inventory missing")
        entries = {}
        for a in menu.select(":scope > li > a[href]"):
            title = a.get_text(" ", strip=True)
            # Positive instrument vocabulary; exclude withdrawal notices, forms,
            # procurement, agreements and generic news even if they mention a plan.
            if not re.match(r"^(?:Estudio de detalle|Plan Especial|Proyecto de reparcelación|Tercera modificación del proyecto de reparcelación|A\s*44-2 Proyecto de Urbanización|Gune historikoa birgaitzeko plan berezia)", title, re.I):
                continue
            url = canonical(a["href"])
            if not re.fullmatch(r"https://www\.bergara\.eus/es/node/\d+", url):
                raise ValueError(f"Unexpected instrument URL: {url}")
            entries[url] = {"titulo": title, "url": url}
        if not entries:
            raise ValueError("No supported planning instruments in inventory")
        return list(entries.values())

    @staticmethod
    def parse_detail(html, url):
        soup = BeautifulSoup(html, "html.parser")
        check_pagination(soup)
        article = soup.select_one("article.node-book")
        if article is None:
            raise ValueError(f"Planning chapter missing: {url}")
        title = article.select_one('[property="dc:title"]')
        if title is None or not title.get("content"):
            raise ValueError(f"Planning chapter title missing: {url}")
        body = article.select_one(".field-name-body")
        text = body.get_text(" ", strip=True) if body else ""
        docs = {}
        for a in article.select(".field a[href]"):
            link = canonical(a["href"], url)
            p = urlsplit(link)
            municipal = p.hostname == "www.bergara.eus" and p.path.startswith("/sites/default/files/")
            gazette = p.hostname == "egoitza.gipuzkoa.eus" and p.path.startswith("/gao-bog/")
            if municipal or gazette:
                label = a.get_text(" ", strip=True) or p.path.rsplit("/", 1)[-1]
                relation = "enlace_documental_en_fuente"
                # This chapter itself attaches a D/E/F/G study alongside H.
                # Preserve the link without claiming it is the H instrument.
                if "parcela h" in title["content"].lower() and "parcelas_d-e-f_y_g" in p.path.lower():
                    relation = "adjunto_de_otras_parcelas_no_identificado_como_instrumento_h"
                doc = docs.setdefault(link, {"url": link, "titulo": label, "titulos": [], "source_urls": [url],
                                             "relacion": relation,
                                             "origen": "adjunto_municipal" if municipal else "boletin_oficial_gipuzkoa"})
                if label not in doc["titulos"]:
                    doc["titulos"].append(label)
        # Follow subordinate book chapters only, never page-next/previous links.
        children = []
        for a in article.select(".book-navigation > ul.menu > li > a[href]"):
            child = canonical(a["href"], url)
            if not re.fullmatch(r"https://www\.bergara\.eus/(?:es|eu)/node/\d+", child):
                raise ValueError(f"Unexpected child chapter: {child}")
            children.append(child)
        return {"url": url, "titulo": title["content"], "descripcion": text,
                "fecha_acuerdo": agreement_date(text), "fecha_publicacion": None,
                "documentos": list(docs.values()), "children": children}

    @staticmethod
    def group_key(entry):
        # The BOG notice linked by 19972 identifies the modified/adapted A-18
        # plan also documented by 20827. Retain both stages in one record.
        if re.match(r"^Plan Especial.*(?:Área|Area) A-18$", entry["titulo"], re.I):
            return "peou-a18"
        return "node-" + entry["url"].rsplit("/", 1)[-1]

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        cache = {}
        capture = self.config.get("capture_dir")
        with requests.Session() as session:
            session.headers["User-Agent"] = "municipio-bergara/1.0"

            def fetch(url):
                if url not in cache:
                    if cache:
                        time.sleep(0.2)
                    r = session.get(url, timeout=40)
                    r.raise_for_status()
                    if urlsplit(r.url).hostname != "www.bergara.eus":
                        raise ValueError("Unexpected source redirect")
                    if "html" not in r.headers.get("Content-Type", "").lower():
                        raise ValueError("Expected an HTML source chapter")
                    r.encoding = "utf-8"
                    cache[url] = r.text
                    if capture:
                        folder = Path(capture)
                        folder.mkdir(parents=True, exist_ok=True)
                        (folder / (url.rsplit("/", 1)[-1] + ".html")).write_text(r.text, encoding="utf-8")
                return cache[url]

            groups = {}
            for entry in self.parse_inventory(fetch(SOURCE)):
                key = self.group_key(entry)
                group = groups.setdefault(key, {"entry": entry, "pages": {}})
                pending = [entry["url"]]
                while pending:
                    url = pending.pop(0)
                    if url in group["pages"]:
                        continue
                    page = self.parse_detail(fetch(url), url)
                    group["pages"][url] = page
                    pending.extend(page["children"])

        rows = []
        for key, group in groups.items():
            docs = {}
            pages = list(group["pages"].values())
            for page in pages:
                for doc in page["documentos"]:
                    if doc["url"] not in docs:
                        docs[doc["url"]] = doc
                    else:
                        old = docs[doc["url"]]
                        old["source_urls"] = sorted(set(old["source_urls"] + doc["source_urls"]))
                        old["titulos"] = sorted(set(old["titulos"] + doc["titulos"]))
            if not docs:
                raise ValueError(f"Instrument has no documentary sources: {key}")
            entry = group["entry"]
            lower = entry["titulo"].lower()
            kind = "reparcelacion" if "reparcelación" in lower else "urbanizacion" if "urbanización" in lower else "planeamiento_urbanistico"
            dates = {p["fecha_acuerdo"] for p in pages if p["fecha_acuerdo"]}
            rows.append({"id": "bergara-proy-" + key, "municipio": "Bergara", "codigo_ine": "20074",
                         "provincia": "Gipuzkoa", "titulo": entry["titulo"], "tipo": kind,
                         "url": entry["url"], "source": "ayuntamiento", "origen": "inventario_urbanismo",
                         # Documentary identity is verified, not an administrative
                         # expediente number or an execution/approval event.
                         "source_entity_type": "documento",
                         "source_urls": [p["url"] for p in pages], "inventory_url": SOURCE,
                         "fecha": None, "fecha_publicacion": None,
                         "fecha_acuerdo": next(iter(dates)) if len(dates) == 1 else None,
                         "fuentes": [{k: v for k, v in p.items() if k not in {"children", "documentos"}} for p in pages],
                         "documentos": list(docs.values()), "geometry": None, "lat": None, "lon": None,
                         "geometry_status": "unavailable", "publication_ready": False})
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": list(cache), "limitations": LIMITATIONS}

    def update_proyectos(self, out_jsonl, state_path):
        # Complete documentary snapshot; not an incremental historical event log.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
