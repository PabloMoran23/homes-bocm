"""Urduliz's development-plan inventory and PGOU document tree.

Document labels are provenance, not evidence of approval or publication dates.
Each crawl is a full snapshot of these two branches, not a municipal works census.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from municipio.adapters.portal import AyuntamientoAdapter

BASE = "https://www.urduliz.eus"
PREFIX = "/es-ES/Ayuntamiento/Urbanismo/"
ROOT = BASE + PREFIX + "Paginas/default.aspx"
DEVELOPMENT = "planeamiento-desarrollo.aspx"
PGOU = "PGOU.aspx"


def canonical(url):
    """Page 1 aliases the unparameterized page; preserve other page numbers."""
    p = urlsplit(url)
    query = parse_qs(p.query)
    if query and (set(query) != {"page"} or len(query["page"]) != 1
                  or not re.fullmatch(r"[1-9]\d*", query["page"][0])):
        raise ValueError(f"Unreviewed pagination/query: {url}")
    q = urlencode({"page": query["page"][0]}) if query.get("page", ["1"])[0] != "1" else ""
    if p.scheme != "https" or p.netloc != "www.urduliz.eus" or not p.path.startswith(PREFIX):
        raise ValueError(f"Unexpected municipal source: {url}")
    return urlunsplit((p.scheme, p.netloc, p.path, q, ""))


def parse_page(html, url):
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one("#main-content #ProcedureContent")
    if content is None:
        raise ValueError(f"Missing municipal content: {url}")
    links, documents, pages, totals = {}, {}, set(), {}
    for a in content.select("a[href]"):
        href = a["href"].strip()
        if href.startswith(("#", "javascript:")):
            continue
        target = urljoin(url, href)
        p = urlsplit(target)
        title = a.get_text(" ", strip=True)
        if p.path.lower().endswith(".pdf"):
            target = canonical(target)
            if not title:
                raise ValueError("Unnamed planning document")
            documents[target] = {"titulo": title, "url": target, "source_url": url}
        elif p.query or title.lower() in {"siguiente", "next", ">", "»"}:
            target = canonical(target)
            if p.path != urlsplit(url).path or not p.query:
                raise ValueError("Unrecognized next-page link")
            pages.add(target)
        elif p.path.startswith(PREFIX + "Paginas/") and p.path.lower().endswith(".aspx"):
            target = canonical(target)
            if not title:
                img = a.select_one("img[alt]")
                title = img["alt"] if img else ""
            links[target] = title
    # Each SharePoint webpart advertises its own total, not the page's total.
    for block in content.select(".ms-WPBody"):
        match = re.search(r"Resultados\s+\d+\s*-\s*\d+\s+de\s+(\d+)", block.get_text(" ", strip=True))
        if match:
            members = {canonical(urljoin(url, a["href"])) for a in block.select('a[href]')
                       if urlsplit(a["href"]).path.lower().endswith(".pdf")}
            if not members:
                raise ValueError("Advertised document inventory has no documents")
            heading = block.parent.select_one(".ms-WPTitle")
            if heading is None:
                raise ValueError("Unidentified paginated document inventory")
            key = heading.get_text(" ", strip=True)
            totals[key] = (int(match[1]), members)
    return {"links": links, "documents": documents, "pages": pages, "totals": totals}


class UrdulizAyuntamientoAdapter(AyuntamientoAdapter):
    def _fetch(self, url):
        time.sleep(0.2)
        response = requests.get(url, timeout=40, headers={
            "User-Agent": "municipio-urduliz/1.0 (public planning inventory)"})
        response.raise_for_status()
        if canonical(response.url) != canonical(url):
            raise ValueError(f"Unexpected redirect: {response.url}")
        response.encoding = "utf-8"
        if self.config.get("capture_dir"):
            directory = Path(self.config["capture_dir"])
            directory.mkdir(parents=True, exist_ok=True)
            key = hashlib.sha256(url.encode()).hexdigest()[:16]
            (directory / f"{key}.html").write_text(response.text, encoding="utf-8")
            (directory / f"{key}.url").write_text(url, encoding="utf-8")
        return response.text

    def _inventory(self, start):
        pending, seen, docs, links, counts = [canonical(start)], set(), {}, {}, {}
        while pending:
            url = pending.pop(0)
            if url in seen:
                continue
            if len(seen) >= 100:
                raise ValueError("Pagination exceeds safety bound; no snapshot written")
            seen.add(url)
            parsed = parse_page(self._fetch(url), url)
            for target, doc in parsed["documents"].items():
                docs.setdefault(target, doc)
            links.update(parsed["links"])
            pending.extend(sorted(parsed["pages"] - seen))
            for name, (total, members) in parsed["totals"].items():
                prior_total, prior_members = counts.setdefault(name, (total, set()))
                if prior_total != total:
                    raise ValueError("Document inventory changed during pagination")
                prior_members.update(members)
        for name, (total, members) in counts.items():
            if len(members) != total:
                raise ValueError(f"Incomplete {name}: {len(members)} of {total}")
        return links, docs, seen

    @staticmethod
    def _branch(links, filename):
        matches = [url for url in links if urlsplit(url).path.rsplit("/", 1)[-1] == filename]
        if len(matches) != 1:
            raise ValueError(f"Missing/ambiguous inventory branch: {filename}")
        return matches[0]

    @staticmethod
    def _record(url, title, kind, docs, sources):
        if not docs:
            raise ValueError(f"Instrument has no documents: {url}")
        return {
            "id": "urduliz-plan-" + hashlib.sha256(url.encode()).hexdigest()[:16],
            "municipio": "Urduliz", "codigo_ine": "48089", "provincia": "Bizkaia",
            "titulo": title, "tipo": kind, "url": url,
            "source": "ayuntamiento", "origen": "inventario_planeamiento_municipal",
            "fecha_publicacion": None, "fecha_acuerdo": None, "fecha_aprob": None,
            "fase": None, "documentos": [docs[k] for k in sorted(docs)],
            "source_urls": sorted(sources), "geometry_status": "unavailable",
            "geometry": None, "lat": None, "lon": None, "publication_ready": False,
        }

    @staticmethod
    def _write(path, rows):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(path.suffix + ".tmp")
        temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        temp.replace(path)

    def backfill_proyectos(self, out_jsonl):
        root_links, _, root_sources = self._inventory(ROOT)
        development = self._branch(root_links, DEVELOPMENT)
        pgou = self._branch(root_links, PGOU)
        links, _, sources = self._inventory(development)
        rows = []
        for url, title in sorted(links.items()):
            if urlsplit(url).path.rsplit("/", 1)[-1] in {DEVELOPMENT, "default.aspx"}:
                continue
            if not re.match(r"^(Plan (?:Especial|Parcial)|Estudio de Detalle|Proyecto de|Modificaci[oó]n)\b", title, re.I):
                raise ValueError(f"Unreviewed development-plan entry: {title}")
            child_links, docs, detail_sources = self._inventory(url)
            if any(u not in {ROOT, development, url} for u in child_links):
                raise ValueError("New nested development inventory requires review")
            rows.append(self._record(url, title, "planeamiento_desarrollo", docs, sources | detail_sources))
        if not rows:
            raise ValueError("Empty development inventory requires review")
        # All technical phases and participation documents belong to ONE PGOU.
        pending, visited, all_docs, pgou_sources = [pgou], set(), {}, set()
        while pending:
            url = pending.pop(0)
            if url in visited:
                continue
            if len(visited) >= 100:
                raise ValueError("PGOU tree exceeds bound; review required")
            visited.add(url)
            child_links, docs, seen = self._inventory(url)
            all_docs.update(docs)
            pgou_sources.update(seen)
            # These links come from the content zone, excluding navigation.
            # Follow new phase pages too, regardless of their filename.
            pending.extend(u for u in child_links if u not in {ROOT, development} and u not in visited)
        rows.append(self._record(pgou, "Plan General de Ordenación Urbana de Urduliz (PGOU)",
                                 "plan_general_ordenacion_urbana", all_docs, pgou_sources))
        self._write(out_jsonl, rows)
        return {"status": "ok", "rows": len(rows), "source_urls": sorted(
            root_sources | {u for r in rows for u in r["source_urls"]}),
            "coverage": "development plans and PGOU documents; partial municipal coverage"}

    def update_proyectos(self, out_jsonl, state_path):
        return self.backfill_proyectos(out_jsonl)

    def backfill_licencias(self, out_jsonl):
        self._write(out_jsonl, [])
        return {"status": "disabled", "rows": 0, "reason": "No verified granted-licence register"}

    def update_licencias(self, out_jsonl, state_path):
        return self.backfill_licencias(out_jsonl)
