from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://nijar.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "https://nijar.es"
URBANISMO_AREA_URL = f"{WEB_BASE}/ayuntamiento/areas/urbanismo-e-infraestructuras/"
URBANISMO_NEWS_URL = f"{WEB_BASE}/noticias/categoria/urbanismo/"
MUNICIPIO = "Níjar"
ID_PREFIX = "nijar"
COD_INE = "04066"

_WFS_CQL_INE = urllib.parse.quote(f"cod_ine='{COD_INE}'")
WFS_SECTORS_URL = (
    "https://app.dipalme.org/geoserver/urbanismo/ows?"
    "service=WFS&version=2.0.0&request=GetFeature&"
    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
    f"CQL_FILTER={_WFS_CQL_INE}&"
    "outputFormat=application/json&srsName=EPSG:4326"
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad|industria)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler|licencia municipal de apertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|pol[ií]gono|"
    r"cambio de uso|ordenanza|infraestructur|saneamiento|alumbrado|rehabilitaci[oó]n|"
    r"investigaci[oó]n titularidad|camino|urbanizaci[oó]n|puerto seco)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|cens[eo]|pleno|junta de gobierno|proceso selectivo|"
    r"agente de igualdad|psic[oó]logo|subvenci[oó]n)",
)
RE_BOARD_ROW = re.compile(r'<tr[^>]*>\s*<td class="class_name".*?</tr>', re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://nijar\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_ARTICLE = re.compile(r'href="(https://nijar\.es/noticias/[^"]+/)"', re.I)
RE_WP_TITLE = re.compile(r"<title>\s*([^<|]+?)\s*(?:\||-|–)\s*Ayuntamiento", re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_CODE = re.compile(
    r"(?i)\b(?:sector\s+)?((?:s|ue)[\-\s]?)?([a-z]{2,4})\s*[\-\s]?(\d+[a-z]?)\b"
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", " ", t.upper()).strip()


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(text or "")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "plan especial" in blob:
        return "plan especial"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "plan parcial" in blob or "sector" in blob:
        return "plan parcial"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "investigaci" in blob and "titularidad" in blob:
        return "investigación titularidad"
    if "licencia" in blob:
        return "licencia publicada"
    if "saneamiento" in blob or "alumbrado" in blob or "infraestructur" in blob:
        return "infraestructura urbana"
    if "rehabilitaci" in blob or "obra" in blob:
        return "obra pública"
    return "urbanismo"


class NijarAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona (tablón) + noticias WP urbanismo + WFS Diputación Almería (sectores)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_news_url = str(self.config.get("urbanismo_news_url") or URBANISMO_NEWS_URL)
        self.urbanismo_area_url = str(self.config.get("urbanismo_area_url") or URBANISMO_AREA_URL)
        self.cod_ine = str(self.config.get("cod_ine") or COD_INE)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._sector_cache: list[dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-nijar/1.0")},
        )
        if insecure is False:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-nijar/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90, context=self._ssl_ctx) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _collect_wp_urbanismo_news(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        article_urls: list[str] = []
        for page in range(1, 8):
            url = self.urbanismo_news_url if page == 1 else f"{self.urbanismo_news_url}page/{page}/"
            try:
                html = self._fetch(url, insecure=False)
            except urllib.error.URLError:
                break
            found = 0
            for m in RE_WP_ARTICLE.finditer(html):
                link = m.group(1)
                if "/categoria/" in link or "/page/" in link or link in seen_urls:
                    continue
                seen_urls.add(link)
                article_urls.append(link)
                found += 1
            if found == 0 and page > 1:
                break

        rows: list[dict[str, Any]] = []
        for link in article_urls:
            try:
                html = self._fetch(link, insecure=False)
            except urllib.error.URLError:
                continue
            tm = RE_WP_TITLE.search(html)
            titulo = _strip_html(tm.group(1)) if tm else link.rstrip("/").split("/")[-1].replace("-", " ")
            if not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(html[:8000]),
                    "url": link,
                    "procedimiento": "noticias urbanismo",
                    "blob": titulo,
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias de obra y actividad",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y licencias publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_area_url),
                "fecha_concesion": None,
                "tipo": "área urbanismo e infraestructuras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área de Urbanismo e Infraestructuras (web municipal)",
                "url": self.urbanismo_area_url,
                "source": "ayuntamiento",
                "nota": "Información y enlaces del área de urbanismo",
                "origen": "web_urbanismo",
            },
        ]

    def _load_sectors(self) -> list[dict[str, Any]]:
        if self._sector_cache is not None:
            return self._sector_cache
        rows: list[dict[str, Any]] = []
        wfs_url = str(self.config.get("wfs_sectors_url") or WFS_SECTORS_URL)
        try:
            data = self._fetch_json(wfs_url)
            for feat in data.get("features") or []:
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                sector = str(props.get("sector") or "").strip()
                if not sector or not isinstance(geom, dict):
                    continue
                rows.append(
                    {
                        "sector": sector,
                        "sector_norm": _norm_text(sector),
                        "geom": geom,
                    }
                )
        except (urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError):
            rows = []
        rows.sort(key=lambda r: len(r["sector_norm"]), reverse=True)
        self._sector_cache = rows
        return rows

    def _sector_codes_from_title(self, title: str) -> list[str]:
        codes: list[str] = []
        for m in RE_SECTOR_CODE.finditer(title or ""):
            prefix = (m.group(1) or "S").upper().replace("-", "").replace(" ", "")
            zone = m.group(2).upper()
            num = m.group(3).upper()
            codes.append(f"{prefix} {zone} {num}".replace("  ", " "))
            codes.append(f"S {zone} {num}")
        return codes

    def _fetch_geometry_for_title(self, title: str) -> dict[str, Any] | None:
        cache_key = _norm_text(title)
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        title_norm = _norm_text(title)
        title_codes = {_norm_text(c) for c in self._sector_codes_from_title(title)}
        result: dict[str, Any] | None = None
        for row in self._load_sectors():
            sector_norm = row["sector_norm"]
            if len(sector_norm) < 3:
                continue
            compact = sector_norm.replace(" ", "")
            title_compact = title_norm.replace(" ", "")
            if (
                sector_norm in title_norm
                or compact in title_compact
                or sector_norm in title_codes
                or re.search(rf"\b{re.escape(sector_norm)}\b", title_norm)
            ):
                geom = row["geom"]
                sector_escaped = row["sector"].replace("'", "''")
                cql = urllib.parse.quote(
                    f"cod_ine='{self.cod_ine}' AND sector='{sector_escaped}'"
                )
                query = (
                    "https://app.dipalme.org/geoserver/urbanismo/ows?"
                    "service=WFS&version=2.0.0&request=GetFeature&"
                    "typeName=urbanismo:v_siu_ambitos_o_sectores&"
                    f"CQL_FILTER={cql}&"
                    "count=1&outputFormat=application/json&srsName=EPSG:4326"
                )
                result = {
                    "geom_geojson": geom,
                    "geometry_source": "dipalme_wfs_sector",
                    "geometry_source_url": query,
                    "coord_source": "portal_geometry_centroid",
                    "sector_urbanistico": row["sector"],
                }
                centroid = geometry_centroid(geom)
                if centroid:
                    result["lat"], result["lon"] = centroid
                break
        self._geom_cache[cache_key] = result
        return result

    def _enrich_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        if record_geometry(rec):
            return rec
        geom_fields = self._fetch_geometry_for_title(rec.get("titulo") or "")
        if geom_fields:
            rec.update(geom_fields)
        return rec

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "información pública")):
            return True
        if "ordenanza" in cat or "urban" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc or "apertura" in blob.lower():
            tipo = "licencia de actividad"
        elif re.search(r"(?i)licencias urban", blob):
            tipo = "licencia urbanística"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _row_to_proyecto(self, row: dict[str, Any], origen: str) -> dict[str, Any]:
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{origen}:{key}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": origen,
        }
        return self._enrich_geometry(rec)

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "información pública" not in proc:
            return None
        return self._row_to_proyecto(row, "tablon")

    def _news_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        return self._row_to_proyecto(row, "noticias_urbanismo")

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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") != "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_wp_urbanismo_news():
            add(self._news_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "noticias": sum(1 for r in rows if r.get("origen") == "noticias_urbanismo"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
