from __future__ import annotations

import gzip
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.rubi.cat"
SEDE_BASE = "https://seu.rubi.cat"
SITEMAP_GZ = f"{WEB_BASE}/sitemap.xml.gz"
MUNICIPIO = "Rubí"
ID_PREFIX = "rubi"
INE_MUN = "08184"

DEFAULT_SEEDS: tuple[str, ...] = (
    f"{WEB_BASE}/ca/temes/urbanisme/planejament-vigent-i-gestio-urbanistica/planejament-i-gestio-urbanistica",
    f"{WEB_BASE}/ca/temes/urbanisme/poum",
    f"{WEB_BASE}/ca/temes/urbanisme/poum/documentacio",
    f"{WEB_BASE}/ca/temes/urbanisme/llicencies-i-disciplina-1/llicencies-i-disciplina-dobres",
    f"{SEDE_BASE}/catalogoTramites/listTemes",
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel={INE_MUN}",
    f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca",
)

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|licències|comunicaci[oó]n previa|comunicaci[oó] pr[eè]via|"
    r"declaraci[oó]n responsable|declaraci[oó] responsable|autoritzaci[oó] d.?obres|"
    r"obra (?:major|menor|mayor)|primera ocupaci[oó]|certificat de compatibilitat urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|poum|peu\b|pe-\d|pla (?:parcial|especial|de millora)|"
    r"plan (?:parcial|especial|de mejora)|pgou|pmu|informaci[oó] p[uú]blica|exposici[oó] p[uú]blica|"
    r"expedient|modificaci[oó]|reparcel|sector|cremaller|extractiv|tramitaci[oó].*poum|"
    r"aprovaci[oó] (?:inicial|provisional|definitiva)|consell consultiu|avan[cç] del poum)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(carnaval|mascares|concurs de|veredicte del|color week|genere i urbanisme|"
    r"vida quotidiana|horticultura|proc[eé]s selectiu|subvenci[oó] comer[cç])",
)
RE_SITEMAP_URBAN = re.compile(
    r"(?i)(/temes/urbanisme/|/poum/|planejament-vigent|millora-urb|"
    r"area-de-serveis-territorials/poum/|sala-de-premsa/notes/.*poum|"
    r"noticies/.*(?:poum|planej|millora-urb|peu-|extractiv|cremaller|urbanisme))",
)
RE_SKIP_URL = re.compile(
    r"(?i)(/slides$|/banners$|/portada$|/agenda$|/noticies$|rss\.xml|atom\.xml|"
    r"\.(?:jpg|jpeg|png|gif|gpx)(?:/view)?$|@@redirect)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})[./](\d{1,2})[./](\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_TRAMITE_SHOW = re.compile(r'href="(/catalogoTramites/show/\d+)"[^>]*>([^<]+)</a>', re.I)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    for parser in (_parse_fecha_iso, _parse_fecha_dmy):
        d = parser(text)
        if d:
            return d
    m = re.search(r"(20\d{6})-", url)
    if m:
        s = m.group(1)
        try:
            return datetime(int(s[:4]), int(s[4:6]), int(s[6:8])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1995 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-06-01"
    return None


def _title_from_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0].rstrip("/"))
    if path.endswith("/view"):
        path = path[:-5]
    name = Path(path).name
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    name = name.replace("%20", " ").replace("_", " ").replace("-", " ")
    return _strip_html(name)[:500] or url


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "pla de millora" in n or "plan de mejora" in n:
        return "plan de mejora urbana"
    if "poum" in n and "avan" in n:
        return "avance POUM"
    if "poum" in n:
        return "POUM"
    if "peu" in n or "plan especial" in n or "pla especial" in n:
        return "plan especial"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "aprovaci" in n:
        return "aprobación planeamiento"
    if "extractiv" in n:
        return "plan especial extractivo"
    if "cremaller" in n:
        return "reordenación sectorial"
    return "urbanismo"


class RubiAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone rubi.cat (urbanisme/POUM) + seu.rubi.cat (catálogo trámites obras)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.sitemap_url = str(self.config.get("sitemap_url") or SITEMAP_GZ)
        self.fetch_timeout = int(self.config.get("fetch_timeout_s", 90))

    def _fetch(self, url: str, *, timeout: int | None = None) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-rubi/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout or self.fetch_timeout) as resp:
            return resp.read()

    def _fetch_text(self, url: str) -> str:
        raw = self._fetch(url)
        charset = "utf-8"
        if url.endswith(".gz"):
            raw = gzip.decompress(raw)
        return raw.decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{self.web_base}/", unescape(href))

    def _collect_sitemap_urls(self) -> list[str]:
        try:
            xml = self._fetch_text(self.sitemap_url)
        except (urllib.error.URLError, OSError, gzip.BadGzipFile):
            return []
        try:
            root = ET.fromstring(xml)
        except ET.ParseError:
            return []
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        locs = [el.text.strip() for el in root.findall(".//sm:loc", ns) if el.text]
        if not locs:
            locs = [el.text.strip() for el in root.findall(".//{*}loc") if el.text]
        out: list[str] = []
        seen: set[str] = set()
        for u in locs:
            if not RE_SITEMAP_URBAN.search(u) or RE_SKIP_URL.search(u):
                continue
            if RE_EXCLUDE.search(u):
                continue
            u = u.split("#")[0].rstrip("/")
            if u not in seen:
                seen.add(u)
                out.append(u)
        return sorted(out)

    def _parse_plone_page(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch_text(url)
        except (urllib.error.URLError, OSError):
            return None
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        titulo = _strip_html(h1.group(1)) if h1 else _title_from_url(url)
        blob = f"{titulo} {url}"
        if RE_EXCLUDE.search(blob) or not RE_PROYECTO.search(blob):
            return None
        meta = re.search(r'name="DC\.date\.modified" content="([^"]+)"', html)
        fecha = _parse_fecha_iso(meta.group(1)[:10]) if meta else None
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
            "origen": "plone",
        }
        pdf = re.search(r'href="([^"]+\.pdf[^"]*)"', html, re.I)
        if pdf:
            rec["documento_url"] = self._abs_url(pdf.group(1), url)
        return rec

    def _record_from_pdf_url(self, url: str) -> dict[str, Any] | None:
        titulo = _title_from_url(url)
        blob = f"{titulo} {url}"
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": _fecha_from_blob(titulo, url) or "1970-01-01",
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": "pdf_sitemap",
            "documento_url": url,
        }

    def _collect_seu_tramites(self) -> list[dict[str, Any]]:
        url = f"{self.sede_base}/catalogoTramites/listTemes"
        try:
            html = self._fetch_text(url)
        except (urllib.error.URLError, OSError):
            return []
        lic_rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, text in RE_TRAMITE_SHOW.findall(html):
            titulo = _strip_html(text)
            if not titulo or not RE_LICENCIA.search(titulo):
                continue
            u = self._abs_url(href, url)
            if u in seen:
                continue
            seen.add(u)
            lic_rows.append(
                {
                    "id": _stable_id("lic", u),
                    "fecha_concesion": _fecha_from_blob(titulo, u) or "1970-01-01",
                    "tipo": titulo[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": "seu_tramites",
                }
            )
        return lic_rows

    def _collect_licencia_pages(self) -> list[dict[str, Any]]:
        rows = self._collect_seu_tramites()
        page = f"{self.web_base}/ca/temes/urbanisme/llicencies-i-disciplina-1/llicencies-i-disciplina-dobres"
        try:
            html = self._fetch_text(page)
        except (urllib.error.URLError, OSError):
            return rows
        seen = {r["url"] for r in rows}
        for href, text in RE_LINK.findall(html):
            t = _strip_html(text)
            u = self._abs_url(href, page)
            if "catalogoTramites" not in u and "rubi.cat" not in u:
                continue
            if len(t) < 6 and "catalogoTramites" not in u:
                continue
            if not (RE_LICENCIA.search(t) or RE_LICENCIA.search(u) or "tramites" in u.lower()):
                continue
            if u in seen:
                continue
            seen.add(u)
            rows.append(
                {
                    "id": _stable_id("lic", u),
                    "fecha_concesion": _fecha_from_blob(t, u) or "1970-01-01",
                    "tipo": (t or "Tràmits d'obres")[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": u,
                    "source": "ayuntamiento",
                    "origen": "web_licencias",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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
        for url in self._collect_sitemap_urls():
            if url.lower().endswith(".pdf") or "/.pdf" in url.lower() or url.endswith("/view"):
                rec = self._record_from_pdf_url(url)
            else:
                rec = self._parse_plone_page(url)
            if rec:
                by_id[rec["id"]] = rec
        for seed in DEFAULT_SEEDS:
            if seed.startswith(self.web_base):
                rec = self._parse_plone_page(seed)
                if rec:
                    by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sitemap": sum(1 for r in rows if r.get("origen") in ("plone", "pdf_sitemap")),
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
        rows = self._collect_licencia_pages()
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
