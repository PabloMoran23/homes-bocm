from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WP_BASE = "https://elboalo-cerceda-mataelpino.org"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://sede.elboalo-cerceda-mataelpino.org/eAdmin"
TABLON_URL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/normativa-urbanistica/",
    f"{WP_BASE}/urbanismo/",
    f"{WP_BASE}/portal-de-transparencia/",
]

TABLON_SEARCH_TERMS = (
    "urbanismo",
    "licencia",
    "licencias",
    "edicto",
    "informacion publica",
    "planeamiento",
    "parcela",
    "subasta",
    "bando",
    "PGOU",
    "ordenanza",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|edicto.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urbanismo|urbanistic|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n puntual|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental)|normas subsidiarias|subasta.*parcela|"
    r"parcela(?:s)? municipal|ordenaci[oó]n|bando.*parcela|asfaltado|urbanizaci|"
    r"edicto|obras de renovaci|embellecimiento|licitaci[oó]n.*parcela)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(
    r'href="((?:https://elboalo-cerceda-mataelpino\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_TABLON_ROW = re.compile(
    r"<tr[^>]*>(.*?)</tr>",
    re.I | re.S,
)
RE_TABLON_LINK = re.compile(
    r'href="(\./Tablon\.do\?[^"]+|Tablon\.do\?[^"]+)"[^>]*>([^<]+)',
    re.I,
)
RE_TABLON_PDF = re.compile(
    r'href="([^"]+\.pdf[^"]*)"',
    re.I,
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"el-boalo-{prefix}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        m = re.search(r"BOCM[^0-9]*(\d{1,2})[^0-9]+de[^0-9]+(\d{4})", url, re.I)
        if m:
            return f"{m.group(2)}-01-01"
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", url)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _iso_date(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw[:10] if len(raw) >= 10 else None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pdf_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n or "pgou" in n:
        return "PGOU"
    if "plano" in n and "orden" in n:
        return "plano ordenación"
    if "ordenanza" in n and "licencia" in n:
        return "ordenanza licencias"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "convenio" in n:
        return "convenio"
    return "documento urbanismo"


class ElBoaloAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress (normativa urbanística + noticias) + tablón sede add4u."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.wp_api = str(self.config.get("wp_api_base") or WP_API).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.search_terms = list(self.config.get("tablon_search_terms") or TABLON_SEARCH_TERMS)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-boalo/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.elboalo" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_post(self, url: str, data: dict[str, str]) -> str:
        time.sleep(self.delay_s)
        body = urllib.parse.urlencode(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-el-boalo/1.0"),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str = WP_BASE) -> str:
        return urllib.parse.urljoin(base, href)

    def _extract_pdfs(self, html: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            url = self._abs_url(m.group(1))
            if url in seen:
                continue
            seen.add(url)
            name = unescape(urllib.parse.unquote(Path(url).name))
            name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ")
            out.append((name[:500], url))
        return out

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for title, pdf_url in self._extract_pdfs(html):
                blob = f"{title} {pdf_url}"
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", pdf_url),
                    "municipio": "El Boalo",
                    "titulo": title[:500],
                    "fecha": _fecha_from_url(pdf_url),
                    "tipo": _pdf_tipo(title),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": page_url,
                }
                if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                rows.append(rec)
        return rows

    def _paginate_wp_posts(self) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        page = 1
        while page <= 10:
            url = f"{self.wp_api}/posts?per_page=100&page={page}&status=publish"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            posts.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return posts

    @staticmethod
    def _post_title(post: dict[str, Any]) -> str:
        title = post.get("title") or {}
        return unescape(str(title.get("rendered") or "")).strip()

    def _post_to_proyecto(self, post: dict[str, Any]) -> dict[str, Any] | None:
        title = self._post_title(post)
        if not RE_PROYECTO.search(title):
            return None
        url = str(post.get("link") or "").strip()
        if not url:
            return None
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        pdfs = self._extract_pdfs(str((post.get("content") or {}).get("rendered") or ""))
        tipo = "urbanismo"
        if re.search(r"(?i)subasta|parcela", title):
            tipo = "subasta parcelas"
        elif re.search(r"(?i)bando", title):
            tipo = "bando municipal"
        elif re.search(r"(?i)plan de asfaltado|embellecimiento|urbanizaci", title):
            tipo = "plan municipal"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": "El Boalo",
            "titulo": title[:500],
            "fecha": _iso_date(str(post.get("date") or "")),
            "tipo": tipo,
            "url": url,
            "source": "ayuntamiento",
            "origen": "wp_posts",
        }
        if pdfs:
            rec["pdf_url"] = pdfs[0][1]
        return rec

    def _collect_wp_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for post in self._paginate_wp_posts():
            rec = self._post_to_proyecto(post)
            if rec:
                rows.append(rec)
        return rows

    def _parse_tablon_html(self, html: str, source: str) -> list[dict[str, Any]]:
        if "no existen anuncios" in html.lower() and "card-header" in html.lower():
            if html.lower().count("no existen anuncios") >= 3:
                pass
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_TABLON_LINK.finditer(html):
            path, title = m.group(1), unescape(m.group(2).strip())
            if not title or len(title) < 5:
                continue
            url = self._abs_url(path, self.sede_base + "/")
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": title[:500], "url": url, "source_page": source})

        for m in RE_TABLON_ROW.finditer(html):
            row_html = m.group(1)
            if "no existen anuncios" in row_html.lower():
                continue
            text = _strip_html(row_html)
            if len(text) < 15:
                continue
            if not RE_PROYECTO.search(text) and not RE_LICENCIA.search(text):
                continue
            pdfs = [self._abs_url(u, self.sede_base + "/") for u in RE_TABLON_PDF.findall(row_html)]
            link_m = re.search(r'href="(\./Tablon\.do\?[^"]+)"', row_html, re.I)
            url = self._abs_url(link_m.group(1), self.sede_base + "/") if link_m else source
            key = url + text[:80]
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "titulo": text[:500],
                    "url": url,
                    "source_page": source,
                    "pdf_url": pdfs[0] if pdfs else None,
                    "fecha": _parse_fecha_dmy(text),
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}

        def add(item: dict[str, Any]) -> None:
            key = item.get("url") or item.get("titulo", "")
            prev = by_key.get(key)
            if prev:
                if not prev.get("pdf_url") and item.get("pdf_url"):
                    prev["pdf_url"] = item["pdf_url"]
                if not prev.get("fecha") and item.get("fecha"):
                    prev["fecha"] = item["fecha"]
            else:
                by_key[key] = item

        try:
            html = self._fetch(self.tablon_url, use_sede_ssl=True)
            for item in self._parse_tablon_html(html, self.tablon_url):
                add(item)
        except urllib.error.URLError:
            pass

        for term in self.search_terms:
            try:
                html = self._fetch_post(self.tablon_url, {"referenciaBusqueda": term})
                for item in self._parse_tablon_html(html, f"{self.tablon_url}#q={term}"):
                    add(item)
            except urllib.error.URLError:
                continue

        return list(by_key.values())

    def _tablon_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title = item.get("titulo") or ""
        if not RE_LICENCIA.search(title):
            return None
        url = str(item.get("url") or self.tablon_url)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title = item.get("titulo") or ""
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        url = str(item.get("url") or self.tablon_url)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": "El Boalo",
            "titulo": title[:500],
            "fecha": item.get("fecha"),
            "tipo": "edicto" if re.search(r"(?i)edicto|bando", title) else "urbanismo",
            "url": url,
            "source": "ayuntamiento",
            "origen": "tablon_sede",
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        return rec

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        urbanismo_url = f"{WP_BASE}/urbanismo/"
        normativa_url = f"{WP_BASE}/normativa-urbanistica/"

        for page_url in (urbanismo_url, normativa_url):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            plain = _strip_html(html)
            for m in re.finditer(
                r"(?i)((?:declaraci[oó]n responsable|comunicaci[oó]n previa|"
                r"solicitud de licencia|licencia urban)[^\.]{0,120})",
                plain,
            ):
                title = m.group(1).strip()
                if len(title) < 12 or title in seen:
                    continue
                seen.add(title)
                rows.append(
                    {
                        "id": _stable_id("lic", f"{page_url}#{title}"),
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": page_url,
                        "source": "ayuntamiento",
                        "nota": "Trámite informativo; no concesión publicada",
                    }
                )

            for title, pdf_url in self._extract_pdfs(html):
                if RE_LICENCIA.search(title):
                    rows.append(
                        {
                            "id": _stable_id("lic", pdf_url),
                            "fecha_concesion": _fecha_from_url(pdf_url),
                            "tipo": "ordenanza licencias",
                            "distrito": None,
                            "lat": None,
                            "lon": None,
                            "titulo": title[:500],
                            "url": normativa_url,
                            "pdf_url": pdf_url,
                            "source": "ayuntamiento",
                            "nota": "Normativa reguladora; no concesión individual",
                        }
                    )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        tablon = self._collect_tablon()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in tablon:
            add(self._tablon_to_licencia(item))
        for rec in self._collect_licencia_tramites():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon_items": len(tablon)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for rec in self._collect_licencia_tramites():
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        added = len(rows) - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_seed_pdfs():
            add(rec)
        for rec in self._collect_wp_proyectos():
            add(rec)
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "seed_pdfs": sum(1 for r in rows if r.get("origen", "").startswith("http") and "pdf" in str(r.get("pdf_url", ""))),
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_posts"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
