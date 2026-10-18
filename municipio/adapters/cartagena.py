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

WEB_BASE = "https://www.cartagena.es"
URBANISMO_BASE = "https://urbanismo.cartagena.es/urbanismo"
SEDE_BASE = "https://cartagena.sedipualba.es"
MUNICIPIO = "Cartagena"
ID_PREFIX = "cartagena"

TABLON_RSS = f"{SEDE_BASE}/tablondeanuncios/tablon_rss.aspx"
TABLON_URL = f"{SEDE_BASE}/tablondeanuncios/"
CATALOGO_URBANISMO = f"{SEDE_BASE}/catalogoservicios.aspx?area=980&ambito="

LISTA_KINDS: tuple[tuple[str, str, str], ...] = (
    ("IP", f"{URBANISMO_BASE}/Lista/IP", "información pública"),
    ("PL", f"{URBANISMO_BASE}/Lista/PL", "plan urbanístico"),
    ("ED", f"{URBANISMO_BASE}/Lista/ED", "estudio de detalle"),
    ("UA", f"{URBANISMO_BASE}/Lista/UA", "unidad de actuación"),
    ("Convenio", f"{URBANISMO_BASE}/Lista/Convenio", "convenio urbanístico"),
)

RE_TRAMITE = re.compile(
    r'href="(https://cartagena\.sedipualba\.es/(?:carpetaciudadana|segex)/tramite\.aspx\?idtramite=\d+)"'
    r'[^>]*class="a_procedimiento[^"]*"[^>]*title="[^"]*Acceder[^"]*">([^<]+)</a>',
    re.I | re.S,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|obra (?:mayor|menor)|primera ocupaci[oó]n|demolici[oó]n|"
    r"drub|drpo|drso|cpro|icio)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n|expediente|proyecto|modificaci[oó]n|"
    r"reparcel|estudio de detalle|unidad de actuaci[oó]n|edicto|borm|"
    r"aprobaci[oó]n|revisi[oó]n del plan|área de reparto|pau-|peop)",
)
RE_TABLON_NOISE = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"becas|mercadillo|pleno ordinario|junta municipal|jurado|bodas|"
    r"hijo predilecto|herencia a beneficio)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ES = re.compile(
    r"(\d{1,2})-(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)-(\d{4})",
    re.I,
)
RE_MAPA = re.compile(
    r"CQEntidad=([^&']+)&CQValor=(\d+)&CQAdd=\d+&CQBox=([0-9\-]+)",
    re.I,
)
RE_FICHA = re.compile(
    r'href="(https://urbanismo\.cartagena\.es/urbanismo/Ficha/[^"]+)"',
    re.I,
)

_MONTH_ES = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha(text: str) -> str | None:
    if not text:
        return None
    m = RE_FECHA_ES.search(text)
    if m:
        try:
            return datetime(
                int(m.group(3)),
                _MONTH_ES[m.group(2).lower()],
                int(m.group(1)),
            ).strftime("%Y-%m-%d")
        except (KeyError, ValueError):
            pass
    m = RE_FECHA_DMY.search(text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _proyecto_tipo(kind: str, title: str) -> str:
    n = (title or "").lower()
    if kind == "IP":
        return "información pública"
    if kind == "ED":
        return "estudio de detalle"
    if kind == "UA":
        return "unidad de actuación"
    if kind == "Convenio":
        return "convenio urbanístico"
    if "plan general" in n or "pgmo" in n or "pgou" in n:
        return "PGOU"
    if "plan parcial" in n or "pau-" in n:
        return "plan parcial"
    if "revisi" in n and "plan" in n:
        return "revisión planeamiento"
    return "planeamiento"


def _cqbox_to_geojson(box: str) -> dict[str, Any] | None:
    parts = box.split("-")
    if len(parts) != 4:
        return None
    try:
        xmin, ymin, xmax, ymax = (float(p) for p in parts)
    except ValueError:
        return None
    try:
        from pyproj import Transformer

        transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
    except Exception:
        return None
    ring: list[list[float]] = []
    for x, y in ((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)):
        lon, lat = transformer.transform(x, y)
        ring.append([lon, lat])
    return {"type": "Polygon", "coordinates": [ring]}


class CartagenaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal urbanismo.cartagena.es (ASP.NET SIU) + sede Sedipualba."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or URBANISMO_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.urbanismo_base = str(self.config.get("urbanismo_base") or URBANISMO_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.tablon_rss = str(self.config.get("tablon_rss") or TABLON_RSS)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_urbanismo = str(
            self.config.get("catalogo_urbanismo") or CATALOGO_URBANISMO
        )

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        last_err: Exception | None = None
        for attempt in range(3):
            time.sleep(self.delay_s)
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cartagena/1.0")},
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    raw = resp.read()
                for enc in ("utf-8", "latin-1", "iso-8859-1"):
                    try:
                        return raw.decode(enc)
                    except UnicodeDecodeError:
                        continue
                return raw.decode("utf-8", errors="replace")
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.4 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

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
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _geovisor_url(self, entidad: str, valor: str, box: str) -> str:
        return (
            f"{self.urbanismo_base}/GeoVisor?FOR=Page&Composicion=COMPOSICION_RPG0"
            f"&Fondo=CARTOGRAFIA_87&CQEntidad={urllib.parse.quote(entidad)}"
            f"&CQValor={valor}&CQAdd=2&CQBox={box}"
        )

    def _attach_map_geometry(self, rec: dict[str, Any], entidad: str, valor: str, box: str) -> None:
        if record_geometry(rec):
            return
        geom = _cqbox_to_geojson(box)
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_visor_cqbox"
        rec["geometry_source_url"] = self._geovisor_url(entidad, valor, box)
        rec["coord_source"] = "portal_geometry_centroid"
        cen = geometry_centroid(geom)
        if cen:
            rec.setdefault("lat", cen[0])
            rec.setdefault("lon", cen[1])

    def _parse_gv_rows(self, html: str, kind: str, default_tipo: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for table in re.findall(r'<table class="GV_Lista"[^>]*>(.*?)</table>', html, re.S | re.I):
            for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S | re.I):
                if "<th" in tr:
                    continue
                cells = [_clean_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S | re.I)]
                if len(cells) < 2:
                    continue
                ficha_m = RE_FICHA.search(tr)
                mapa_m = RE_MAPA.search(tr)
                matricula = cells[0] if cells[0] and len(cells[0]) < 40 else ""
                expediente = ""
                for c in cells:
                    if re.search(r"\d{4}/\d+", c) or re.match(r"R\d+-", c):
                        expediente = c
                        break
                title_candidates = [c for c in cells if len(c) > 25 and not re.match(r"^[\d\s/✔✖-]+$", c)]
                titulo = max(title_candidates, key=len) if title_candidates else cells[-2]
                fecha = None
                for c in cells[:3]:
                    fecha = _parse_fecha(c) or fecha
                ficha = ficha_m.group(1) if ficha_m else None
                key = ficha or f"{kind}:{matricula}:{titulo[:80]}"
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(kind, titulo) if kind else default_tipo,
                    "url": ficha or f"{self.urbanismo_base}/Lista/{kind}",
                    "source": "ayuntamiento",
                    "origen": f"urbanismo_lista_{kind.lower()}",
                    "matricula": matricula or None,
                    "expediente": expediente or None,
                }
                if mapa_m:
                    ent, val, box = mapa_m.group(1), mapa_m.group(2), mapa_m.group(3)
                    self._attach_map_geometry(rec, ent, val, box)
                rows.append(rec)
        return rows

    def _collect_urbanismo_listas(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for kind, url, _label in LISTA_KINDS:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for rec in self._parse_gv_rows(html, kind, _label):
                if rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                out.append(rec)
        return out

    def _collect_tablon_rss(self) -> list[dict[str, Any]]:
        try:
            raw = self._fetch(self.tablon_rss)
        except urllib.error.URLError:
            return []
        try:
            root = ET.fromstring(raw)
        except ET.ParseError:
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = item.findtext("pubDate") or ""
            fecha = None
            try:
                fecha = parsedate_to_datetime(pub).strftime("%Y-%m-%d")
            except (TypeError, ValueError, IndexError):
                fecha = None
            if not title or not link:
                continue
            rows.append({"titulo": title, "url": link, "fecha": fecha, "blob": title})
        return rows

    def _tablon_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_TABLON_NOISE.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _collect_tramites_urbanismo(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(self.catalogo_urbanismo)
        except urllib.error.URLError:
            return rows
        for href, title in RE_TRAMITE.findall(html):
            titulo = _clean_html(unescape(title))
            if href in seen:
                continue
            seen.add(href)
            rows.append(
                {
                    "id": _stable_id("lic", href),
                    "fecha_concesion": None,
                    "tipo": "trámite urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": href,
                    "source": "ayuntamiento",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de edictos electrónicos — Cartagena",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
                "nota": "Edictos y licencias en cartagena.sedipualba.es",
            },
            {
                "id": _stable_id("lic", self.catalogo_urbanismo),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites — área Urbanismo y Actividades",
                "url": self.catalogo_urbanismo,
                "source": "ayuntamiento",
                "origen": "sede_tramite",
            },
        ]

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._licencia_info_pages() + self._collect_tramites_urbanismo():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon_rss():
            if not self._tablon_is_urban(item):
                continue
            blob = item.get("blob") or ""
            if not RE_LICENCIA.search(blob):
                continue
            key = item["url"]
            rec = {
                "id": _stable_id("lic", key),
                "fecha_concesion": item.get("fecha"),
                "tipo": "licencia / edicto tablón",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"][:500],
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": "tablon",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
        rows = self._collect_urbanismo_listas()
        for item in self._collect_tablon_rss():
            if not self._tablon_is_urban(item):
                continue
            blob = item.get("blob") or ""
            if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            key = item["url"]
            rows.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": item["titulo"][:500],
                    "fecha": item.get("fecha"),
                    "tipo": _proyecto_tipo("", item["titulo"]),
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": "tablon",
                }
            )
        # dedupe by id
        by_id: dict[str, dict[str, Any]] = {}
        for rec in rows:
            by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "urbanismo_listas": sum(1 for r in rows if str(r.get("origen", "")).startswith("urbanismo")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
