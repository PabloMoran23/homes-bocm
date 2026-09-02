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

WEB_BASE = "https://www.aytotarifa.com"
SEDE_BASE = "https://sede.aytotarifa.com"
MUNICIPIO = "Tarifa"
ID_PREFIX = "tarifa"

TABLON_URL = (
    f"{SEDE_BASE}/sede/castellano/Externos/ASP/enlacesPortada/"
    "EnlacesPortadaSede.asp?enlacePortada=tablon"
)
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"

DEFAULT_RSS_FEEDS: list[str] = [
    f"{WEB_BASE}/notice-category/urbanismo-informacion-publica/feed/",
    f"{WEB_BASE}/notice-category/oficina-tecnica/feed/",
    f"{WEB_BASE}/notice-category/informacion-publica/feed/",
    f"{WEB_BASE}/notice-category/e-l-a-facinas-informacion-publica/feed/",
]

DEFAULT_NOTICE_CATEGORIES: list[str] = [
    "urbanismo-informacion-publica",
    "oficina-tecnica",
    "informacion-publica",
    "e-l-a-facinas-informacion-publica",
]

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/pgou/",
    f"{WEB_BASE}/atencionalaciudadania/informacion-citaprevia/",
]

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (f"{WEB_BASE}/atencionalaciudadania/informacion-citaprevia/#obras", "Licencia de obras"),
    (f"{WEB_BASE}/atencionalaciudadania/informacion-citaprevia/#obrasdr", "Declaración responsable de obras"),
    (f"{WEB_BASE}/atencionalaciudadania/informacion-citaprevia/#ovp", "Licencia de ocupación de vía pública"),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|calificaci[oó]n ambiental|"
    r"inicio de obra|obra (?:mayor|menor)|ocupaci[oó]n de v[ií]a p[uú]blica)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|boja|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|atu|"
    r"delimitaci[oó]n|unidad(?:es)? de ejecuci[oó]n|urbanizaci[oó]n|consulta p[uú]blica|"
    r"cesi[oó]n.*parcela|vivienda(?:s)? (?:asequible|protegida)|retranqueo)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"presupuest|subvenci[oó]n deportiv|empadron|tribut|matrimonio civil|"
    r"tribunal calificador|bolsa de|plan de cooperaci[oó]n local|"
    r"cr[eé]dito extraordinario|suplemento de cr[eé]dito|censo electoral|"
    r"convocatoria pleno|recursos humanos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_TIME = re.compile(r"(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*([A-Z]?\d{1,4}[/\-]\d{4}[^/\s]*)")
RE_TABLON_NUMINT = re.compile(r"numint=([A-F0-9]+)", re.I)
RE_NOTICE_CARD = re.compile(
    r'href="(https://www\.aytotarifa\.com/notices/[^"#?]+/?)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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


def _parse_rss_date(text: str) -> str | None:
    try:
        return email.utils.parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, IndexError):
        return None


def _fecha_from_text(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_iso(text)


def _clean_title(text: str) -> str:
    t = unescape(htmlmod.unescape(text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "atu" in n or ("delimitaci" in n and "actuaci" in n):
        return "ATU / delimitación"
    if "plan parcial" in n or "atu-ta" in n:
        return "plan parcial"
    if "estudio de detalle" in n or "estudio detalle" in n:
        return "estudio de detalle"
    if "urbanizaci" in n and "sector" in n:
        return "proyecto de urbanización"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "convenio" in n or "cesi" in n and "parcela" in n:
        return "convenio / cesión suelo"
    if "calificaci" in n and "ambiental" in n:
        return "calificación ambiental"
    if "licencia" in n:
        return "licencia publicada"
    if "modificaci" in n:
        return "modificación PGOU"
    return "urbanismo"


class TarifaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress TownPress + sede Absis/eConstruye (tablón) + SITUA Junta de Andalucía."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.rss_feeds = [str(u) for u in (self.config.get("rss_feeds") or DEFAULT_RSS_FEEDS)]
        self.notice_categories = [
            str(c) for c in (self.config.get("notice_categories") or DEFAULT_NOTICE_CATEGORIES)
        ]
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [
            (str(u), str(t))
            for u, t in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self.max_notice_pages = int(self.config.get("max_notice_pages", 12))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-tarifa/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_web(self, href: str, base: str | None = None) -> str:
        return unescape(urljoin(base or f"{self.web_base}/", href))

    def _tablon_detail_url(self, numint: str) -> str:
        return (
            f"{self.sede_base}/sede/castellano/Externos/ASP/dlg/TablonAnuncios/"
            f"dlgVerDetalleAnuncio.aspx?numint={numint}"
        )

    def _parse_tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.config.get("tablon_url") or TABLON_URL)
        except urllib.error.URLError:
            return []

        html = htmlmod.unescape(html)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in RE_FECHA_DMY_TIME.finditer(html):
            chunk = html[m.start() : m.start() + 2500]
            texts = [
                t.strip()
                for t in re.findall(r">([^<]{3,400})<", chunk)
                if t.strip() and not t.startswith("&")
            ]
            if len(texts) < 2:
                continue
            titulo = texts[0]
            unidad = texts[1] if len(texts) > 1 else ""
            tipo_doc = texts[2] if len(texts) > 2 else ""
            numint_m = RE_TABLON_NUMINT.search(chunk)
            numint = numint_m.group(1) if numint_m else _stable_id("tab", titulo + m.group(1))
            if numint in seen:
                continue
            seen.add(numint)
            rows.append(
                {
                    "titulo": _clean_title(titulo),
                    "fecha": _parse_fecha_dmy(m.group(1)),
                    "unidad": _clean_title(unidad),
                    "tipo_doc": _clean_title(tipo_doc),
                    "url": self._tablon_detail_url(numint) if numint_m else TABLON_URL,
                    "numint": numint,
                    "origen": "tablon_absis",
                }
            )
        return rows

    def _parse_rss_feed(self, feed_url: str) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(feed_url)
            root = ET.fromstring(xml_text)
        except (urllib.error.URLError, ET.ParseError):
            return []

        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = _clean_title(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            if not title or not link:
                continue
            link = link.split("?utm_")[0].rstrip("/") + "/"
            rows.append(
                {
                    "titulo": title,
                    "fecha": _parse_rss_date(item.findtext("pubDate") or ""),
                    "url": link,
                    "origen": "wp_rss",
                }
            )
        return rows

    def _collect_notice_archives(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for slug in self.notice_categories:
            for page in range(1, self.max_notice_pages + 1):
                if page == 1:
                    url = f"{self.web_base}/notice-category/{slug}/"
                else:
                    url = f"{self.web_base}/notice-category/{slug}/page/{page}/"
                try:
                    html = self._fetch(url)
                except urllib.error.URLError:
                    break

                found = 0
                for m in RE_NOTICE_CARD.finditer(html):
                    notice_url = m.group(1).rstrip("/") + "/"
                    if notice_url in seen:
                        continue
                    seen.add(notice_url)
                    found += 1
                    rows.append(
                        {
                            "titulo": _clean_title(m.group(2)),
                            "fecha": None,
                            "url": notice_url,
                            "origen": "wp_archivo",
                        }
                    )
                if found == 0:
                    break

        return rows

    def _collect_pgou_docs(self) -> list[dict[str, Any]]:
        url = f"{self.web_base}/pgou/"
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        rows.append(
            {
                "titulo": "PGOU Tarifa — buscador SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_SEARCH,
                "origen": "situa",
                "key": SITUA_SEARCH,
            }
        )
        seen.add(SITUA_SEARCH)

        for m in RE_PDF.finditer(html):
            pdf = self._abs_web(m.group(1), url)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = _clean_title(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "titulo": name or "Documento PGOU Tarifa",
                    "fecha": _fecha_from_text(name) or _fecha_from_text(pdf),
                    "tipo": "planeamiento",
                    "url": url,
                    "pdf_url": pdf,
                    "origen": "wp_pgou",
                    "key": pdf,
                }
            )
        return rows

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('unidad', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob):
            return None
        key = row.get("numint") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / calificación ambiental",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"expte": m.group(1)} if (m := RE_EXPTE.search(row["titulo"])) else {}),
        }

    def _tramite_to_licencia(self, titulo: str, url: str) -> dict[str, Any]:
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": url,
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "wp_tramite",
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('unidad', '')} {row.get('tipo', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("origen") == "tablon_absis":
            if not RE_PROYECTO.search(blob):
                return None
            if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
                return None
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("numint") or row.get("pdf_url") or row.get("key") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if m := RE_EXPTE.search(titulo):
            rec["expte"] = m.group(1)
        return rec

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
        for item in self._parse_tablon_rows():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for titulo, url in self.licencia_pages:
            rec = self._tramite_to_licencia(titulo, url)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_absis"),
            "tramites": sum(1 for r in rows if r.get("origen") == "wp_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._parse_tablon_rows():
            add(self._row_to_proyecto(item))

        wp_rows: list[dict[str, Any]] = []
        for feed in self.rss_feeds:
            wp_rows.extend(self._parse_rss_feed(feed))
        wp_rows.extend(self._collect_notice_archives())
        for item in wp_rows:
            add(self._row_to_proyecto(item))

        for item in self._collect_pgou_docs():
            add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_absis"),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp")),
            "situa": sum(1 for r in rows if r.get("origen") == "situa"),
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
