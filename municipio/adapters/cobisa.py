"""Partial inventory of completed physical works reported by Cobisa's website.

The REST publication date is never an agreement or construction date. Selection
requires both a physical intervention in the title and an explicit municipal
execution statement in the body; procurement and procedure notices are excluded.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://cobisa.es/wp-json/wp/v2/posts"


def normalize(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if unicodedata.category(c) != "Mn")


def official_url(url):
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in {"cobisa.es", "www.cobisa.es"}


def parse_post(post):
    """Return a source-backed work, or None for unsupported announcements."""
    if post.get("status") != "publish" or post.get("type") != "post":
        return None
    title = BeautifulSoup(post["title"]["rendered"], "html.parser").get_text(" ", strip=True)
    soup = BeautifulSoup(post["content"]["rendered"], "html.parser")
    body = soup.get_text(" ", strip=True)
    nt, nb = normalize(title), normalize(body)
    if re.search(r"\b(licitacion|contratacion|pliego|licencia|solicitud|teatral|teatro)\b", nt):
        return None
    action = r"\b(amplio|ampliacion|reformo|reforma|rehabilito|rehabilitacion|renovo|renovacion|pavimento|pavimentacion)\b"
    asset = r"\b(gradas|graderio|polideportivo|pabellon|calle|acera|parque|alumbrado|saneamiento)\b"
    execution = r"\bel ayuntamiento de cobisa (?:llevo a cabo|ha realizado|ha ejecutado|ha finalizado)\b"
    if not (re.search(action, nt) and re.search(asset, nt)
            and re.search(execution, nb) and re.search(action, nb) and re.search(asset, nb)):
        return None
    url = post["link"]
    if not official_url(url):
        raise ValueError("Work permalink is outside the official website")
    if type(post.get("id")) is not int or post["id"] <= 0:
        raise ValueError("Invalid WordPress post ID")
    published = datetime.fromisoformat(post["date"]).date().isoformat()
    documents = {url: {"titulo": title, "url": url, "tipo": "noticia municipal"}}
    for a in soup.select("a[href]"):
        target = urljoin(url, a["href"])
        if official_url(target) and urlparse(target).path.lower().endswith(".pdf"):
            documents[target] = {"titulo": a.get_text(" ", strip=True) or "Documento adjunto",
                                 "url": target, "tipo": "adjunto de la noticia"}
    return {
        "id": f"cobisa-obra-wp-{post['id']}", "municipio": "Cobisa",
        "codigo_ine": "45052", "provincia": "Toledo", "titulo": title,
        "tipo": "obra_publica", "descripcion": body,
        "fecha_publicacion": published, "url": url,
        "source": "ayuntamiento", "origen": "noticia_municipal_obra_realizada",
        "inventory_url": SOURCE,
        "source_api_url": f"{SOURCE}/{post['id']}",
        "documentos": list(documents.values()),
        "publication_ready": False, "geometry_status": "unavailable",
        "coverage": "partial_municipal_reports_of_completed_physical_works",
    }


class CobisaAyuntamientoAdapter(AyuntamientoAdapter):
    def backfill_proyectos(self, out_jsonl: Path):
        # No page limit: traverse the advertised inventory, fail on inconsistent
        # totals/duplicate IDs instead of silently accepting a partial snapshot.
        rows, seen = {}, set()
        expected_pages = expected_total = None
        page = 1
        with requests.Session() as session:
            session.headers.update({"User-Agent": "municipio-cobisa-inventory/1.0"})
            while True:
                response = session.get(SOURCE, params={"per_page": 100, "page": page,
                    "orderby": "id", "order": "asc"}, timeout=40)
                response.raise_for_status()
                if not official_url(response.url):
                    raise ValueError("Unexpected inventory redirect")
                pages = int(response.headers["X-WP-TotalPages"])
                total = int(response.headers["X-WP-Total"])
                if expected_pages is None:
                    expected_pages, expected_total = pages, total
                if (pages, total) != (expected_pages, expected_total):
                    raise ValueError("Inventory changed during pagination; retry")
                posts = response.json()
                if not isinstance(posts, list) or not posts or pages < page or total < 1:
                    raise ValueError("Empty or invalid municipal inventory")
                for post in posts:
                    if post["id"] in seen:
                        raise ValueError("Duplicate post during pagination; retry")
                    seen.add(post["id"])
                    row = parse_post(post)
                    if row:
                        if row["url"] in rows:
                            raise ValueError("Duplicate work permalink")
                        rows[row["url"]] = row
                if page == pages:
                    break
                page += 1
        if len(seen) != expected_total:
            raise ValueError("Incomplete inventory traversal")
        if not rows:
            raise ValueError("No supported physical works in the current inventory")
        self._write(out_jsonl, rows.values())
        return {"count": len(rows), "written": len(rows), "inventory_posts": len(seen),
                "inventory_pages": page, "coverage": "partial_municipal_works_news"}

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                             encoding="utf-8")
        temporary.replace(path)

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        self._write(out_jsonl, [])
        return {"count": 0, "disabled": True, "reason": "No verified granted licence register"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
