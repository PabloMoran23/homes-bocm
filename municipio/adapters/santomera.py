"""Santomera's current municipal planning inventory (not a licence register)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

SOURCE = "https://santomera.es/planeamiento/"
MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()


def explicit_date(text):
    match = re.search(r"(\d{1,2}) de (\w+) de (\d{4})", text.lower())
    if not match or match[2] not in MONTHS:
        return None
    return date(int(match[3]), MONTHS.index(match[2]) + 1, int(match[1])).isoformat()


def content(html):
    soup = BeautifulSoup(html, "html.parser")
    main = soup.select_one("main")
    if main is None:
        raise ValueError("Missing municipal main content")
    # This is a complete static inventory. Fail visibly if pagination appears.
    if soup.select('a[rel~="next"], .pagination, .nav-links, .page-links, a.page-numbers'):
        raise ValueError("Pagination detected; inventory coverage must be revalidated")
    return main


def official_url(href, source):
    target = urljoin(source, href)
    parsed = urlparse(target)
    if parsed.scheme != "https" or parsed.hostname != "santomera.es":
        raise ValueError("Unexpected planning document host: " + target)
    return target


def document(anchor, source):
    title = anchor.get_text(" ", strip=True)
    target = official_url(anchor["href"], source)
    item = {"titulo": title, "url": target, "source_url": source}
    # Only explicit human-readable dates, never CMS upload paths or filenames.
    value = explicit_date(title)
    if value:
        if "BORM" in title:
            item["fecha_publicacion"] = value
        elif "Certificado" in title and ("Pleno" in title or "Junta de Gobierno" in title):
            item["fecha_acuerdo"] = value
    return item


def parse_inventory(html, source=SOURCE):
    main = content(html)
    rows = []
    current = None
    seen = set()
    for node in main.find_all(["h2", "p", "a"]):
        if node.name == "h2":
            title = node.get_text(" ", strip=True)
            current = None
            if not re.match(r"^Plan (General|Parcial)\b", title):
                continue
            if title in seen:
                raise ValueError("Duplicate instrument heading")
            seen.add(title)
            current = {
                "id": "santomera-plan-" + hashlib.sha256(title.encode()).hexdigest()[:16],
                "municipio": "Santomera", "codigo_ine": "30901", "provincia": "Murcia",
                "titulo": title, "tipo": "instrumento de planeamiento urbanístico",
                "url": source, "inventory_url": source, "source": "ayuntamiento",
                "origen": "inventario_planeamiento", "documentos": [], "detail_urls": [],
                "descripcion": "", "publication_ready": False, "geometry_status": "unavailable",
            }
            rows.append(current)
        elif current is not None and node.name == "p":
            text = node.get_text(" ", strip=True)
            if text:
                current["descripcion"] += ("\n" if current["descripcion"] else "") + text
            if "se aprobó de forma definitiva el" in text:
                current["fecha_aprob"] = explicit_date(text.split("se aprobó de forma definitiva el", 1)[1])
        elif current is not None and node.name == "a" and node.get("href"):
            item = document(node, source)
            path = urlparse(item["url"]).path
            if path.lower().endswith(".pdf"):
                if item not in current["documentos"]:
                    current["documentos"].append(item)
            elif path.startswith("/planeamiento/") and item["url"] not in current["detail_urls"]:
                current["detail_urls"].append(item["url"])
    if not rows or any(not r["documentos"] and not r["detail_urls"] for r in rows):
        raise ValueError("No usable instruments or incomplete inventory markup")
    return rows


def parse_detail(html, source):
    main = content(html)
    docs = []
    for anchor in main.select("a[href]"):
        if urlparse(urljoin(source, anchor["href"])).path.lower().endswith(".pdf"):
            item = document(anchor, source)
            if item not in docs:
                docs.append(item)
    if not docs:
        raise ValueError("Planning detail has no documents: " + source)
    return docs


class SantomeraAyuntamientoAdapter(AyuntamientoAdapter):
    def __init__(self, slug="santomera", config=None, base_url=SOURCE):
        super().__init__(slug, config, base_url)

    def _fetch(self, url):
        official_url(url, SOURCE)
        response = requests.get(
            url, timeout=45, headers={"User-Agent": "municipio-santomera/1.0"},
            verify=self.config.get("verify_tls", True),
        )
        response.raise_for_status()
        official_url(response.url, SOURCE)
        if "text/html" not in response.headers.get("Content-Type", ""):
            raise ValueError("Expected municipal HTML inventory")
        if self.config.get("capture_dir"):
            directory = Path(self.config["capture_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            name = hashlib.sha256(url.encode()).hexdigest()[:16] + ".html"
            (directory / name).write_text(response.text, encoding="utf-8")
        return response.text

    def backfill_proyectos(self, out_jsonl: Path):
        rows = parse_inventory(self._fetch(SOURCE))
        sources = [SOURCE]
        for row in rows:
            for detail in row["detail_urls"]:
                row["documentos"].extend(parse_detail(self._fetch(detail), detail))
                sources.append(detail)
            # Retain the municipal attribution but flag contradictory filenames.
            row["source_warnings"] = []
            if "MZ-16" in row["titulo"] and any("CB-01" in d["url"] for d in row["documentos"]):
                row["source_warnings"].append("Municipal MZ-16 page links CB-01 documents; attribution not independently verified")
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        return {"count": len(rows), "source_urls": list(dict.fromkeys(sources)),
                "coverage": "current municipal planning inventory; partial municipal coverage",
                "tls_verified": self.config.get("verify_tls", True), "publication_ready": False}

    def update_proyectos(self, out_jsonl: Path, state_path: Path):
        # Full current snapshot; no false incremental completeness claim.
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl: Path):
        output = Path(out_jsonl)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("", encoding="utf-8")
        return {"count": 0, "disabled": True, "reason": "No verified granted-licence register; forms excluded"}

    def update_licencias(self, out_jsonl: Path, state_path: Path):
        return self.backfill_licencias(out_jsonl)
