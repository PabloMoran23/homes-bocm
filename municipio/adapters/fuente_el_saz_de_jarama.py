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

WP_BASE = "https://ayuntamientofuentelsaz.com"
SEDE_BASE = "https://sede.ayuntamientofuentelsaz.com/eAdmin"
MUNICIPIO = "Fuente el Saz de Jarama"
ID_PREFIX = "fuente-el-saz"

TABLON_LIST = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TABLON_HOME = f"{SEDE_BASE}/Tablon.do?action=inicioTablon"
TRANSPARENCY_URBANISMO = f"{WP_BASE}/ayuntamiento/portal-de-transparencia/urbanismo"
TRANSPARENCY_RSS = f"{TRANSPARENCY_URBANISMO}?format=feed&type=rss"
URBANISMO_PAGE = f"{WP_BASE}/areas-municipales/urbanismo-y-actividades/urbanismo"
LICENCIAS_PAGE = f"{URBANISMO_PAGE}/solicitudes-de-licencias"
DECLARACION_PAGE = f"{URBANISMO_PAGE}/declaracion-responsable-urbanistica-y-documentacion"
PGOU_PAGE = f"{URBANISMO_PAGE}/plan-general-de-ordenacion-urbana"
TABLON_WEB = f"{WP_BASE}/ayuntamiento/tablon-de-edictos"

DEFAULT_LICENCIA_PAGES: list[str] = [
    URBANISMO_PAGE,
    LICENCIAS_PAGE,
    DECLARACION_PAGE,
]

RE_TABLON_ID = re.compile(r'verAnuncio&id=([A-F0-9]+)"', re.I)
RE_TABLON_TITLE = re.compile(r'width="40%"[^>]*>\s*([^<]+)', re.I)
RE_TABLON_PERIOD = re.compile(r"Periodo:.*?(\d{2}/\d{2}/\d{4})", re.I | re.S)
RE_TRANSPARENCY_ARTICLE = re.compile(
    r'<a href="(/ayuntamiento/portal-de-transparencia/urbanismo/\d+-[^"]+)">\s*([^<]+)',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|vado|"
    r"ocupaci[oó]n de v[ií]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan |informaci[oó]n p[uú]blica|pgou|convenio|"
    r"expediente|edicto|reparcel|pleno|ordenanza|estudio de detalle|"
    r"aprobaci[oó]n (?:inicial|definitiva)|modificaci[oó]n|suelo|parcela|"
    r"urbanizaci[oó]n|actuaci[oó]n|iniciativa urban|proyecto de|"
    r"aa-\d+|ae-\d+|ed-\d+|ue-\d+|uueq)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?ayuntamientofuentelsaz\.com)?/images/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_URBAN_LINK = re.compile(
    r'href="((?:https?://(?:www\.)?ayuntamientofuentelsaz\.com)?/[^"]*(?:urbanismo|licencia|obra|planeam)[^"]*)"',
    re.I,
)


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


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<br\s*/?>", " ", text or "", flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _norm_key(key: str) -> str:
    t = (key or "").lower()
    for src, dst in (("ó", "o"), ("í", "i"), ("é", "e"), ("á", "a"), ("ú", "u"), ("ñ", "n")):
        t = t.replace(src, dst)
    return t


class FuenteElSazDeJaramaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla transparencia + sede add4u tablón + web trámites urbanismo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.fetch_detail = bool(self.config.get("fetch_tablon_detail", True))
        self.max_transparency_pages = int(self.config.get("max_transparency_pages", 8))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-fuente-el-saz/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        for enc in ("utf-8", "iso-8859-1", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WP_BASE}/", href)

    def _parse_tablon_listing(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TABLON_ID.finditer(html):
            anuncio_id = m.group(1)
            if anuncio_id in seen:
                continue
            seen.add(anuncio_id)
            chunk = html[m.start() : m.start() + 3000]
            title_m = RE_TABLON_TITLE.search(chunk)
            period_m = RE_TABLON_PERIOD.search(chunk)
            title = unescape(title_m.group(1).strip()) if title_m else ""
            title = re.sub(r"\s+", " ", title)
            fecha = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={anuncio_id}"
            rows.append(
                {
                    "anuncio_id": anuncio_id,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": url,
                }
            )
        return rows

    def _parse_detail_fields(self, html: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for m in re.finditer(r"<td[^>]*>([^<]+)</td>\s*<td[^>]*>([^<]*)", html, re.I):
            key = _norm_key(unescape(m.group(1).strip()))
            val = unescape(m.group(2).strip())
            if key:
                fields[key] = val
        return fields

    def _fetch_anuncio_detail(self, url: str) -> dict[str, str]:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return {}
        return self._parse_detail_fields(html)

    def _collect_tablon(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (TABLON_LIST, TABLON_HOME):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for row in self._parse_tablon_listing(html):
                if row["anuncio_id"] in seen:
                    continue
                seen.add(row["anuncio_id"])
                items.append(row)
        return items

    def _enrich_tablon_item(self, item: dict[str, Any]) -> dict[str, Any]:
        blob = item["titulo"]
        if not self.fetch_detail or not (
            RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob)
        ):
            return {**item, "blob": blob}
        detail = self._fetch_anuncio_detail(item["url"])
        desc = detail.get("descripcion") or ""
        contenido = detail.get("contenido") or ""
        fecha_ini = detail.get("fecha inicio publicacion") or ""
        grupo = detail.get("grupo") or ""
        titulo = desc or item["titulo"]
        fecha = _parse_fecha_dmy(fecha_ini) or item.get("fecha")
        blob = f"{titulo} {desc} {contenido} {grupo}"[:2000]
        return {
            **item,
            "titulo": titulo[:500] or item["titulo"],
            "fecha": fecha,
            "descripcion": desc,
            "contenido": contenido[:1000],
            "grupo": grupo,
            "blob": blob,
        }

    def _collect_rss_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            xml_text = self._fetch(TRANSPARENCY_RSS)
        except urllib.error.URLError:
            return rows
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return rows
        channel = root.find("channel")
        if channel is None:
            return rows
        for item in channel.findall("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = item.findtext("pubDate") or ""
            if not title or not link:
                continue
            rows.append(
                {
                    "titulo": unescape(title)[:500],
                    "fecha": _parse_rss_date(pub),
                    "url": link,
                    "source_kind": "rss",
                }
            )
        return rows

    def _collect_transparency_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for page_idx in range(self.max_transparency_pages):
            start = page_idx * 10
            url = TRANSPARENCY_URBANISMO if start == 0 else f"{TRANSPARENCY_URBANISMO}?start={start}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            found = 0
            for m in RE_TRANSPARENCY_ARTICLE.finditer(html):
                path = m.group(1)
                title = unescape(m.group(2).strip())
                title = re.sub(r"\s+", " ", title)
                full_url = self._abs_wp(path)
                if full_url in seen_urls:
                    continue
                seen_urls.add(full_url)
                found += 1
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": None,
                        "url": full_url,
                        "source_kind": "transparencia",
                    }
                )
            if found == 0:
                break
        return rows

    def _proyecto_tipo(self, blob: str) -> str:
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            return "información pública"
        if re.search(r"(?i)pleno", blob):
            return "acuerdo plenario"
        if re.search(r"(?i)convenio", blob):
            return "convenio"
        if re.search(r"(?i)reparcel", blob):
            return "reparcelación"
        if re.search(r"(?i)estudio de detalle", blob):
            return "estudio de detalle"
        if re.search(r"(?i)urbanizaci[oó]n", blob):
            return "proyecto de urbanización"
        if re.search(r"(?i)plan |planeam|pgou", blob):
            return "planeamiento"
        return "urbanismo"

    def _title_to_licencia(self, title: str, url: str, fecha: str | None) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(title):
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": fecha,
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "url": url,
            "source": "ayuntamiento",
        }

    def _title_to_proyecto(
        self,
        title: str,
        url: str,
        fecha: str | None,
        blob: str = "",
    ) -> dict[str, Any] | None:
        text = f"{title} {blob}"
        if RE_LICENCIA.search(text) and not RE_PROYECTO.search(text):
            return None
        if not RE_PROYECTO.search(text):
            return None
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": fecha,
            "tipo": self._proyecto_tipo(text),
            "url": url,
            "source": "ayuntamiento",
        }

    def _collect_licencias_informativas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        page_defs = [
            (URBANISMO_PAGE, "Urbanismo — trámites y normativa"),
            (LICENCIAS_PAGE, "Solicitudes de licencias de obra"),
            (DECLARACION_PAGE, "Declaración responsable urbanística"),
            (PGOU_PAGE, "Plan General de Ordenación Urbana"),
        ]
        for page_url, title in page_defs:
            rec_id = _stable_id("lic", page_url)
            if rec_id not in seen:
                seen.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title,
                        "url": page_url,
                        "source": "ayuntamiento",
                        "nota": "Página informativa; no concesión publicada en tablón",
                    }
                )
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                link = self._abs_wp(m.group(1))
                if link in seen:
                    continue
                fname = urllib.parse.unquote(link.rsplit("/", 1)[-1])
                if not RE_LICENCIA.search(fname):
                    continue
                rec_id = _stable_id("lic", link)
                if rec_id in seen:
                    continue
                seen.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "fecha_concesion": None,
                        "tipo": "formulario licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": fname.replace("_", " ").replace(".pdf", "")[:500],
                        "url": link,
                        "source": "ayuntamiento",
                        "nota": "Formulario PDF informativo",
                    }
                )
        return rows

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (r"<h1[^>]*>([^<]+)", r"<title>([^<]+)"):
            m = re.search(pat, html, re.I)
            if m:
                t = unescape(m.group(1).strip())
                t = re.sub(r"\s*[-|].*Ayuntamiento.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        tablon = self._collect_tablon()
        for item in tablon:
            enriched = self._enrich_tablon_item(item)
            blob = enriched.get("blob") or enriched["titulo"]
            add(self._title_to_licencia(blob, enriched["url"], enriched.get("fecha")))
        for rec in self._collect_licencias_informativas():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tablon": len(tablon)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        tablon = self._collect_tablon()
        for item in tablon:
            enriched = self._enrich_tablon_item(item)
            blob = enriched.get("blob") or enriched["titulo"]
            add(
                self._title_to_proyecto(
                    enriched["titulo"],
                    enriched["url"],
                    enriched.get("fecha"),
                    blob=blob,
                )
            )

        rss_items = self._collect_rss_proyectos()
        for item in rss_items:
            add(
                self._title_to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                )
            )

        transparency_items = self._collect_transparency_pages()
        for item in transparency_items:
            add(
                self._title_to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                )
            )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_items": len(tablon),
            "rss_items": len(rss_items),
            "transparency_items": len(transparency_items),
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
