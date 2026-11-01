from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.figueres.cat"
MUNICIPIO = "Figueres"
ID_PREFIX = "figueres"

PLANEJAMENT_RSS = f"{WEB_BASE}/temes/urbanisme/planejament-urbanistic/rss.xml"
PROJECTES_RSS = f"{WEB_BASE}/temes/urbanisme/projectes/rss.xml"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/temes/urbanisme/planejament-urbanistic",
    f"{WEB_BASE}/temes/urbanisme/projectes",
    f"{WEB_BASE}/temes/urbanisme/projectes/projectes-en-exposicio-publica",
    f"{WEB_BASE}/temes/urbanisme/poum",
]

LICENCIA_PAGES: list[str] = [
    f"{WEB_BASE}/tramits/tramits-i-gestions/llicencies-dobres",
    f"{WEB_BASE}/tramits/tramits-i-gestions/llicencies-urbanistiques",
    f"{WEB_BASE}/tramits/tramits-i-gestions/llicencies-destabliments",
    f"{WEB_BASE}/tramits",
    (
        "https://tramit.figueres.org/OAC/SegExpStandalone.jsp?"
        "idioma=ca&useValid=true&ddlo=true&_UNITREE=CARP&"
    ),
]

RE_FIGUERES_HOST = re.compile(r"^https?://(?:www\.)?figueres\.cat/", re.I)
RE_SKIP_SLUG = re.compile(
    r"(?i)^(planejament-urbanistic|projectes|poum|projectes-en-exposicio-publica|"
    r"rss\.xml|atom\.xml|RSS)$"
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó]n responsable|declaraci[oó] responsable|obra[s]?|"
    r"consulta.*expedient|segellat|tramit)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|poum|pla especial|modificaci[oó]|projecte|proyecto|"
    r"informaci[oó] p[uú]blica|exposici[oó]|gsur|ordenan[cç]a|suspensi[oó] de llic|"
    r"reurban|equipament|habitatge|accessibilitat)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_iso_date(text: str) -> str | None:
    m = RE_ISO_DATE.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    for parser in (_parse_iso_date, _parse_fecha_dmy):
        d = parser(text)
        if d:
            return d
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return _parse_iso_date(text.replace("/", "-"))


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "pla especial" in n or "plan especial" in n:
        return "plan especial"
    if "modificaci" in n and "poum" in n:
        return "modificación POUM"
    if "poum" in n or "pla general" in n or "planejament" in n:
        return "planeamiento"
    if "suspensi" in n and "llic" in n:
        return "suspensión de licencias"
    if "projecte d'urban" in n or "urbanitz" in n:
        return "proyecto de urbanización"
    if "informaci" in n or "exposici" in n or "consulta" in n:
        return "información pública"
    if re.search(r"\bgsur\d+", n):
        return "expediente urbanístico"
    if "ordenan" in n:
        return "ordenanza urbanística"
    if "habitatge" in n and "tur" in n:
        return "regulación uso turístico"
    return "urbanismo"


class FigueresAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone figueres.cat (planejament + projectes RSS) + tràmits licències + consulta expedients."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.fetch_timeout_s = int(self.config.get("fetch_timeout_s", 90))

    def _fetch(self, url: str, *, timeout: int | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-figueres/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout or self.fetch_timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{WEB_BASE}/", unescape(href))

    def _is_project_url(self, url: str) -> bool:
        clean = urllib.parse.unquote(url.split("#")[0].split("?")[0]).rstrip("/")
        if not RE_FIGUERES_HOST.match(clean):
            return False
        if "/temes/urbanisme/planejament-urbanistic/" not in clean and (
            "/temes/urbanisme/projectes/" not in clean
        ):
            return False
        slug = clean.split("/")[-1]
        if not slug or RE_SKIP_SLUG.match(slug) or slug.endswith(".pdf"):
            return False
        if slug.endswith(".view") and ".pdf" in clean.lower():
            return False
        return True

    def _collect_crawl_urls(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for href, _ in RE_LINK.findall(html):
                if href.startswith(("mailto:", "javascript:", "#")):
                    continue
                u = self._abs_url(href, seed).split("#")[0].rstrip("/")
                if not self._is_project_url(u) or u in seen:
                    continue
                seen.add(u)
                out.append(u)
        return sorted(out)

    def _collect_rss(self, feed_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(feed_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        channel = root.find("channel")
        if channel is None:
            channel = root
        rows: list[dict[str, Any]] = []
        for item in channel.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or item.findtext("guid") or "").strip()
            date_raw = item.findtext("pubDate") or item.findtext("date") or ""
            if not title or not link:
                continue
            if not RE_FIGUERES_HOST.match(link):
                link = self._abs_url(link, WEB_BASE)
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link.split("#")[0].rstrip("/"),
                    "fecha": _parse_rss_date(date_raw),
                    "origen": origen,
                }
            )
        return rows

    def _parse_project_page(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return None
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        titulo = _strip_html(h1.group(1)) if h1 else ""
        if not titulo:
            titulo = url.rstrip("/").split("/")[-1].replace("-", " ").strip().title()
        meta = re.search(r'name="DC\.date\.modified" content="([^"]+)"', html)
        fecha = _parse_iso_date(meta.group(1)[:10]) if meta else None
        if not fecha:
            fecha = _fecha_from_blob(titulo, url)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha or "1970-01-01",
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
        }
        if "/planejament-urbanistic/" in url:
            rec["origen"] = "plone_planejament"
        elif "/projectes/" in url:
            rec["origen"] = "plone_projectes"
        else:
            rec["origen"] = "plone"
        pdf = re.search(r'href="([^"]+\.pdf[^"]*)"', html, re.I)
        if pdf:
            rec["documento_url"] = self._abs_url(pdf.group(1), url)
        return rec

    def _rss_row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        url = str(row["url"])
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"], url) or "1970-01-01",
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen", "rss"),
        }

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for page in LICENCIA_PAGES:
            try:
                html = self._fetch(page, timeout=45)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            if "tramit.figueres.org" in page:
                titulo = "Consulta d'expedients (sede tramit.figueres.org)"
                if page not in seen_urls:
                    seen_urls.add(page)
                    rows.append(
                        {
                            "id": _stable_id("lic", page),
                            "fecha_concesion": "1970-01-01",
                            "tipo": titulo,
                            "distrito": "Figueres",
                            "lat": None,
                            "lon": None,
                            "url": page,
                            "source": "ayuntamiento",
                            "origen": "sede_consulta",
                        }
                    )
                continue
            for href, text in RE_LINK.findall(html):
                t = _strip_html(text)
                u = self._abs_url(href, page)
                if len(t) < 6 or u in seen_urls:
                    continue
                if "figueres.cat" not in u and "tramit.figueres.org" not in u:
                    continue
                if not RE_LICENCIA.search(t) and not RE_LICENCIA.search(u):
                    continue
                seen_urls.add(u)
                rows.append(
                    {
                        "id": _stable_id("lic", u),
                        "fecha_concesion": _fecha_from_blob(t, u) or "1970-01-01",
                        "tipo": t[:200] if t else "Tràmit llicències",
                        "distrito": "Figueres",
                        "lat": None,
                        "lon": None,
                        "url": u,
                        "source": "ayuntamiento",
                        "origen": "tramits_web",
                    }
                )
        for feed_rows in (
            self._collect_rss(PLANEJAMENT_RSS, "plone_planejament"),
            self._collect_rss(PROJECTES_RSS, "plone_projectes"),
        ):
            for item in feed_rows:
                blob = f"{item['titulo']} {item['url']}"
                if not RE_LICENCIA.search(blob):
                    continue
                u = item["url"]
                if u in seen_urls:
                    continue
                seen_urls.add(u)
                rows.append(
                    {
                        "id": _stable_id("lic", u),
                        "fecha_concesion": item.get("fecha")
                        or _fecha_from_blob(item["titulo"], u)
                        or "1970-01-01",
                        "tipo": item["titulo"][:200],
                        "distrito": "Figueres",
                        "lat": None,
                        "lon": None,
                        "url": u,
                        "source": "ayuntamiento",
                        "origen": "rss_suspension",
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        by_id: dict[str, dict[str, Any]] = {}
        rss_rows = self._collect_rss(PLANEJAMENT_RSS, "plone_planejament") + self._collect_rss(
            PROJECTES_RSS, "plone_projectes"
        )
        for row in rss_rows:
            rec = self._rss_row_to_proyecto(row)
            by_id[rec["id"]] = rec
        urls = set(self._collect_crawl_urls())
        for row in rss_rows:
            urls.add(row["url"])
        for url in sorted(urls):
            if not self._is_project_url(url):
                continue
            rec = self._parse_project_page(url)
            if rec:
                by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "rss": sum(1 for r in rows if str(r.get("origen", "")).startswith("plone_")),
            "crawl": len(urls),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {**stats, "delta": after - before}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_info()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps(
                {"updated_at": datetime.now(timezone.utc).isoformat(), "rows": after},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "status": "ok", "delta": after - before}
