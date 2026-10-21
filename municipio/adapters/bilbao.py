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
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.bilbao.eus"
MUNICIPIO = "Bilbao"
ID_PREFIX = "bilbao"

LICITACIONES_API = f"{BASE}/opendata/datos/licitaciones"
CONVENIOS_API = (
    f"{BASE}/cs/Satellite?c=Page&language=es&pageid=1272976790212"
    "&pagename=Bilbaonet/Page/OD_ListadoConvenios"
)
URBANISMO_RSS = (
    f"{BASE}/cs/Satellite?language=es&pageid=3000075248"
    "&pagename=Bilbaonet/Page/BIO_suscripcionRSS&tipoSus=Noticias&idSec=3000003788"
)

ARCGIS_MAP = (
    "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/"
    "LurraldeAntolamendua_PlanificacionTerritorial/PX_Bilbao_Metropolitano_inf/MapServer"
)
PLANEAMIENTO_LAYER_IDS = (119, 120, 121, 122, 134)

DEFAULT_TRAMITE_LICENCIA: list[tuple[str, str]] = [
    (
        (
            f"{BASE}/cs/Satellite?anclaServ=aB3&c=BIO_Procedimiento_FA&categoria=municipales"
            "&language=es&pageid=1279126910314&pagename=Bilbaonet%2FBIO_Procedimiento_FA%2FBIO_ProcResumen"
            "&perfil=ciudadano&rutaCatServ=3002269359%2C1279189514568&selec=1"
        ),
        "Licencias o autorizaciones para obras mayores",
    ),
    (
        (
            f"{BASE}/cs/Satellite?c=BIO_Tramite_FA&categoria=a&idProc=1279198449765&language=es"
            "&pageid=1279198292568&pagename=Bilbaonet%2FBIO_Tramite_FA%2FBIO_TramiteSrvTram&perfil=ciudadano"
        ),
        "Licencia de obras menores (procedimiento ordinario)",
    ),
    (
        (
            f"{BASE}/cs/Satellite?c=BIO_Procedimiento_FA&language=es&pageid=3000094370"
            "&pagename=Bilbaonet%2FBIO_Procedimiento_FA%2FBIO_Procedimiento&rutaCatServ=3003445620"
        ),
        "Consultas urbanísticas sobre planeamiento vigente y en trámite",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|obra(s)?\s+menor|obra(s)?\s+mayor|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"modificaci[oó]n|ordenaci[oó]n|reparcel|urbanizaci[oó]n|instrumento|"
    r"unidad de (?:ejecuci[oó]n|actuaci[oó]n)|pgou)",
)
RE_FECHA_DMY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{5,}")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha(text: str | None) -> str | None:
    if not text:
        return None
    m = RE_FECHA_ISO.search(text)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = RE_FECHA_DMY_SLASH.search(text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            return None
    return None


def _tipo_proyecto(blob: str) -> str:
    b = (blob or "").lower()
    if "convenio urban" in b:
        return "convenio urbanístico"
    if "modificaci" in b and "pgou" in b:
        return "modificación PGOU"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan especial" in b:
        return "plan especial"
    if "plan parcial" in b:
        return "plan parcial"
    if "urbanizaci" in b:
        return "urbanización"
    if "concurso de proyectos" in b or "ordenaci" in b:
        return "ordenación urbanística"
    if re.search(r"licitaci|contrat", b):
        return "contratación urbanística"
    return "planeamiento / urbanismo"


class BilbaoAyuntamientoAdapter(AyuntamientoAdapter):
    """Open Data Bilbao (licitaciones, convenios, RSS urbanismo) + trámites licencia."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.licitacion_years = [int(y) for y in (self.config.get("licitacion_years") or [2023, 2024, 2025])]
        self.convenio_years = [int(y) for y in (self.config.get("convenio_years") or [2023, 2024])]
        raw_tramites = self.config.get("tramite_licencia")
        if isinstance(raw_tramites, list) and raw_tramites:
            self.tramite_licencia = [(str(t[0]), str(t[1])) for t in raw_tramites if len(t) >= 2]
        else:
            self.tramite_licencia = list(DEFAULT_TRAMITE_LICENCIA)
        self.arcgis_map = str(self.config.get("arcgis_map_url") or ARCGIS_MAP)
        self.planeamiento_layers = tuple(
            int(x) for x in (self.config.get("planeamiento_layer_ids") or PLANEAMIENTO_LAYER_IDS)
        )
        self.geometry_enrich = bool(self.config.get("geometry_enrich", True))
        self.geometry_max_rows = int(self.config.get("geometry_max_rows", 12))
        self._geometry_attempts = 0

    def _fetch(self, url: str, *, data: bytes | None = None) -> bytes:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-bilbao/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read()

    def _fetch_text(self, url: str) -> str:
        return self._fetch(url).decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
            r"<title>([^<]+)",
            r'class="[^"]*c-page-title[^"]*"[^>]*>([^<]+)',
            r"<h2[^>]*>([^<]+)",
            r"<h1[^>]*>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                return _strip_html(m.group(1))[:500]
        return fallback

    def _geom_search_tokens(self, text: str) -> list[str]:
        stop = {
            "bilbao",
            "ayuntamiento",
            "municipio",
            "modificacion",
            "planeamiento",
            "urbanismo",
            "proyecto",
            "obras",
            "servicio",
            "contrato",
            "convenio",
        }
        seen: set[str] = set()
        out: list[str] = []
        for m in RE_TOKEN.finditer(text or ""):
            w = m.group(0)
            key = w.lower()
            if key in stop or len(key) < 5:
                continue
            if key not in seen:
                seen.add(key)
                out.append(w)
        return out[:4]

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if self._geometry_attempts >= self.geometry_max_rows:
            return None
        self._geometry_attempts += 1
        for token in self._geom_search_tokens(titulo):
            esc = token.replace("'", "''")
            where = f"(ETIQUETA LIKE '%{esc}%' OR DESCRIPCION LIKE '%{esc}%')"
            for layer_id in self.planeamiento_layers:
                params = {
                    "where": where,
                    "outFields": "ETIQUETA,DESCRIPCION",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "geojson",
                    "resultRecordCount": "1",
                }
                url = f"{self.arcgis_map}/{layer_id}/query?{urllib.parse.urlencode(params)}"
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                    continue
                feats = data.get("features") if isinstance(data, dict) else None
                if not feats:
                    continue
                geom = feats[0].get("geometry") if isinstance(feats[0], dict) else None
                if not isinstance(geom, dict) or not geom.get("type"):
                    continue
                return {
                    "geom_geojson": geom,
                    "geometry_source": "portal_visor_arcgis",
                    "geometry_source_url": url,
                    "coord_source": "portal_geometry_centroid",
                }
        return None

    def _attach_geometry(self, rec: dict[str, Any], *, enabled: bool = True) -> None:
        if not enabled or record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec["lat"], rec["lon"] = cen

    def _licitaciones_urbanas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for year in self.licitacion_years:
            url = (
                f"{LICITACIONES_API}?formato=json&anio={year}&idioma=es"
            )
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                continue
            for item in data.get("licitaciones") or []:
                if not isinstance(item, dict):
                    continue
                objeto = _strip_html(str(item.get("Objeto") or ""))
                area = str(item.get("Area_Municipal_promotora_del_Expediente") or "")
                blob = f"{objeto} {area}"
                if not RE_PROYECTO.search(blob):
                    continue
                exp = str(item.get("N_Expediente") or "").strip()
                lote = str(item.get("Lote") or "1").strip()
                key = f"licit-{year}-{exp}-{lote}"
                if key in seen:
                    continue
                seen.add(key)
                fecha = _parse_fecha(str(item.get("Fecha_de_adjudicacion") or "")) or f"{year}-01-01"
                titulo = objeto[:500] if objeto else f"Contrato urbanístico {exp}"
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": fecha,
                    "tipo": _tipo_proyecto(blob),
                    "url": f"{LICITACIONES_API}?formato=json&anio={year}&idioma=es",
                    "source": "ayuntamiento",
                    "expediente": exp,
                    "origen": "opendata_licitaciones",
                }
                self._attach_geometry(rec, enabled=self.geometry_enrich)
                rows.append(rec)
        return rows

    def _convenios_urbanisticos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for year in self.convenio_years:
            url = f"{CONVENIOS_API}&anio={year}&formato=JSON"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                continue
            for item in data.get("convenios") or []:
                if not isinstance(item, dict):
                    continue
                titulo = _strip_html(str(item.get("titulo") or ""))
                tipo_conv = str(item.get("tipoconvenio") or "")
                blob = f"{titulo} {tipo_conv} {_strip_html(str(item.get('ampliatoria') or ''))}"
                if not RE_PROYECTO.search(blob):
                    continue
                exp = str(item.get("numeroexpediente") or item.get("numeroinscripcion") or titulo[:40])
                key = f"conv-{year}-{exp}"
                if key in seen:
                    continue
                seen.add(key)
                fecha = _parse_fecha(str(item.get("fechaaprobacion") or "")) or f"{year}-01-01"
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _tipo_proyecto(blob),
                    "url": url,
                    "source": "ayuntamiento",
                    "expediente": exp,
                    "origen": "opendata_convenios",
                }
                self._attach_geometry(rec, enabled=self.geometry_enrich)
                rows.append(rec)
        return rows

    def _noticias_urbanismo(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            raw = self._fetch_text(URBANISMO_RSS)
        except urllib.error.URLError:
            return rows
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return rows
        channel = root.find("channel")
        if channel is None:
            return rows
        for item in channel.findall("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = _strip_html(title_el.text if title_el is not None and title_el.text else "")
            if not title or not RE_PROYECTO.search(title):
                continue
            link = (link_el.text or "").strip() if link_el is not None else URBANISMO_RSS
            fecha = _parse_fecha(date_el.text if date_el is not None else None) or datetime.now(
                timezone.utc
            ).strftime("%Y-%m-%d")
            guid_el = item.find("guid")
            guid = guid_el.text if guid_el is not None and guid_el.text else title
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"rss-{guid}"),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": fecha,
                "tipo": _tipo_proyecto(title),
                "url": link,
                "source": "ayuntamiento",
                "origen": "rss_urbanismo",
            }
            rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        self._geometry_attempts = 0
        by_id: dict[str, dict[str, Any]] = {}
        for rec in (
            self._licitaciones_urbanas()
            + self._convenios_urbanisticos()
            + self._noticias_urbanismo()
        ):
            by_id[rec["id"]] = rec
        return list(by_id.values())

    def _collect_licencias_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, default_title in self.tramite_licencia:
            try:
                html = self._fetch_text(url)
            except urllib.error.URLError:
                html = ""
            title = self._page_title(html, default_title)
            if not RE_LICENCIA.search(f"{title} {default_title}"):
                title = default_title
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite licencia / autorización obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title,
                "url": url,
                "source": "ayuntamiento",
                "nota": "Página informativa de trámite; sin listado público de licencias concedidas",
            }
            rows.append(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_pages()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_urbanismo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_pages():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "licitaciones": sum(1 for r in rows if r.get("origen") == "opendata_licitaciones"),
            "convenios": sum(1 for r in rows if r.get("origen") == "opendata_convenios"),
            "rss": sum(1 for r in rows if r.get("origen") == "rss_urbanismo"),
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
