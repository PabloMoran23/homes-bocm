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
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import _merge_geometries, resolve_ambito_geometry

JOOMLA_BASE = "https://www.villamantilla.org"
SEDE_BASE = "https://villamantilla.sedelectronica.es"
MUNICIPIO = "Villamantilla"
ID_PREFIX = "villamantilla"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VILLAMANTILLA"

URBANISMO_URL = f"{JOOMLA_BASE}/normativa/urbanismo"
TABLON_URL = f"{JOOMLA_BASE}/inicio/tablon-municipal"
TRAMITES_URL = f"{JOOMLA_BASE}/tramites"
BOARD_URL = f"{SEDE_BASE}/board/"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
VISOR_URL = "http://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=175"

URBANISMO_RSS = f"{URBANISMO_URL}?format=feed&type=rss"
TABLON_RSS = f"{TABLON_URL}?format=feed&type=rss"

RE_PREVIEW = re.compile(
    r'href="(https://villamantilla\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|vado|parcelaci[oó]n|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|bando|edicto|exposici[oó]n p[uú]blica|reasfalt|embellecimiento viario|"
    r"parcela|suelo|urbaniz|licitaci[oó]n.*(?:obra|viario|urban)|"
    r"\b(?:UE|UA|AD|AN|AI|PAU|SAU|S)-\d+\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|plusvalia|basura|"
    r"residuos s[oó]lidos urbanos|vehiculos|igualdad|iae\b|cobranza|ibi\b|"
    r"incendio|fuegos artificiales|fiestas|huertos sociales|empleo|pleno|"
    r"convocatoria.*sesi[oó]n|calendario fiscal|orden de la consejera)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.)?villamantilla\.org)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_TABLON_LINK = re.compile(
    r'href="(/inicio/tablon-municipal/\d+-[^"#?]+)"[^>]*>\s*([^<]+?)\s*</a>',
    re.I | re.S,
)


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "reasfalt" in n or "embellecimiento viario" in n:
        return "obra viaria"
    if "bando" in n and "parcel" in n:
        return "bando municipal"
    if "exposici" in n:
        return "exposición pública"
    if re.search(r"\bsau-\d+\b", n):
        return "suelo urbanizable"
    if re.search(r"\bue-\d+\b", n):
        return "unidad de ejecución"
    if "licitaci" in n:
        return "licitación obra"
    return "urbanismo"


class VillamantillaAyuntamientoAdapter(AyuntamientoAdapter):
    """Joomla Helix Ultimate + icagenda tablón + sede espublico + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or JOOMLA_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        self.max_tablon_pages = int(self.config.get("max_tablon_pages", 10))
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)

    def _fetch(self, url: str, timeout: float = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villamantilla/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_joomla(self, href: str) -> str:
        return urllib.parse.urljoin(f"{JOOMLA_BASE}/", unescape(href))

    def _parse_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            preview_m = RE_PREVIEW.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()

            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "descripcion": descripcion[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {titulo}"
                    ),
                    "origen": "sede_board",
                }
            )

        if not rows:
            for m in RE_PREVIEW.finditer(html):
                url = m.group(1)
                local = html[max(0, m.start() - 400) : m.end() + 200]
                title_m = re.search(r'title="([^"]*)"', local, re.I)
                titulo = unescape(title_m.group(1).strip()) if title_m else url
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": "",
                        "procedimiento": "",
                        "categoria": "",
                        "descripcion": titulo,
                        "fecha": _fecha_from_blob(titulo),
                        "url": url,
                        "blob": titulo,
                        "origen": "sede_board",
                    }
                )
        return rows

    def _parse_rss(self, rss_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(rss_url, timeout=30)
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return []

        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
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
                    "origen": origen,
                }
            )
        return rows

    def _parse_tablon_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(self.max_tablon_pages):
            url = self.tablon_url if page == 0 else f"{self.tablon_url}?start={page * 10}"
            try:
                html = self._fetch(url, timeout=30)
            except urllib.error.URLError:
                break
            found = 0
            for m in RE_TABLON_LINK.finditer(html):
                path, title = m.group(1), unescape(_strip_html(m.group(2)))
                if not title or path in seen:
                    continue
                seen.add(path)
                found += 1
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(title),
                        "url": self._abs_joomla(path),
                        "origen": "joomla_tablon",
                    }
                )
            if found == 0 and page > 0:
                break
        return rows

    def _collect_tramite_forms(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramites_url, timeout=30)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_joomla(m.group(1))
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(Path(urllib.parse.unquote(pdf)).stem.replace("_", " ").replace("-", " "))
            if not RE_LICENCIA.search(name):
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "fecha": _fecha_from_blob(pdf + " " + name),
                    "url": self.tramites_url,
                    "pdf_url": pdf,
                    "origen": "formulario_web",
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(titulo or ""):
            return None
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if not geom:
            return None
        name = str(meta.get("ambito_name") or "")
        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
        ) if name else ""
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                if cql
                else self.wfs_url
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": name or None,
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y exposiciones públicas (espublico gestiona)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "normativa urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Normativa — Urbanismo",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Sección urbanismo en web municipal Joomla",
                "origen": "joomla_urbanismo",
            },
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "formularios licencia y obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites — solicitud de licencia de obra",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Formulario PDF; concesiones individuales en tablón cuando se publiquen",
                "origen": "formulario_web",
            },
            {
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "portal transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia — Urbanismo, obras públicas y medio ambiente",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "nota": "Sección 7 en sede espublico",
                "origen": "transparencia",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "trámites sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo en sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias, declaraciones responsables, cédula urbanística",
                "origen": "sede_tramite",
            },
        ]

    def _form_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        return {
            "id": _stable_id("lic", row.get("pdf_url") or row["titulo"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "formulario licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("url") or self.tramites_url,
            "source": "ayuntamiento",
            "nota": "Formulario de solicitud; no concesión publicada",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row["titulo"]
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row["titulo"]
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _item_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row["titulo"]
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"] + "|" + row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
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
        for item in self._collect_tramite_forms():
            rec = self._form_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._parse_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(
                1
                for r in rows
                if r.get("origen")
                in ("sede_tablon", "joomla_urbanismo", "transparencia", "sede_tramite", "formulario_web")
            ),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tramite_forms():
            rec = self._form_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._parse_board():
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

        for item in self._parse_rss(URBANISMO_RSS, "joomla_rss_urbanismo"):
            add(self._item_to_proyecto(item))
        for item in self._parse_rss(self.tablon_rss, "joomla_rss_tablon"):
            add(self._item_to_proyecto(item))
        for item in self._parse_tablon_pages():
            add(self._item_to_proyecto(item))
        for item in self._parse_board():
            add(self._board_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("joomla")),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
