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

WEB_BASE = "https://www.lorca.es"
SEDE_BASE = "https://www.portalciudadano.lorca.es"
URBANISMO_BASE = "https://urbanismo.lorca.es"
MUNICIPIO = "Lorca"
ID_PREFIX = "lorca"
COD_INE = "30024"

TABLON_URL = f"{SEDE_BASE}/web/guest/tablon-de-anuncios"
CATALOGO_URL = f"{SEDE_BASE}/web/guest/catalogo-de-servicios"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27Lorca%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

DEFAULT_URBANISMO_SEEDS = (
    f"{URBANISMO_BASE}/planGeneral.asp",
    f"{URBANISMO_BASE}/planParcial.asp",
    f"{URBANISMO_BASE}/planEspecial.asp",
    f"{URBANISMO_BASE}/acuerdos.asp",
)

CATALOGO_LICENCIA_PATHS = (
    "/catalogo/USTREC/",
    "/catalogo/URMPGM/",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|recepciones? de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|pepri|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|normativa urban|evaluaci[oó]n ambiental|"
    r"delimitaci[oó]n|urbanizaci[oó]n|ficha ua|mpgmo|urconv|urmpgm)",
)
RE_TABLON_SKIP = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"jurado del municipio|subvenci[oó]n de transporte|ayudas leader|"
    r"responsabilidad patrimonial|empleo p[uú]blico|estudiantes lorquinos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_TIME = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+\d{1,2}:\d{2}")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(
    r"(?i)\b(?:expediente|expte\.?|mpgmo|urconv|urmpgm)[:\s]*([0-9]{4}/[A-Z0-9-]+|[0-9]{2,4}/[0-9]{2,4}/[A-Z]+|"
    r"MOD(?:IFICACI[OÓ]N)?\s*(?:N[ºo°.]?\s*)?\d+)",
)
RE_AMBITO = re.compile(r"(?i)\b(UA-\d{1,3}|S\.?I\.?D\.?U\.?-\d+|SECTOR\s+\d+[-\s]?[A-Z]?|SGEL)\b")
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]*)', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY_TIME, RE_FECHA_DMY):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_ambito(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"\s+", "-", code)
    code = code.replace("SECTOR-", "SECTOR ")
    m = re.search(r"UA-?\s*(\d+)", code)
    if m:
        return f"UA-{m.group(1)}"
    return code


def _ambito_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_AMBITO.finditer(text or ""):
        code = _normalize_ambito(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "convenio" in b:
        return "convenio urbanístico"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "plan parcial" in b or "pp " in b:
        return "plan parcial"
    if "plan especial" in b or "pepri" in b:
        return "plan especial"
    if "pgmo" in b or "pgou" in b or "plan general" in b:
        return "PGMO"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class LorcaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay sede (tablón) + urbanismo.lorca.es (PGMO/PEPRI PDFs) + SITMURCIA WFS (geometría parcial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.urbanismo_base = str(self.config.get("urbanismo_base") or URBANISMO_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.urbanismo_seeds = [str(u) for u in (self.config.get("urbanismo_seeds") or DEFAULT_URBANISMO_SEEDS)]
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, latin1: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-lorca/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
        if latin1:
            return raw.decode("latin-1", errors="replace")
        return raw.decode("utf-8", errors="replace")

    def _abs_sede(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", unescape(href))

    def _abs_urbanismo(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.urbanismo_base}/", unescape(href))

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

    def _parse_tablon_page(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.I | re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.I | re.S)
            if len(cells) < 3:
                continue
            title = _strip_html(cells[0])
            desc = _strip_html(cells[1]) if len(cells) > 1 else ""
            fecha_raw = _strip_html(cells[-1])
            if not title or title == "Título":
                continue
            link_m = re.search(r'href="(/tablon-de-anuncios/anuncio/\d+/)', tr)
            url = self._abs_sede(link_m.group(1)) if link_m else self.tablon_url
            blob = f"{title} {desc}"
            rows.append(
                {
                    "titulo": title[:500],
                    "descripcion": desc[:800] if desc else None,
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "origen": "tablon_sede",
                    "blob": blob,
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        out: list[dict[str, Any]] = []
        url = self.tablon_url
        for _ in range(40):
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            page_rows = self._parse_tablon_page(html)
            if not page_rows:
                break
            new = 0
            for row in page_rows:
                if row["url"] in seen_urls:
                    continue
                seen_urls.add(row["url"])
                out.append(row)
                new += 1
            if new == 0:
                break
            m = re.search(r'href="(\?page=\d+[^"]*)"[^>]*>\s*siguiente', html, re.I)
            if not m:
                break
            url = urllib.parse.urljoin(url, unescape(m.group(1)))
        return out

    def _collect_urbanismo_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.urbanismo_seeds:
            try:
                html = self._fetch(seed, latin1=True)
            except urllib.error.URLError:
                continue
            for href, title in RE_LINK.findall(html):
                titulo = _strip_html(title)
                if len(titulo) < 4:
                    continue
                blob = f"{titulo} {href}"
                if not RE_PROYECTO.search(blob) and not href.lower().endswith(".pdf"):
                    continue
                if re.search(r"(organigrama|estatutos|privacidad)", blob, re.I):
                    continue
                url = self._abs_urbanismo(href)
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": titulo[:500] or _strip_html(Path(href).name),
                        "fecha": _fecha_from_blob(blob),
                        "url": url,
                        "origen": "urbanismo_web",
                        "blob": blob,
                    }
                )
        return rows

    def _collect_catalogo_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for href, title in RE_LINK.findall(html):
            path = unescape(href)
            if not any(path.startswith(p) for p in CATALOGO_LICENCIA_PATHS):
                continue
            titulo = _strip_html(title)
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": None,
                    "url": self._abs_sede(path),
                    "origen": "catalogo_sede",
                    "blob": titulo,
                    "es_licencia": True,
                }
            )
        return rows

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        try:
            data = json.loads(self._fetch(self.wfs_url))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = index
            return index
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            ambito = _normalize_ambito(str(props.get("Ambito") or ""))
            geom = feat.get("geometry")
            if not ambito or not isinstance(geom, dict):
                continue
            rec = {
                "geom_geojson": geom,
                "geometry_crs": "EPSG:4326",
                "geometry_axis_order": "xy",
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": ambito,
                "clasificacion": props.get("Clasificacion"),
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            index[ambito] = rec
        self._wfs_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "blob", "expte"))
        index = self._build_wfs_index()
        for code in _ambito_codes_from_text(blob):
            hit = index.get(code)
            if not hit:
                continue
            for key in (
                "geom_geojson",
                "geometry_source",
                "geometry_source_url",
                "coord_source",
                "lat",
                "lon",
                "ambito",
                "clasificacion",
            ):
                if hit.get(key) is not None:
                    rec[key] = hit[key]
            return

    def _to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if RE_TABLON_SKIP.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or self.urbanismo_base)
        expte_m = RE_EXPEDIENTE.search(blob)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": raw.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        if expte_m:
            rec["expte"] = expte_m.group(1).strip()
        if raw.get("descripcion"):
            rec["descripcion"] = raw["descripcion"]
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if raw.get("es_licencia"):
            pass
        elif not RE_LICENCIA.search(blob):
            return None
        if RE_TABLON_SKIP.search(blob):
            return None
        titulo = str(raw.get("titulo") or "")[:500]
        url = str(raw.get("url") or self.catalogo_url)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": raw.get("fecha") or _fecha_from_blob(blob) or "1970-01-01",
            "tipo": titulo[:200],
            "distrito": MUNICIPIO,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
            "url": url,
        }
        self._attach_geometry(rec)
        if rec.get("lat") is None or rec.get("lon") is None:
            centroid = self.config.get("centroid") or [37.6712, -1.7017]
            rec["lat"], rec["lon"] = float(centroid[0]), float(centroid[1])
            rec["coord_source"] = "municipio_centroid"
        rec["coordinates_crs"] = "EPSG:4326"
        return rec

    def _collect_proyecto_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for src in self._collect_tablon(), self._collect_urbanismo_docs():
            for raw in src:
                rec = self._to_proyecto(raw)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        return rows

    def _collect_licencia_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        sources = list(self._collect_tablon()) + list(self._collect_catalogo_tramites())
        for raw in sources:
            rec = self._to_licencia(raw)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_sede"),
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
        return {**stats, "added": max(0, after - before)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyecto_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "urbanismo": sum(1 for r in rows if r.get("origen") == "urbanismo_web"),
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
        return {**stats, "added": max(0, after - before)}
