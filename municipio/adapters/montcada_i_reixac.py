from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.montcada.cat"
MUNICIPIO = "Montcada i Reixac"
ID_PREFIX = "montcada-i-reixac"
INE_MUN = "08124"

TAULER_URL = "https://tauler.seu.cat/inici.do?idens=812520002"
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
RPUC_PORTAL = (
    f"https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?"
    f"reqCode=cerca&municipiSel={INE_MUN}"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ajuntament/planejament",
    f"{WEB_BASE}/ajuntament/gestio-urbanistica",
    f"{WEB_BASE}/temes/urbanisme",
    f"{WEB_BASE}/ajuntament/normativa/normativa-urbanistica",
    f"{WEB_BASE}/ajuntament/anuncis-edictes",
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/temes/urbanisme", "Urbanisme i llicències d'obres"),
    (
        f"{WEB_BASE}/serveis-i-tramits/tramits-i-gestions/placa-informativa-dobra.html",
        "Placa informativa d'obra",
    ),
    (
        f"{WEB_BASE}/serveis-i-tramits/tramits-i-gestions/consulta-sobre-expedients-de-larea-territorial.html",
        "Consulta expedients àrea territorial",
    ),
    (
        f"{WEB_BASE}/serveis-i-tramits/tramits-i-gestions/acces-als-expedients-finalitzats-de-larea-territorial.html",
        "Accés expedients finalitzats àrea territorial",
    ),
    (TAULER_URL, "e-TAULER — anuncis i edictes (exposició pública)"),
    (f"{WEB_BASE}/serveis-i-tramits/instancia", "Sol·licitud genèrica / instància"),
]

RE_HOST = re.compile(r"^https?://(?:www\.)?montcada\.cat/", re.I)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autoritzaci[oó] d.?obres|obra (?:major|menor)|placa informativa|enderroc|"
    r"primera ocupaci[oó])",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|expedient|exp\.|reparcel|mpgm|mppe|pgm|"
    r"consulta pr[eè]via|aprovaci[oó]|modificaci[oó]|informaci[oó] p[uú]blica|"
    r"exposici[oó]|soterrament|urbanitz|gesti[oó] urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(subvenci[oó]|oferta p[uú]blica.*personal|convocat[oò]ria.*selecci[oó]|"
    r"farm[aà]cia|factura electr[oò]nica|borsa de treball)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(
    r"(?i)(?:exp(?:edient)?\.?|n[uú]m\.?\s*exp\.?)\s*[:.]?\s*"
    r"(\d{1,4}/\d{4}/[A-Z]{1,6}|\d{1,4}/\d{4}[A-Z]{0,6}|\d{1,4}-\d{4}[A-Z]*)",
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PROJECT_PATH = re.compile(
    r"(?i)/(?:ajuntament/(?:planejament|gestio-urbanistica)|temes/urbanisme)/[^\"#?]+\.html$"
)


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    m = RE_EXPEDIENTE.search(text or "")
    if m:
        parts = re.findall(r"\d+", m.group(1))
        if len(parts) >= 2:
            year = parts[1] if len(parts[1]) == 4 else parts[0]
            if len(year) == 4:
                return f"{year}-06-01"
    blob = f"{text} {url}"
    years = [int(y.group(1)) for y in RE_YEAR.finditer(blob) if 1985 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "reparcel" in n:
        return "reparcelación"
    if "consulta pr" in n:
        return "consulta previa"
    if "mpgm" in n or "pgm" in n:
        return "modificación PGM"
    if "plan parcial" in n or "mppe" in n:
        return "plan parcial / especial"
    if "soterrament" in n:
        return "infraestructura / soterramiento"
    if "aprovaci" in n and "inicial" in n:
        return "aprobación inicial"
    if "aprovaci" in n and "definitiva" in n:
        return "aprobación definitiva"
    if "suspensi" in n and "llic" in n:
        return "suspensión de licencias"
    if "informaci" in n or "exposici" in n or "anunci" in n:
        return "información pública"
    return "planeamiento"


class MontcadaIReixacAyuntamientoAdapter(AyuntamientoAdapter):
    """CMS montcada.cat (planejament/gestió urbanística) + e-TAULER (referencia); sin GIS enlazable."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 80))
        self.ua = str(self.config.get("user_agent", "poc-bocm-montcada-i-reixac/1.0"))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_maybe(self, url: str) -> str | None:
        try:
            return self._fetch(url)
        except (urllib.error.URLError, TimeoutError, OSError, urllib.error.HTTPError):
            return None

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{self.web_base}/", unescape(href))

    def _is_project_html(self, url: str) -> bool:
        clean = urllib.parse.unquote(url.split("#")[0].split("?")[0]).rstrip("/")
        if not RE_HOST.match(clean):
            return False
        if not clean.endswith(".html"):
            return False
        if not RE_PROJECT_PATH.search(clean):
            return False
        if RE_EXCLUDE.search(clean):
            return False
        return bool(RE_PROYECTO.search(clean))

    def _is_urban_pdf(self, url: str) -> bool:
        low = url.lower()
        if not low.endswith(".pdf"):
            return False
        if "/media/repository/" not in low:
            return False
        return bool(RE_PROYECTO.search(low))

    def _sitemap_project_urls(self) -> list[str]:
        out: list[str] = []
        index_url = f"{self.web_base}/sitemap.xml"
        html = self._fetch_maybe(index_url)
        if not html:
            return out
        try:
            root = ET.fromstring(html)
        except ET.ParseError:
            return out
        ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        sitemap_locs = [
            el.text.strip()
            for el in root.findall(".//sm:loc", ns)
            if el.text and "sitemap" in el.text
        ]
        for sm_url in sitemap_locs[:25]:
            sm_xml = self._fetch_maybe(sm_url)
            if not sm_xml:
                continue
            try:
                sm_root = ET.fromstring(sm_xml)
            except ET.ParseError:
                continue
            for loc in sm_root.findall(".//sm:loc", ns):
                if not loc.text:
                    continue
                u = loc.text.strip()
                if self._is_project_html(u):
                    out.append(u.split("?")[0])
        return list(dict.fromkeys(out))

    def _collect_links_from_seeds(self) -> tuple[list[str], list[str]]:
        html_urls: set[str] = set()
        pdf_urls: set[str] = set()
        for seed in self.seed_pages:
            html = self._fetch_maybe(seed)
            if not html:
                continue
            for href in RE_HREF.findall(html):
                if href.startswith(("#", "mailto:", "javascript:")):
                    continue
                u = self._abs_url(href, seed).split("#")[0]
                if self._is_project_html(u):
                    html_urls.add(u.rstrip("/"))
                elif self._is_urban_pdf(u):
                    pdf_urls.add(u)
        return sorted(html_urls), sorted(pdf_urls)

    def _parse_project_page(self, url: str) -> dict[str, Any] | None:
        html = self._fetch_maybe(url)
        if not html:
            return None
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
        titulo = _strip_html(h1.group(1)) if h1 else ""
        if not titulo:
            slug = url.rstrip("/").split("/")[-1].replace(".html", "")
            titulo = slug.replace("-", " ").strip().title()
        if RE_EXCLUDE.search(titulo):
            return None
        blob = f"{titulo} {url}"
        if not RE_PROYECTO.search(blob):
            return None
        fecha = _fecha_from_blob(titulo, url)
        exp_m = RE_EXPEDIENTE.search(titulo) or RE_EXPEDIENTE.search(_strip_html(html[:8000]))
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha or "1970-01-01",
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": "web_project_page",
        }
        if exp_m:
            rec["expediente"] = exp_m.group(1).strip()
        pdf = re.search(r'href="(/media/repository/[^"]+\.pdf)"', html, re.I)
        if pdf:
            rec["documento_url"] = self._abs_url(pdf.group(1), url)
        return rec

    def _pdf_row(self, url: str) -> dict[str, Any]:
        titulo = urllib.parse.unquote(url.split("/")[-1]).replace(".pdf", "").replace("_", " ")
        titulo = re.sub(r"\s+", " ", titulo).strip() or url
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": _fecha_from_blob(titulo, url) or "1970-01-01",
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": "repository_pdf",
        }

    def _merge_proyectos(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for row in rows:
            rid = row.get("id") or _stable_id("proy", row.get("url", ""))
            if rid not in by_id:
                by_id[rid] = row
                continue
            prev = by_id[rid]
            if not prev.get("documento_url") and row.get("documento_url"):
                prev["documento_url"] = row["documento_url"]
            if prev.get("fecha") == "1970-01-01" and row.get("fecha") not in (None, "1970-01-01"):
                prev["fecha"] = row["fecha"]
        return list(by_id.values())

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        html_urls, pdf_urls = self._collect_links_from_seeds()
        html_urls = list(dict.fromkeys(html_urls + self._sitemap_project_urls()))
        rows: list[dict[str, Any]] = []
        for url in html_urls[: self.max_crawl_pages]:
            rec = self._parse_project_page(url)
            if rec:
                rows.append(rec)
        for url in pdf_urls:
            rows.append(self._pdf_row(url))
        return self._merge_proyectos(rows)

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url, label in DEFAULT_LICENCIA_PAGES:
            if page_url in seen:
                continue
            seen.add(page_url)
            rows.append(
                {
                    "id": _stable_id("lic", page_url),
                    "fecha_concesion": "1970-01-01",
                    "tipo": label[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": "tramites_informativos",
                }
            )
        urbanisme = self._fetch_maybe(f"{self.web_base}/temes/urbanisme")
        if urbanisme:
            for href, text in RE_LINK.findall(urbanisme):
                t = _strip_html(text)
                u = self._abs_url(href, f"{self.web_base}/temes/urbanisme")
                if u in seen or len(t) < 8:
                    continue
                if "montcada.cat" not in u and "tauler.seu.cat" not in u:
                    continue
                if not (RE_LICENCIA.search(t) or RE_LICENCIA.search(u)):
                    continue
                seen.add(u)
                rows.append(
                    {
                        "id": _stable_id("lic", u),
                        "fecha_concesion": _fecha_from_blob(t, u) or "1970-01-01",
                        "tipo": t[:200],
                        "distrito": MUNICIPIO,
                        "lat": None,
                        "lon": None,
                        "url": u,
                        "source": "ayuntamiento",
                        "origen": "urbanisme_web",
                    }
                )
        return rows

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "mode": "backfill"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.utcnow().isoformat() + "Z", "count": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "mode": "update"}

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "mode": "backfill"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"updated_at": datetime.utcnow().isoformat() + "Z", "count": len(rows)}),
            encoding="utf-8",
        )
        return {"rows": len(rows), "mode": "update"}
