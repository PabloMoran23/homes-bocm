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
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import record_geometry

WEB_BASE = "https://ajuntamentbenissano.es"
WP_API = f"{WEB_BASE}/es/wp-json/wp/v2"
SEDE_BASE = "https://benissano.sede.dival.es"
TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URL = f"{SEDE_BASE}/catalogoservicios.aspx"
TRANSPARENCY_URL = f"{WEB_BASE}/es/portal-de-transparencia/urbanismo-y-obras-publicas/"
MUNICIPIO = "Benissanó"
ID_PREFIX = "benissano"
INE_COD_MUN = "46069"

DEFAULT_TRANSPARENCY_PDFS: tuple[str, ...] = (
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/0-bop-hhgg-03052005-original.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/1-bop-modificacion-15062006-nucleo-historico.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/2-bop-aclaraciones-modificaciones-29012007.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/3-pleno-extraordinario-28012010-ampliacion-usos-c-social.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/4-bop-ampliacion-usos-10032010-colegio-viejo.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/5-docv-ampliacion-usos-y-estudio-detalle-06-04-11-consultorio.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/hhgg-directrices-catalogo-y-fichas.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/hhgg-memoria-informativa.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/hhgg-memoria-justificativa.pdf",
    "https://ajuntamentbenissano.ayuntamientobenisano.es/wp-content/uploads/2019/04/hhgg-normas-urbanisticas.pdf",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|manipulaci[oó]n y comercializaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|urba)|pgou|pla especial|pla urba|convenio|"
    r"informaci[oó]n p[uú]blica|consulta (?:p[uú]blica|pr[eè]via)|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|dogv|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|cat[aà]leg|protecci[oó]|hhgg|normas subsidiarias|nn\.?ss|homologaci[oó]n|"
    r"antenas|vivienda.*tur[ií]stic|vut|sometimiento.*consultas)",
)
RE_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|calendario fiscal|recogida de (?:poda|voluminosos)|"
    r"paelleros|campanya salut|plan (?:de igualdad|local de (?:gesti[oó]n de )?residuos|colonias felinas)|"
    r"plan resistir|plan par[eé]ntesis|subvenci[oó]n.*bomberos|ordenanza.*contaminaci[oó]n ac[uú]stica|"
    r"covid|transporte p[uú]blico|reciclaje|ivace|fiestas|festival)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_WP_TITLE = re.compile(r"<[^>]+>")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _year_from_text(text: str) -> str | None:
    m = RE_YEAR.search(text or "")
    return m.group(1) if m else None


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "plan especial" in n or "pla especial" in n:
        return "plan especial"
    if "plan urba" in n or "puam" in n:
        return "plan urbanístico de actuación"
    if "modificaci" in n and ("norma" in n or "pgou" in n or "nn.ss" in n):
        return "modificación normas urbanísticas"
    if "consulta" in n:
        return "consulta pública"
    if "estudio de detalle" in n or "estudi de detall" in n:
        return "estudio de detalle"
    if "hhgg" in n or "históric" in n or "núcleo histórico" in n:
        return "planeamiento histórico"
    if "vivienda" in n and "turíst" in n:
        return "modificación planeamiento VUT"
    if "antenas" in n:
        return "modificación puntual antenas"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "licencia" in n or "llicència" in n:
        return "licencia publicada"
    return "urbanismo"


def _pdf_title_from_url(url: str) -> str:
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    name = re.sub(r"\.pdf.*$", "", name, flags=re.I)
    name = name.replace("-", " ").replace("_", " ")
    return name[:500]


class BenissanoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Bridge + sede Dival (tablón vacío) + transparencia PDFs."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.wp_api = str(self.config.get("wp_api") or WP_API).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        self.transparency_pdfs = tuple(self.config.get("transparency_pdfs") or DEFAULT_TRANSPARENCY_PDFS)

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-benissano/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 90) -> Any:
        return json.loads(self._fetch(url, timeout=timeout))

    def _abs_web(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.web_base}{href if href.startswith('/') else '/' + href}"

    def _abs_sede(self, href: str) -> str:
        href = unescape(href)
        if href.startswith("http"):
            return href
        return f"{self.sede_base}{href if href.startswith('/') else '/' + href}"

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
            return False
        return bool(RE_PROYECTO.search(blob) or RE_LICENCIA.search(blob))

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss, timeout=60)
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []

        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = datetime.strptime(
                        date_el.text.strip()[:25].strip(),
                        "%a, %d %b %Y %H:%M:%S",
                    ).strftime("%Y-%m-%d")
                except ValueError:
                    fecha = None
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": fecha,
                    "blob": title,
                    "origen": "tablon_rss",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = f"{self.wp_api}/posts?per_page=100&page={page}"
            try:
                posts = self._fetch_json(url, timeout=60)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(posts, list) or not posts:
                break
            for post in posts:
                title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                content = _strip_html(str((post.get("content") or {}).get("rendered") or ""))[:2000]
                blob = f"{title} {content}"
                if not self._is_urban_blob(blob):
                    continue
                fecha = str(post.get("date") or "")[:10] or None
                link = str(post.get("link") or "")
                if not title or not link:
                    continue
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": link,
                        "fecha": fecha,
                        "blob": blob,
                        "origen": "wordpress",
                    }
                )
            if len(posts) < 100:
                break
            page += 1
        return rows

    def _collect_transparency_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        pdf_urls = list(self.transparency_pdfs)
        try:
            html = self._fetch(self.transparency_url, timeout=60)
            for m in RE_PDF_HREF.finditer(html):
                pdf_urls.append(self._abs_web(m.group(1)))
        except urllib.error.URLError:
            pass

        for url in pdf_urls:
            if url in seen:
                continue
            seen.add(url)
            titulo = _pdf_title_from_url(url)
            year = _year_from_text(url) or _year_from_text(titulo)
            fecha = f"{year}-01-01" if year else None
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": fecha,
                    "blob": titulo,
                    "origen": "transparencia_pdf",
                    "pdf_url": url,
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tauler d'anuncis — sede electrónica Benissanó",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Tablón Dival vacío (ago 2026); licencias publicadas como edictos cuando existan",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.catalogo_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catàleg de tràmits — sede electrónica",
                "url": self.catalogo_url,
                "source": "ayuntamiento",
                "nota": "Sin trámites de licencia urbanística en línea; instancia general presencial/sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "urbanismo y obras públicas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo y obras públicas — portal transparencia",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "nota": "Normas subsidiarias y documentación PGOU en PDF",
                "origen": "transparencia",
            },
        ]

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or blob
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or blob
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for source in (
            self._collect_tablon_rss(),
            self._collect_wp_posts(),
            self._collect_transparency_pdfs(),
        ):
            for item in source:
                rec = self._row_to_licencia(item)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
            "wordpress": sum(1 for r in rows if r.get("origen") == "wordpress"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "transparencia")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for source in (
            self._collect_tablon_rss(),
            self._collect_wp_posts(),
            self._collect_transparency_pdfs(),
        ):
            for item in source:
                rec = self._row_to_licencia(item)
                if rec:
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

        for source in (
            self._collect_tablon_rss(),
            self._collect_wp_posts(),
            self._collect_transparency_pdfs(),
        ):
            for item in source:
                add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_rss"),
            "wordpress": sum(1 for r in rows if r.get("origen") == "wordpress"),
            "transparencia_pdf": sum(1 for r in rows if r.get("origen") == "transparencia_pdf"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": stats.get("with_geometry", 0),
        }
