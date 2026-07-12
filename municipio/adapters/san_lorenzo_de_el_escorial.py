from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://sede.aytosanlorenzo.es/eAdmin"
TRANSP_BASE = "https://transparencia.aytosanlorenzo.es"
TRANSP_PLANEAMIENTO = (
    f"{TRANSP_BASE}/urbanismo-y-obras-publicas/planeamiento/"
)
MUNICIPIO = "San Lorenzo de El Escorial"
ID_PREFIX = "san-lorenzo-de-el-escorial"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TRAMITES_URL = f"{SEDE_BASE}/Registrar.do?action=listadoEntradas"
WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"

DEFAULT_SEARCH_TERMS = (
    "URBANISMO",
    "LICENCIA",
    "INFORMACION PUBLICA",
    "PLAN",
    "PGOU",
    "NORMAS",
    "MODIFICACION",
    "APROBACION",
    "ORDEN DE EJECUCION",
)

DEFAULT_TRAMITE_IDS = (87, 111, 121, 128, 136, 143)

GEOM_HINTS: list[tuple[str, str]] = [
    ("las pozas", "Pozas"),
    ("pozas", "Pozas"),
    ("ue-11", "Cebadillas"),
    ("ue 11", "Cebadillas"),
    ("cebadillas", "Cebadillas"),
    ("ue-9", "Tercera"),
    ("ue 9", "Tercera"),
    ("la tercera", "Tercera"),
    ("santa clara", "Santa Clara"),
    ("apd-3", "Santa Clara"),
    ("apd 3", "Santa Clara"),
    ("pizarra", "Pizarra"),
    ("apd-9", "Pizarra"),
    ("colonia historica", "Colonia"),
    ("abantos", "Abantos"),
    ("romeral", "Romeral"),
]

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_EXPTE = re.compile(r"(?i)EXP\.?\s*([0-9]+/[0-9]{4})")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable.*obra|"
    r"comunicaci[oó]n previa|orden de ejecuci[oó]n|ordenanza.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|normas subsidi|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"orden de ejecuci|modificaci[oó]n|estudio (?:ac[uú]stico|ambiental)|ua-\d|ue-\d|apd|"
    r"proyecto de|iniciativa urban|evaluaci[oó]n edific|peri\b|bocm)",
)
RE_MODAL_TITLE = re.compile(
    r'id="modalInformacion(\d+)"[^>]*>.*?<h4[^>]*>([^<]+)',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOCM_DATE = re.compile(r"BOCM[_-]?(\d{4})[_-]?(\d{2})[_-]?(\d{2})", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"\s+", " ", text or "")).strip()
    if t.lower().startswith("ver documento"):
        t = t[len("ver documento") :].strip()
    return t[:500]


def _doc_url(sede_base: str, code: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(code, safe='')}&tipo=doc&mode=ori"
    )


def _pdf_url(token: str, sede_base: str) -> str:
    return _doc_url(sede_base, token)


def _proyecto_tipo(title: str, default: str = "urbanismo") -> str:
    n = title.lower()
    if "plan especial" in n or "peri" in n:
        return "plan especial"
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "plan parcial" in n or "pgou" in n or re.search(r"ua-\d|ue-\d", n):
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación puntual"
    if "aprobaci" in n:
        return "aprobación"
    if "normas subsidi" in n:
        return "normas subsidiarias"
    return default


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for feat in features:
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif gtype == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class SanLorenzoDeElEscorialAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede eAdmin (tablón + trámites) + transparencia WordPress (planeamiento)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.transp_planeamiento = str(
            self.config.get("transparencia_planeamiento") or TRANSP_PLANEAMIENTO
        )
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.tramite_ids = [int(x) for x in (self.config.get("tramite_ids") or DEFAULT_TRAMITE_IDS)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or "San Lorenzo")
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-san-lorenzo-de-el-escorial/1.0")
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "iso-8859-1"
            return raw.decode(charset, errors="replace")

    def _wfs_query(self, name_hint: str, max_features: int = 25) -> dict[str, Any] | None:
        if name_hint in self._geom_cache:
            cached = self._geom_cache[name_hint]
            return cached.copy() if cached else None
        esc = name_hint.replace("'", "''")
        cql = (
            f"DS_MUNICIPIO ILIKE '%{self.wfs_municipio}%' "
            f"AND DS_NOMB_AMB ILIKE '%{esc}%'"
        )
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": self.wfs_type,
            "outputFormat": "application/json",
            "count": str(max_features),
            "CQL_FILTER": cql,
        }
        url = f"{self.wfs_url}?{urllib.parse.urlencode(params)}"
        try:
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": self.config.get(
                        "user_agent", "poc-bocm-san-lorenzo-de-el-escorial/1.0"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._geom_cache[name_hint] = None
            return None
        geom = _merge_geometries(data.get("features") or [])
        if not geom:
            self._geom_cache[name_hint] = None
            return None
        result = {
            "geom_geojson": geom,
            "geometry_source": "cm_sit_wfs",
            "geometry_source_url": url,
            "coord_source": "portal_geometry_centroid",
        }
        self._geom_cache[name_hint] = result
        return result.copy()

    def _fetch_geometry(self, title: str, page_url: str = "") -> dict[str, Any]:
        blob = f"{title} {page_url}".lower()
        for needle, wfs_hint in GEOM_HINTS:
            if needle in blob:
                geom = self._wfs_query(wfs_hint)
                if geom:
                    return geom
        return {}

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        extra = self._fetch_geometry(
            str(rec.get("titulo") or ""),
            str(rec.get("url") or rec.get("origen") or ""),
        )
        if extra:
            rec.update(extra)
            centroid = geometry_centroid(extra["geom_geojson"])
            if centroid:
                rec["lat"], rec["lon"] = centroid

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
            fecha_fin = _parse_fecha_dmy(period_m.group(2)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "fecha_fin": fecha_fin,
                "url": detail_url,
                "doc_token": doc_token,
                "expte": _parse_expte(title),
            }
            if doc_token:
                rec["pdf_url"] = _pdf_url(doc_token, self.sede_base)
            by_id[ann_id] = rec
        return by_id

    def _search_tablon(self, term: str) -> dict[str, dict[str, Any]]:
        body = urllib.parse.urlencode({"referenciaBusqueda": term}).encode("utf-8")
        try:
            html = self._fetch(TABLON_ALL, data=body)
        except urllib.error.URLError:
            return {}
        return self._parse_tablon_html(html)

    def _collect_tablon(self) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(TABLON_ALL)
            by_id.update(self._parse_tablon_html(html))
        except urllib.error.URLError:
            pass
        for term in self.search_terms:
            for ann_id, rec in self._search_tablon(term).items():
                by_id.setdefault(ann_id, rec)
        return by_id

    def _collect_transparencia_proyectos(self) -> list[dict[str, Any]]:
        page_url = self.transp_planeamiento
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(title: str, url: str, section: str, default_tipo: str) -> None:
            title = _clean_title(title)
            if len(title) < 8 or not RE_PROYECTO.search(title):
                return
            key = f"{title}|{url}"
            if key in seen:
                return
            seen.add(key)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": title,
                "fecha": _parse_fecha_dmy(f"{title} {url}"),
                "tipo": _proyecto_tipo(title, default_tipo),
                "url": url,
                "source": "ayuntamiento",
                "origen": section,
            }
            if url.lower().endswith(".pdf") or "bocm.es" in url.lower():
                rec["pdf_url"] = url
            self._attach_geometry(rec)
            rows.append(rec)

        for m in re.finditer(r"<h4[^>]*>(.*?)</h4>(.*?)(?=<h4|$)", html, re.S | re.I):
            heading = _clean_title(re.sub(r"<[^>]+>", " ", m.group(1)))
            section = heading or "planeamiento"
            default_tipo = "planeamiento" if "plan" in section.lower() else "urbanismo"
            block = m.group(2)

            for li in re.finditer(r"<li[^>]*>(.*?)</li>", block, re.S | re.I):
                li_html = li.group(1)
                text = _clean_title(re.sub(r"<[^>]+>", " ", li_html))
                links = re.findall(r'href="([^"]+)"', li_html, re.I)
                url = links[0] if links else page_url
                if len(text) >= 8:
                    add(text, url, section, default_tipo)

            for href in re.findall(r'href="([^"]+)"', block, re.I):
                if not (
                    href.lower().endswith(".pdf")
                    or "bocm.es" in href.lower()
                    or "comunidad.madrid" in href.lower()
                ):
                    continue
                name = href.rsplit("/", 1)[-1]
                name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
                title = f"{heading}: {name}" if heading else name
                add(title, href, section, default_tipo)

        return rows

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRAMITES_URL)
        except urllib.error.URLError:
            return []
        titles: dict[str, str] = {}
        for m in RE_MODAL_TITLE.finditer(html):
            tid, title = m.group(1), _clean_title(m.group(2))
            if tid in {str(x) for x in self.tramite_ids}:
                titles[tid] = title
        rows: list[dict[str, Any]] = []
        for tid in self.tramite_ids:
            title = titles.get(str(tid))
            if not title:
                continue
            url = f"{self.sede_base}/Registrar.do?action=infoTramite&tipoReg={tid}"
            rows.append(
                {
                    "id": _stable_id("lic", f"tramite-{tid}"),
                    "fecha_concesion": None,
                    "tipo": title[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo sede; no concesión publicada",
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _title_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80}|orden de ejecuci[oó]n|ordenanza.*licencia)", title)
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

    def _title_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        out: dict[str, Any] = {
            "id": _stable_id("proy", rec.get("expte") or rec["ann_id"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": rec.get("fecha_ini"),
            "tipo": _proyecto_tipo(title),
            "url": rec["url"],
            "source": "ayuntamiento",
            "expte": rec.get("expte"),
            "origen": "tablon",
        }
        if rec.get("pdf_url"):
            out["pdf_url"] = rec["pdf_url"]
        self._attach_geometry(out)
        return out

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
        tablon = self._collect_tablon()
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in tablon.values():
            lic = self._title_to_licencia(rec)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        for rec in self._collect_tramites_urbanismo():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_items": len(tablon),
            "tramites": len(self.tramite_ids),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            lic = self._title_to_licencia(rec)
            if lic:
                existing[lic["id"]] = lic
        for rec in self._collect_tramites_urbanismo():
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

        for rec in self._collect_transparencia_proyectos():
            add(rec)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            add(self._title_to_proyecto(rec))

        self._write_jsonl(out_jsonl, rows)
        transp = sum(1 for r in rows if r.get("origen") != "tablon")
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia_docs": transp,
            "tablon_items": len(rows) - transp,
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
            "with_geometry": result.get("with_geometry", 0),
        }
