"""Documented urban-planning participation instruments in Huarte's public archive.

The WordPress search is an inventory, not evidence of approval. Only substantive
participation notices with municipal technical documents become instruments.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter


SOURCE = "https://huarte.es/wp-json/wp/v2/posts"
SEARCH = "plan especial"


def _text(html):
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def _norm(text):
    return " ".join(unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower().split())


def _official(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in {"huarte.es", "www.huarte.es"}


class HuarteAyuntamientoAdapter(AyuntamientoAdapter):
    @staticmethod
    def parse_posts(posts):
        grouped = {}
        for post in posts:
            title = _text(post["title"]["rendered"])
            normalized = _norm(title)
            prefix = "proceso de participacion"
            if not (normalized.startswith(prefix) and "plan especial actuacion urbana." in normalized):
                continue
            html = post["content"]["rendered"]
            description = _text(html)
            if "cuyo avance adjuntamos" not in description.lower():
                raise ValueError("Planning notice lost its substantive participation narrative")
            url = post["link"]
            if not _official(url):
                raise ValueError("Non-municipal notice URL")
            published = datetime.fromisoformat(post["date"]).date().isoformat()
            # Repeated notices for the same instrument (notably Zubiarte 16)
            # retain every publication and attachment under one stable identity.
            scope = title.split(".", 1)[1].strip()
            key = _norm(scope)
            soup = BeautifulSoup(html, "html.parser")
            docs = {}
            technical = False
            for anchor in soup.select("a[href]"):
                doc_url = urljoin(url, anchor["href"])
                parsed = urlparse(doc_url)
                if not (_official(doc_url) and parsed.path.startswith("/wp-content/uploads/")
                        and unquote(parsed.path).lower().endswith(".pdf")):
                    continue
                label = anchor.get_text(" ", strip=True)
                technical |= _norm(label) in {"documento", "resumen"}
                docs[doc_url] = {"titulo": label, "url": doc_url,
                                 "url_procedencia": url, "fecha_publicacion": published}
            if not technical:
                raise ValueError("Planning notice lacks a linked technical document")
            if key not in grouped:
                barrio = "barrio antig" in key
                grouped[key] = {
                    "id": "huarte-proy-" + hashlib.sha256(key.encode()).hexdigest()[:16],
                    "municipio": "Huarte / Uharte", "codigo_ine": "31122", "provincia": "Navarra",
                    "titulo": ("Modificación de determinaciones del Barrio Antiguo" if barrio
                               else "Plan Especial de Actuación Urbana — " + scope),
                    "tipo": "modificacion_planeamiento" if barrio else "plan_especial_actuacion_urbana",
                    "fase": "participación pública previa a aprobación inicial (según anuncio)",
                    "fecha": None, "fecha_publicacion": published,
                    "fecha_acuerdo": None, "fecha_aprob": None,
                    "url": url, "source": "ayuntamiento", "origen": "archivo_participacion_urbanistica",
                    "descripcion": description, "documentos": [], "publicaciones": [],
                    "lat": None, "lon": None, "geometry": None,
                    "geometry_status": "unavailable", "publication_ready": False,
                }
            row = grouped[key]
            if published < row["fecha_publicacion"]:
                row.update(fecha_publicacion=published, url=url, descripcion=description)
            row["publicaciones"].append({"id": post["id"], "url": url,
                                         "titulo": title, "fecha_publicacion": published})
            # Deduplicate identical documents while retaining all provenance.
            for doc in docs.values():
                existing = next((d for d in row["documentos"] if d["url"] == doc["url"]), None)
                provenance = {"url": url, "fecha_publicacion": published}
                if existing:
                    if provenance not in existing["procedencias"]:
                        existing["procedencias"].append(provenance)
                else:
                    doc["procedencias"] = [provenance]
                    row["documentos"].append(doc)
        if not grouped:
            raise ValueError("No documented planning instruments; review live inventory")
        return sorted(grouped.values(), key=lambda row: row["id"])

    def _get(self, url, params=None):
        response = requests.get(url, params=params, timeout=40,
                                headers={"User-Agent": "municipio-huarte/1.0"})
        response.raise_for_status()
        if not _official(response.url):
            raise ValueError("Source redirected outside the municipal host")
        capture = self.config.get("capture_dir")
        if capture:
            directory = Path(capture)
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(response.url.encode()).hexdigest()[:20]
            (directory / (name + ".body")).write_bytes(response.content)
            (directory / (name + ".json")).write_text(json.dumps({
                "url": response.url, "status": response.status_code,
                "headers": dict(response.headers),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        return response

    def _inventory(self):
        posts = {}
        page = 1
        expected = None
        while True:
            response = self._get(SOURCE, {"search": SEARCH, "per_page": 100,
                                         "page": page, "orderby": "id", "order": "asc"})
            totals = (int(response.headers["X-WP-Total"]), int(response.headers["X-WP-TotalPages"]))
            if expected is None:
                expected = totals
            if totals != expected or totals[1] > 1000:
                raise ValueError("Inventory changed during pagination or exceeds safety bound")
            batch = response.json()
            if not isinstance(batch, list) or (not batch and totals[0]):
                raise ValueError("Invalid or prematurely empty inventory page")
            for post in batch:
                if post["id"] in posts:
                    raise ValueError("Repeated post across inventory pages")
                posts[post["id"]] = post
            if page >= totals[1]:
                break
            page += 1
        if len(posts) != expected[0]:
            raise ValueError("Inventory count mismatch; refusing partial coverage")
        return list(posts.values())

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temporary.replace(path)
        return {"status": "ok", "rows": len(rows)}

    def backfill_proyectos(self, out_jsonl):
        rows = self.parse_posts(self._inventory())
        for url in sorted({doc["url"] for row in rows for doc in row["documentos"]}):
            response = self._get(url)
            if not response.content.lstrip().startswith(b"%PDF-"):
                raise ValueError("Linked planning document is not a PDF: " + url)
        return self._write(out_jsonl, rows)

    def update_proyectos(self, out_jsonl, state_path):
        # Complete refresh of this explicitly limited archive, not a date cutoff.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
