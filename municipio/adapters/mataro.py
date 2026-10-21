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

WEB_BASE = "https://www.mataro.cat"
MUNICIPIO = "Mataró"
ID_PREFIX = "mataro"

EXPOSICION_ES = (
    f"{WEB_BASE}/es/temas/urbanismo/planificacion-urbanistica/"
    "planeamiento-urbanistico-en-exposicion-publica"
)
EXPOSICION_ES_VIGENT = (
    f"{EXPOSICION_ES}/documents-en-periode-d2019exposicio-publica-vigent-1"
)
EXPOSICION_CA = (
    f"{WEB_BASE}/ca/temes/urbanisme/el-planejament-urbanistic/"
    "planejament-en-periode-dexposicio-publica"
)
LICENCIAS_CA = f"{WEB_BASE}/ca/temes/urbanisme/llicencies-dobres-i-activitats"
LICENCIAS_ES = f"{WEB_BASE}/es/temas/urbanismo/licencias-de-obras-y-actividades"
TRAMITS_CA = f"{WEB_BASE}/ca/tramits"
RSS_URL = f"{WEB_BASE}/rss.xml"
SEDE_BASE = "https://seu.mataro.cat"

DEFAULT_SEED_PAGES: list[str] = [
    EXPOSICION_CA,
    EXPOSICION_ES,
    EXPOSICION_ES_VIGENT,
    LICENCIAS_CA,
    LICENCIAS_ES,
]

EXPOSICION_MARKERS = (
    "planeamiento-urbanistico-en-exposicion-publica",
    "planejament-en-periode-dexposicio-publica",
)
RE_SKIP_SLUG = re.compile(
    r"(?i)^(documents-en-periode|planeamiento-urbanistico-en-exposicion-publica|"
    r"planejament-en-periode-dexposicio-publica|planejament-en-periode-d2019exposicio-publica|"
    r"documents-en-periode-d2019exposicio-publica-vigent-1)$"
)
RE_MATARO_HOST = re.compile(r"^https?://(?:www\.)?mataro\.cat/", re.I)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|licencias|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|suspensi[oó]n de l"
    r"licencias|suspensio de llicencies|obra (?:major|menor)|activitat)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|poum|pe-\d+|mpg-|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudi de detall|estudio en detalle|ed-\s*\d+|pmu-|pdivm|ordenaci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TRAMIT = re.compile(r"(?i)tramit|tràmit|sollicitud|solicitud|gesti[oó]n")


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
    if "estudi de detall" in n or "estudio en detalle" in n or re.search(r"\bed-\s*\d+", n):
        return "estudio de detalle"
    if "plan especial" in n or re.search(r"\bpe-\d+", n):
        return "plan especial"
    if "plan parcial" in n or re.search(r"\bpp-\d+", n):
        return "plan parcial"
    if "poum" in n or "plan general" in n or "pgou" in n or re.search(r"\bmpg-", n):
        return "planeamiento general"
    if "pmu" in n:
        return "plan de mejora urbana"
    if "suspensi" in n and "llic" in n:
        return "suspensión de licencias"
    if "expropi" in n:
        return "expropiación"
    if "infraestructura verda" in n or "pdivm" in n:
        return "plan director"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    return "urbanismo"


class MataroAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone mataro.cat (planeamiento en exposición) + trámites licencias; sede opcional."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.rss_url = str(self.config.get("rss_url") or RSS_URL)
        self.fetch_timeout_s = int(self.config.get("fetch_timeout_s", 90))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-mataro/1.0")},
        )
        with urllib.request.urlopen(req, timeout=self.fetch_timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{WEB_BASE}/", unescape(href))

    def _project_slug(self, url: str) -> str | None:
        clean = urllib.parse.unquote(url.split("#")[0].split("?")[0]).rstrip("/")
        if not RE_MATARO_HOST.match(clean):
            return None
        if not any(m in clean for m in EXPOSICION_MARKERS):
            return None
        slug = clean.split("/")[-1]
        if not slug or RE_SKIP_SLUG.match(slug):
            return None
        return slug

    def _is_project_url(self, url: str) -> bool:
        return self._project_slug(url) is not None

    def _collect_exposicion_urls(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        seeds = list(self.seed_pages)
        for seed in seeds:
            if "exposicion" not in seed and "exposicio" not in seed:
                continue
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for href, _ in RE_LINK.findall(html):
                if href.startswith(("mailto:", "javascript:", "#")):
                    continue
                u = self._abs_url(href, seed)
                if not self._is_project_url(u):
                    continue
                u = u.split("#")[0].rstrip("/")
                if u not in seen:
                    seen.add(u)
                    out.append(u)
        return sorted(out)

    def _parse_project_page(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        titulo = _strip_html(h1.group(1)) if h1 else ""
        if not titulo or titulo.lower() in ("planeamiento urbanístico en exposición",):
            slug = url.rstrip("/").split("/")[-1]
            titulo = slug.replace("-", " ").strip().title()
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
            "origen": "plone_exposicion",
        }
        pdf = re.search(r'href="([^"]+\.pdf[^"]*)"', html, re.I)
        if pdf:
            rec["documento_url"] = self._abs_url(pdf.group(1), url)
        return rec

    def _collect_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.rss_url)
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        channel = root.find("channel")
        if channel is None:
            return []
        rows: list[dict[str, Any]] = []
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            date_raw = item.findtext("date") or item.findtext("pubDate") or ""
            if not title or not link:
                continue
            blob = f"{title} {link}"
            if not (RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)):
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": _parse_rss_date(date_raw),
                    "origen": "rss",
                }
            )
        return rows

    def _rss_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('url', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        url = str(row["url"])
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"], url) or "1970-01-01",
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": url,
            "source": "ayuntamiento",
            "origen": "rss",
        }

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        pages = [LICENCIAS_CA, LICENCIAS_ES, TRAMITS_CA]
        for page in pages:
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            for href, text in RE_LINK.findall(html):
                t = _strip_html(text)
                u = self._abs_url(href, page)
                if len(t) < 8 or "mataro.cat" not in u and "gestorn.com" not in u and "seu.mataro" not in u:
                    continue
                if not (RE_LICENCIA.search(t) or RE_TRAMIT.search(t)):
                    continue
                if u in {r["url"] for r in rows}:
                    continue
                rows.append(
                    {
                        "id": _stable_id("lic", u),
                        "fecha_concesion": _fecha_from_blob(t, u) or "1970-01-01",
                        "tipo": t[:200],
                        "distrito": "Mataró",
                        "lat": None,
                        "lon": None,
                        "url": u,
                        "source": "ayuntamiento",
                        "origen": "tramites_web",
                    }
                )
        for item in self._collect_rss():
            blob = f"{item['titulo']} {item['url']}"
            if not RE_LICENCIA.search(blob):
                continue
            u = item["url"]
            rows.append(
                {
                    "id": _stable_id("lic", u),
                    "fecha_concesion": item.get("fecha") or _fecha_from_blob(item["titulo"], u) or "1970-01-01",
                    "tipo": item["titulo"][:200],
                    "distrito": "Mataró",
                    "lat": None,
                    "lon": None,
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": "rss",
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
        for url in self._collect_exposicion_urls():
            rec = self._parse_project_page(url)
            if rec:
                by_id[rec["id"]] = rec
        for item in self._collect_rss():
            rec = self._rss_to_proyecto(item)
            if rec:
                by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "exposicion": sum(1 for r in rows if r.get("origen") == "plone_exposicion"),
            "rss": sum(1 for r in rows if r.get("origen") == "rss"),
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
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

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
