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

WEB_BASE = "https://www.molletvalles.cat"
SEU_BASE = "https://seu.molletvalles.cat"
TRAMITS_BASE = "https://tramits.molletvalles.cat/Ciutadania"
TRANSP_BASE = "https://transparencia.molletvalles.cat"
MUNICIPIO = "Mollet del Vallès"
ID_PREFIX = "mollet-del-valles"

POUM_URL = f"{WEB_BASE}/ca/serveis/urbanisme/poum-de-mollet"
URBANISME_URL = f"{WEB_BASE}/ca/serveis/urbanisme"
GEOPORTAL_CATALOG = f"{WEB_BASE}/ca/la-ciutat/cataleg-de-mapes/geoportal-urbanistic"
NOTICIES_RSS = f"{WEB_BASE}/ca/serveis/urbanisme/noticies/noticies/rss.xml"
SEARCH_RSS = f"{WEB_BASE}/ca/search_rss?SearchableText=planejament"
TRANSP_PROJECTES = (
    f"{TRANSP_BASE}/ca/informacio-publica/accio-de-govern-i-normativa/"
    "normativa-plans-i-programes/memories-i-documents-dels-projectes-normatius-en-curs"
)

DEFAULT_LICENCIA_TRAMITS: list[dict[str, str]] = [
    {
        "id_tramit": "164",
        "titulo": "Informació ciutadana — Llicències urbanístiques",
        "tipo": "licencia urbanística",
    },
    {
        "id_tramit": "153",
        "titulo": "Informació general tramitació execució d'obres i altres tràmits urbanístics",
        "tipo": "licencia de obra",
    },
    {
        "id_tramit": "58",
        "titulo": "Informes o certificats urbanístics INUR",
        "tipo": "informe urbanístico",
    },
    {
        "id_tramit": "30",
        "titulo": "Informe urbanístic associat a la tramitació d'activitats INUA",
        "tipo": "informe urbanístico",
    },
    {
        "id_tramit": "203",
        "titulo": "Informe urbanístic sobre el canvi d'ús (INCU)",
        "tipo": "informe urbanístico",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|informe urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|poum|pgou|informaci[oó]n p[uú]blica|"
    r"expedient|projecte|proyecto|modificaci[oó]n|sector|geoportal|suspensi[oó] de llic|"
    r"urbanitz|reparcel|estudi|àmbit|ambit|pol[ií]gon|aparcament|calder[ií])",
)
RE_EXCLUDE = re.compile(
    r"(?i)(ordenan[cç]a (?:municipal )?de circulaci[oó]|reglament de prestacions|"
    r"cessi[oó] d.excedent d.energia|subministrament d.aigua|zona blava|"
    r"proc[eé]s selectiu|subvenci[oó]n|festa major|aus urbanes|cotorra)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_SEARCH_RESULT = re.compile(
    r'<a[^>]+class="[^"]*searchResults[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
RE_TRANSP_FOLDER = re.compile(
    r'href="(https://transparencia\.molletvalles\.cat/ca/informacio-publica/'
    r'accio-de-govern-i-normativa/normativa-plans-i-programes/'
    r'memories-i-documents-dels-projectes-normatius-en-curs/[^"]+)"',
    re.I,
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


def _parse_iso_date(text: str) -> str | None:
    m = RE_ISO_DATE.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return _parse_iso_date(text.replace("/", "-"))


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


def _proyecto_tipo(titulo: str) -> str:
    n = (titulo or "").lower()
    if "poum" in n or "pla d'ordenaci" in n or "plan de ordenaci" in n:
        return "POUM"
    if "geoportal" in n:
        return "visor urbanístico"
    if "sector" in n or "polígon" in n or "poligon" in n:
        return "sector / PAU"
    if "suspensi" in n and "llic" in n:
        return "suspensión de licencias"
    if "aparcament" in n or "aparcamiento" in n:
        return "proyecto urbanístico"
    if "urbanitz" in n or "urbaniz" in n:
        return "proyecto de urbanización"
    if "informaci" in n or "consulta pública" in n or "consulta publica" in n:
        return "información pública"
    if "memoria" in n or "avantprojecte" in n:
        return "proyecto normativo"
    return "urbanismo"


class MolletDelVallesAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone molletvalles.cat (urbanisme/POUM) + catàleg tràmits + transparència normativa."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tramits_base = str(self.config.get("tramits_base") or TRAMITS_BASE).rstrip("/")
        self.fetch_timeout_s = int(self.config.get("fetch_timeout_s", 90))
        self.max_search_pages = int(self.config.get("max_search_pages", 4))

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-mollet-del-valles/1.0")

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=self.fetch_timeout_s) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or f"{self.web_base}/", unescape(href))

    def _parse_rss(self, rss_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(rss_url)
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
            date_raw = item.findtext("pubDate") or item.findtext("date") or ""
            if not title or not link:
                continue
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": _parse_rss_date(date_raw),
                    "origen": origen,
                }
            )
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('url', '')}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        url = str(row["url"])
        titulo = str(row["titulo"])
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha") or _fecha_from_blob(titulo, url) or "1970-01-01",
            "tipo": _proyecto_tipo(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen", "web"),
        }

    def _collect_search_hits(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(self.max_search_pages):
            start = page * 10
            url = (
                f"{self.web_base}/ca/@@search?SearchableText=planejament"
                f"&sort_on=Date&sort_order=reverse&b_start:int={start}"
            )
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            found = 0
            for href, text in RE_SEARCH_RESULT.findall(html):
                link = self._abs_url(href)
                if link in seen:
                    continue
                seen.add(link)
                titulo = _strip_html(text) or link.rsplit("/", 1)[-1]
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": link,
                        "fecha": None,
                        "origen": "plone_search",
                    }
                )
                found += 1
            if found == 0:
                for href, text in RE_LINK.findall(html):
                    if "/actualitat/noticies/" not in href and "/serveis/urbanisme" not in href:
                        continue
                    link = self._abs_url(href, url)
                    if link in seen:
                        continue
                    titulo = _strip_html(text)
                    if not titulo or len(titulo) < 12:
                        continue
                    seen.add(link)
                    rows.append(
                        {
                            "titulo": titulo[:500],
                            "url": link,
                            "fecha": None,
                            "origen": "plone_search",
                        }
                    )
            if page > 0 and found == 0:
                break
        return rows

    def _collect_poum_assets(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(POUM_URL)
        except urllib.error.URLError:
            return rows
        rows.append(
            {
                "titulo": "POUM de Mollet del Vallès — documentació i geoportal",
                "url": POUM_URL,
                "fecha": "2021-07-05",
                "origen": "poum_portal",
            }
        )
        for pdf in RE_PDF.findall(html):
            pdf_url = self._abs_url(pdf, POUM_URL)
            name = Path(urllib.parse.urlparse(pdf_url).path).name
            rows.append(
                {
                    "titulo": f"POUM Mollet — {name}"[:500],
                    "url": pdf_url,
                    "fecha": _fecha_from_blob(name, pdf_url),
                    "origen": "poum_pdf",
                    "documento_url": pdf_url,
                }
            )
        for href, text in RE_LINK.findall(html):
            if "nexusgeographics" not in href and "geoportal" not in href.lower():
                continue
            link = self._abs_url(href, POUM_URL)
            titulo = _strip_html(text) or "Geoportal urbanístic Mollet"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": link,
                    "fecha": None,
                    "origen": "geoportal_link",
                }
            )
        try:
            geo_html = self._fetch(GEOPORTAL_CATALOG)
            for href, text in RE_LINK.findall(geo_html):
                if "molletgp" not in href and "geoportal" not in href.lower():
                    continue
                link = self._abs_url(href, GEOPORTAL_CATALOG)
                titulo = _strip_html(text) or "Geoportal urbanístic (catàleg de mapes)"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": link,
                        "fecha": None,
                        "origen": "geoportal_catalog",
                    }
                )
        except urllib.error.URLError:
            pass
        return rows

    def _collect_transparencia_normativa(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRANSP_PROJECTES)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for link in RE_TRANSP_FOLDER.findall(html):
            if link.endswith(".pdf") or link in seen:
                continue
            seen.add(link)
            slug = urllib.parse.unquote(link.rstrip("/").split("/")[-1])
            titulo = slug.replace("-", " ").strip().title()
            if RE_EXCLUDE.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo) and "ordenan" not in titulo.lower():
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": link,
                    "fecha": _fecha_from_blob(slug, link),
                    "origen": "transparencia_normativa",
                }
            )
        for pdf in RE_PDF.findall(html):
            pdf_url = pdf if pdf.startswith("http") else urllib.parse.urljoin(TRANSP_PROJECTES, pdf)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            slug = pdf_url.rsplit("/", 1)[-1]
            titulo = slug.replace("-", " ").replace("_", " ")[:500]
            if RE_EXCLUDE.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "url": pdf_url,
                    "fecha": _fecha_from_blob(slug, pdf_url),
                    "origen": "transparencia_pdf",
                    "documento_url": pdf_url,
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        sources: list[dict[str, Any]] = []
        sources.extend(self._parse_rss(NOTICIES_RSS, "rss_urbanisme"))
        sources.extend(self._parse_rss(SEARCH_RSS, "rss_search"))
        sources.extend(self._collect_search_hits())
        sources.extend(self._collect_poum_assets())
        sources.extend(self._collect_transparencia_normativa())
        for row in sources:
            rec = self._row_to_proyecto(row)
            if not rec:
                continue
            doc = row.get("documento_url")
            if doc:
                rec["documento_url"] = doc
            by_id[rec["id"]] = rec
        return list(by_id.values())

    def _tramit_url(self, tramit_id: str) -> str:
        return f"{self.tramits_base}/DetallTramit.aspx?IdTramit={tramit_id}"

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in DEFAULT_LICENCIA_TRAMITS:
            url = self._tramit_url(item["id_tramit"])
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": "1970-01-01",
                    "tipo": item["tipo"],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "titulo": item["titulo"],
                    "origen": "catalogo_tramits",
                }
            )
        try:
            html = self._fetch(f"{self.tramits_base}/TramitsTemes.aspx")
        except urllib.error.URLError:
            return rows
        for m in re.finditer(
            r"DetallTramit\.aspx\?IdTramit=(\d+)'[^>]*>([^<]+)",
            html,
            re.I,
        ):
            tramit_id, titulo = m.group(1), _strip_html(m.group(2))
            blob = titulo
            if not RE_LICENCIA.search(blob):
                continue
            url = self._tramit_url(tramit_id)
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": "1970-01-01",
                    "tipo": titulo[:200],
                    "distrito": MUNICIPIO,
                    "lat": None,
                    "lon": None,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "catalogo_tramits",
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
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

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
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "info": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
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
