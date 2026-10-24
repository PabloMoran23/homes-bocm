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

WEB_BASE = "https://motril.es"
SEDE_BASE = "https://sede.motril.es"
MUNICIPIO = "Motril"
ID_PREFIX = "motril"

TABLON_URBAN_KEY = "3223500033794117807831"
TABLON_URBAN_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?"
    f"APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY={TABLON_URBAN_KEY}"
)
TABLON_ALL_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
CATSERV_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV"
SITUA_URL = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=18087"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/urbanismo/informacion-publica/",
    f"{WEB_BASE}/urbanismo/consulta-publica/",
    f"{WEB_BASE}/urbanismo/planeamiento/",
    f"{WEB_BASE}/urbanismo/plan-general-de-ordenacion-urbanistica/modificaciones/",
    f"{WEB_BASE}/urbanismo/plan-general-de-ordenacion-urbanistica/participacion-publica/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|primera ocupaci[oó]n|puesta en funcionamiento|"
    r"licencia de (?:obra|actividad|apertura)|divisi[oó]n horizontal)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|consulta p[uú]blica|exposici[oó]n p[uú]blica|"
    r"expediente|proyecto|modificaci[oó]n|reparcel|estudio (?:de detalle|ac[uú]stico)|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|ordenanza (?:urban|fiscal)|"
    r"parcela|suelo|sector|actuaci[oó]n|memoria|planos|edicto|urbanizaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(sesi[oó]n de jgl|junta de gobierno local|selecci[oó]n de personal|"
    r"nombramiento|convocatoria.*empleo|subvenci[oó]n deportiv|padrones|"
    r"mercado municipal|licitaci[oó]n|puesto.*mercado|ofertas econ[oó]micas)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_FECHA_PATH = re.compile(r"/(20\d{2})/(\d{2})/")
RE_DOC_HREF = re.compile(
    r'<a[^>]+href=["\']([^"\']+\.(?:pdf|zip)(?:\?[^"\']*)?)["\'][^>]*>([^<]{3,400})</a>',
    re.I | re.S,
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


def _fecha_from_text(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_PATH.search(url or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        y, mo, d = int(obj["year"]), int(obj["month"]), int(obj["day"])
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "plan parcial" in n:
        return "plan parcial"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "proyecto de urbaniz" in n:
        return "proyecto de urbanización"
    if "ordenanza" in n:
        return "ordenanza"
    if "convenio" in n:
        return "convenio urbanístico"
    if "memoria" in n:
        return "memoria planeamiento"
    return "urbanismo"


class MotrilAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress motril.es (PDFs IP/PGOU) + sede STA T-Systems (tablón + catálogo trámites)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.fetch_timeout = int(self.config.get("fetch_timeout_s", 120))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-motril/1.0")},
        )
        ctx = self._ssl_ctx if use_sede_ssl or "sede.motril.es" in url else None
        with urllib.request.urlopen(req, timeout=self.fetch_timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_CATSERV"
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        by_dboid: dict[str, dict[str, Any]] = {}
        for tablon_url in (TABLON_URBAN_URL, TABLON_ALL_URL):
            try:
                html = self._fetch(tablon_url, use_sede_ssl=True)
            except urllib.error.URLError:
                continue
            for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
                dboid = str(item.get("dboid") or "")
                titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
                if not titulo or not dboid:
                    continue
                rem = item.get("remitent") or {}
                by_dboid[dboid] = {
                    "titulo": titulo,
                    "fecha": _xml_date(item.get("pubDateIni")),
                    "expte": str(item.get("externString") or "").strip() or None,
                    "remitente": str(rem.get("description") or ""),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "origen": "tablon_sta",
                }
        return list(by_dboid.values())

    def _collect_catalog(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATSERV_URL, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            name = _clean_title(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or item.get("code") or "")
            if not name or not dboid:
                continue
            blob = name
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _abs_web(self, href: str, page_url: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(page_url, href)

    def _collect_wp_pdfs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_DOC_HREF.finditer(html):
                href = self._abs_web(m.group(1), page_url)
                if href in seen:
                    continue
                title = _strip_html(m.group(2)) or Path(urllib.parse.unquote(href)).name
                blob = f"{title} {href}"
                seen.add(href)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_text(blob, href),
                        "url": href,
                        "page_url": page_url,
                        "blob": blob,
                        "origen": "web_wp_pdf",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TABLON_URBAN_URL),
                "fecha_concesion": None,
                "tipo": "tablón información pública urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón sede — información pública (urbanismo)",
                "url": TABLON_URBAN_URL,
                "source": "ayuntamiento",
                "nota": "Anuncios de información pública y expedientes urbanísticos (STA KEY urbanismo)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", CATSERV_URL),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — licencias y obras",
                "url": CATSERV_URL,
                "source": "ayuntamiento",
                "nota": "Declaraciones responsables, comunicaciones previas y licencias vía sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.web_base}/solicitud-obra-menor/"),
                "fecha_concesion": None,
                "tipo": "trámite obra menor",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitud de obra menor — web municipal",
                "url": f"{self.web_base}/solicitud-obra-menor/",
                "source": "ayuntamiento",
                "nota": "Formulario informativo; sin listado histórico de concesiones",
                "origen": "web_tramite",
            },
        ]

    def _is_urban_blob(self, blob: str) -> bool:
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('remitente') or ''}"
        if not self._is_urban_blob(blob) or not RE_LICENCIA.search(blob):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expte"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sta",
        }

    def _catalog_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["dboid"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "catalogo_tramites",
        }

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('remitente') or ''}"
        if not self._is_urban_blob(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "expte": row.get("expte"),
            "source": "ayuntamiento",
            "origen": "tablon_sta",
        }

    def _catalog_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["dboid"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "catalogo_tramites",
        }

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        return {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _wp_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "documento licencia / obra",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_catalog():
            rec = self._catalog_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_wp_pdfs():
            rec = self._wp_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_catalog():
            rec = self._catalog_to_licencia(item)
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

        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_catalog():
            add(self._catalog_to_proyecto(item))
        for item in self._collect_wp_pdfs():
            add(self._wp_to_proyecto(item))

        add(
            {
                "id": _stable_id("proy", f"{self.web_base}/urbanismo/informacion-publica/"),
                "municipio": MUNICIPIO,
                "titulo": "Información pública urbanística — índice web",
                "fecha": None,
                "tipo": "información pública",
                "url": f"{self.web_base}/urbanismo/informacion-publica/",
                "source": "ayuntamiento",
                "origen": "web_indice",
            }
        )
        add(
            {
                "id": _stable_id("proy", SITUA_URL),
                "municipio": MUNICIPIO,
                "titulo": "PGOU Motril — consulta SITUA (Junta de Andalucía)",
                "fecha": None,
                "tipo": "PGOU",
                "url": SITUA_URL,
                "source": "ayuntamiento",
                "origen": "situa",
                "nota": "Visor regional de planeamiento digitalizado (INE 18087); sin WFS por expediente",
            }
        )

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "web_wp_pdf": sum(1 for r in rows if r.get("origen") == "web_wp_pdf"),
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
