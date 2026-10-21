from __future__ import annotations

import email.utils
import hashlib
import html as htmlmod
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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter

WEB_BASE = "https://www.toledo.es"
SEDE_BASE = "https://sede.toledo.es/eAdmin"
A2_BASE = "https://a2.toledo.es"
MUNICIPIO = "Toledo"
ID_PREFIX = "toledo"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
URBANISMO_HUB = f"{WEB_BASE}/servicios-municipales/urbanismo/"
RSS_URBANISMO = f"{WEB_BASE}/category/urbanismo/feed/"

DEFAULT_SEARCH_TERMS = (
    "PLANEAMIENTO",
    "URBANISMO",
    "INFORMACION PUBLICA",
    "INFORMACIÓN PÚBLICA",
    "LICENCIA",
    "PGOU",
    "PGMOU",
    "PERI",
    "PAU",
    "ESTUDIO DETALLE",
    "EXPROPIACION",
    "REPARCEL",
    "CALIFICACION",
)

DEFAULT_LICENCIA_TRAMITES: list[tuple[str, str]] = [
    ("licencia-de-obra-mayor", "Licencia de obra mayor"),
    ("licencia-de-obra-menor", "Licencia de obra menor"),
    ("licencias-urbanisticas", "Licencias urbanísticas"),
    (
        "licencia-de-apertura-de-establecimientos-instalaciones-actividades-y-servicios",
        "Licencia de apertura de establecimientos, instalaciones, actividades y servicios",
    ),
    ("licencia-para-cambio-de-uso", "Licencia para cambio de uso"),
    (
        "licencia-para-aprovechamiento-especial-y-utilizacion-privativa-del-dominio-publico-local",
        "Licencia para aprovechamiento especial y utilización privativa del dominio público local",
    ),
    ("licencia-municipal-de-vado-permanente-laboral", "Licencia municipal de vado permanente / laboral"),
]

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrir(?:Original)?\('([^']+)'\)")
RE_EXPTE = re.compile(r"(?i)(?:EXP(?:EDIENTE)?\.?|EXPDTE\.?)\s*[:.]?\s*([0-9]+[/\-_][0-9]{2,4})")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|ambiental|apertura|obra)|"
    r"declaraci[oó]n responsable.*obra|comunicaci[oó]n previa|primera ocupaci[oó]n|"
    r"cedula|c[eé]dula urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|expropi|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"modificaci[oó]n.*pgou|estudio (?:de )?detalle|proyecto de (?:urbaniz|actuaci)|"
    r"sector |pau |peri |calificaci[oó]n urban|anejo expropi|instalaciones urban)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|bolsa de trabajo|polic[ií]a local|jurado|empadron|"
    r"orden del d[ií]a.*junta de gobierno|carrozas|mercadillo|notoriedad|herederos|"
    r"censo electoral|precio p[uú]blico|tribut)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_POST_LINK = re.compile(r'href="(https://www\.toledo\.es/[a-z0-9][a-z0-9\-]+/?)"', re.I)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)
RE_TIME = re.compile(r'<time[^>]+datetime="([^"]+)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    t = unescape(htmlmod.unescape(text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_ISO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    try:
        return email.utils.parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _pdf_url_sede(token: str) -> str:
    return (
        f"{SEDE_BASE}/ValidarDocumento.do?id_Documento="
        f"{urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n or "estudio detalle" in n:
        return "estudio de detalle"
    if "peri" in n or "reforma interior" in n:
        return "PERI"
    if "pau" in n or "programa de actuaci" in n:
        return "PAU"
    if "pgou" in n or "pgmou" in n or "plan general" in n:
        return "PGMOU / planeamiento"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "expropi" in n:
        return "expropiación"
    if "reparcel" in n or "urbaniz" in n:
        return "reparcelación / urbanización"
    if "calificaci" in n:
        return "calificación urbanística"
    return "urbanismo"


class ToledoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress toledo.es (urbanismo RSS + noticias) + sede eAdmin tablón + catálogo ALHAJA (a2)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.a2_base = str(self.config.get("a2_base") or A2_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_ALL)
        self.rss_url = str(self.config.get("rss_urbanismo") or RSS_URBANISMO)
        self.urbanismo_hub = str(self.config.get("urbanismo_hub") or URBANISMO_HUB)
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.licencia_tramites = [
            (str(s), str(t))
            for s, t in (self.config.get("licencia_tramites") or DEFAULT_LICENCIA_TRAMITES)
        ]
        self.max_urb_pages = int(self.config.get("max_urb_pages", 10))

    def _fetch(self, url: str, data: bytes | None = None, *, latin1: bool = False) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-toledo/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
        if latin1 or "sede.toledo.es" in url:
            return raw.decode("iso-8859-1", errors="replace")
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")

    def _abs_web(self, href: str) -> str:
        return unescape(urljoin(f"{self.web_base}/", href))

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(title_raw)
            if not title:
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            doc_token = doc_m.group(1) if doc_m else None
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "url": detail_url,
                "doc_token": doc_token,
                "expte": _parse_expte(title),
            }
            if doc_token:
                rec["pdf_url"] = _pdf_url_sede(doc_token)
            by_id[ann_id] = rec
        return by_id

    def _search_tablon(self, term: str) -> dict[str, dict[str, Any]]:
        body = urllib.parse.urlencode({"referenciaBusqueda": term}).encode("utf-8")
        try:
            html = self._fetch(self.tablon_url, data=body, latin1=True)
        except urllib.error.URLError:
            return {}
        return self._parse_tablon_html(html)

    def _collect_tablon(self) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(self.tablon_url, latin1=True)
            by_id.update(self._parse_tablon_html(html))
        except urllib.error.URLError:
            pass
        for term in self.search_terms:
            for ann_id, rec in self._search_tablon(term).items():
                by_id.setdefault(ann_id, rec)
        return by_id

    def _parse_rss(self) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(self.rss_url)
            root = ET.fromstring(xml_text)
        except (urllib.error.URLError, ET.ParseError):
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = _clean_title(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            content = item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or ""
            pdfs = [self._abs_web(u) for u in RE_PDF.findall(content)]
            rows.append(
                {
                    "titulo": title,
                    "url": link,
                    "fecha": fecha,
                    "pdf_urls": pdfs[:8],
                    "origen": "rss_urbanismo",
                }
            )
        return rows

    def _collect_urb_listing_posts(self) -> list[str]:
        urls: set[str] = set()
        skip = (
            "servicios-municipales",
            "category",
            "wp-content",
            "author",
            "page",
            "feed",
            "tag",
        )
        for page in range(1, self.max_urb_pages + 1):
            page_url = (
                self.urbanismo_hub
                if page == 1
                else f"{self.urbanismo_hub}page/{page}/"
            )
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_POST_LINK.finditer(html):
                u = m.group(1).rstrip("/") + "/"
                if any(s in u for s in skip):
                    continue
                if u.rstrip("/") == self.web_base:
                    continue
                urls.add(u)
        return sorted(urls)

    def _fetch_post_detail(self, post_url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(post_url)
        except urllib.error.URLError:
            return None
        h1 = RE_H1.search(html)
        title = _clean_title(h1.group(1)) if h1 else ""
        if not title:
            return None
        time_m = RE_TIME.search(html)
        fecha = None
        if time_m:
            fecha = _parse_fecha_dmy(time_m.group(1)) or time_m.group(1)[:10]
        pdfs = list(dict.fromkeys(self._abs_web(u) for u in RE_PDF.findall(html)))
        return {
            "titulo": title,
            "url": post_url,
            "fecha": fecha,
            "pdf_urls": pdfs[:12],
            "origen": "wp_post",
        }

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for slug, nombre in self.licencia_tramites:
            url = f"{self.a2_base}/sede/procedimiento/{slug}"
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": nombre[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": nombre,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo (sede ALHAJA); no concesión publicada en tablón",
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        title = str(item.get("titulo") or "")
        if RE_NOISE.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        key = item.get("url") or title
        out: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": item.get("fecha") or item.get("fecha_ini"),
            "tipo": _proyecto_tipo(title),
            "url": item.get("url") or self.urbanismo_hub,
            "source": "ayuntamiento",
            "origen": item.get("origen", "web"),
            "expte": item.get("expte") or _parse_expte(title),
        }
        pdfs = item.get("pdf_urls") or []
        if item.get("pdf_url"):
            pdfs = [item["pdf_url"]] + list(pdfs)
        if pdfs:
            out["pdf_url"] = pdfs[0]
            out["pdf_urls"] = pdfs[:10]
        return out

    def _tablon_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80})", title)
        out: dict[str, Any] = {
            "id": _stable_id("lic", rec.get("expte") or rec["ann_id"]),
            "fecha_concesion": rec.get("fecha_ini"),
            "tipo": (tipo_m.group(1).strip()[:120] if tipo_m else "licencia"),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "expte": rec.get("expte"),
            "url": rec["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        return out

    def _tablon_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        if RE_LICENCIA.search(rec["titulo"]) and not RE_PROYECTO.search(rec["titulo"]):
            return None
        return self._item_to_proyecto({**rec, "origen": "tablon"})

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

    def _merge_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(item: dict[str, Any] | None) -> None:
            if not item:
                return
            proy = self._item_to_proyecto(item) if "municipio" not in item else item
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)

        for item in self._parse_rss():
            add(item)
        for post_url in self._collect_urb_listing_posts():
            detail = self._fetch_post_detail(post_url)
            if detail:
                add(detail)
        for rec in self._collect_tablon().values():
            add(self._tablon_to_proyecto(rec))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_tablon().values():
            lic = self._tablon_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_licencias": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_tablon().values():
            lic = self._tablon_to_licencia(rec)
            if lic:
                existing[lic["id"]] = lic
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
        rows = self._merge_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "rss": sum(1 for r in rows if r.get("origen") == "rss_urbanismo"),
            "wp_post": sum(1 for r in rows if r.get("origen") == "wp_post"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
