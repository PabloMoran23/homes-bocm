from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.coruna.gal"
SEDE_BASE = "https://sede.coruna.gal"
MUNICIPIO = "A Coruña"
ID_PREFIX = "a-coruna"

EXPOSICION_PUBLICA = (
    f"{BASE}/urbanismo/es/informacion-y-normativa/exposicion-publica?argIdioma=es"
)
PLANEAMIENTO_VIGENTE = f"{BASE}/urbanismo/es/planeamiento/planeamiento-vigente?argIdioma=es"
CONVENIOS = f"{BASE}/urbanismo/es/informacion-y-normativa/convenios-urbanisticos?argIdioma=es"
TRAMITES = f"{BASE}/urbanismo/es/informacion-y-normativa/tramites?argIdioma=es"
LICENCIAS_SECCION = f"{BASE}/urbanismo/es/licencias-y-disciplina?argIdioma=es"
TABLON_SEDE = f"{SEDE_BASE}/opensiac/action/infopublica?method=enter&edictos=true"

DESARROLLO_QUERY = (
    "https://ide.coruna.gal/server/rest/services/Publica/PGM13_WMS_DESARROLLO/MapServer/0/query"
)

DEFAULT_SEED_PAGES: list[str] = [
    EXPOSICION_PUBLICA,
    PLANEAMIENTO_VIGENTE,
    CONVENIOS,
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    TRAMITES,
    LICENCIAS_SECCION,
    TABLON_SEDE,
]

RE_LISTADO = re.compile(
    r'<li id="item_(\d+)"[^>]*class="listadoNormativa"[^>]*>\s*'
    r'<header><h1[^>]*><a href=\'([^\']+)\'>([^<]+)</a></h1>.*?'
    r"property='description'[^>]*>(.*?)</div>",
    re.S | re.I,
)
RE_TRAMITE = re.compile(
    r"detalle-tramites/([^/]+)/contenido/(\d+)",
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXPEDIENTE = re.compile(
    r"(?i)(?:expediente|exped\.?|exp\.?)\s*[:.]?\s*"
    r"([A-Z]{2,4}/\d{4}/\d+|631/\d{4}/\d+|DPE/\d{4}/\d+)",
)
RE_COD_PGOM = re.compile(
    r"(?i)\b(?:POL|PE|MPP|MPG|PGOM|PEMD)\s*[A-Z]?\s*[-]?\s*([A-Z]?\d+[A-Z]?)\b|"
    r"\b(?:sector|sector\s*)[sS]\s*[-]?\s*(\d+)\b|"
    r"\bM(\d{2})\b",
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|demolici[oó]n|edificaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgom|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|suspensi[oó]n cautelar|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|pol[ií]gono|parcela)",
)
RE_FECHA_DETAIL = re.compile(
    r'<section class="fecha">.*?<p class="fecha"[^>]*>([^<]+)</p>',
    re.S | re.I,
)
RE_SEDE_ROW = re.compile(
    r'method=view&amp;id=(\d+)"[^>]*title="Amosar ([^"]+)"',
    re.I,
)
RE_SEDE_FECHA = re.compile(
    r'<td class="listaPublicacionesFecha">\s*(\d{2}/\d{2}/\d{4})\s*</td>',
    re.I,
)

MONTHS_GL_ES = {
    "xaneiro": 1,
    "febreiro": 2,
    "marzo": 3,
    "abril": 4,
    "maio": 5,
    "xuño": 6,
    "xuno": 6,
    "xullo": 7,
    "julio": 7,
    "agosto": 8,
    "setembro": 9,
    "septiembre": 9,
    "outubro": 10,
    "octubre": 10,
    "novembro": 11,
    "noviembre": 11,
    "decembro": 12,
    "diciembre": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_ascii(s: str) -> str:
    t = unicodedata.normalize("NFD", s or "")
    return t.encode("ascii", "ignore").decode("ascii").lower()


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


def _parse_fecha_words(text: str) -> str | None:
    low = _norm_ascii(text)
    m = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", low)
    if not m:
        return None
    month = MONTHS_GL_ES.get(m.group(2))
    if not month:
        return None
    try:
        return datetime(int(m.group(3)), month, int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(blob: str) -> str | None:
    return _parse_fecha_dmy(blob) or _parse_fecha_words(blob)


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n or "estudo de detalle" in n:
        return "estudio de detalle"
    if "modificaci" in n and ("pgom" in n or "plan parcial" in n):
        return "modificación planeamiento"
    if "reparcel" in n:
        return "reparcelación"
    if "convenio" in n:
        return "convenio urbanístico"
    if "suspensi" in n and "cautelar" in n:
        return "suspensión cautelar"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "plan parcial" in n or "plan especial" in n:
        return "plan parcial/especial"
    if "pgom" in n or "plan general" in n:
        return "PGOM"
    return "urbanismo"


class ACorunaAyuntamientoAdapter(AyuntamientoAdapter):
    """Portal coruna.gal (Urbanismo20) + sede OpenSIAC + ArcGIS planeamiento desarrollo."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self._desarrollo_cache: list[dict[str, Any]] | None = None
        self._geom_cache: dict[str, dict[str, Any] | None] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-a-coruna/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-a-coruna/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

    def _parse_listado(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LISTADO.finditer(html):
            item_id, href, title, desc_html = m.group(1), m.group(2), m.group(3), m.group(4)
            if item_id in seen:
                continue
            seen.add(item_id)
            desc = _strip_html(desc_html)
            url = self._abs_url(href)
            blob = f"{title} {desc}"
            rows.append(
                {
                    "item_id": item_id,
                    "titulo": unescape(title).strip()[:500],
                    "descripcion": desc[:2000],
                    "blob": blob[:2500],
                    "fecha": _fecha_from_blob(blob),
                    "url": url,
                    "origen": origen,
                }
            )
        return rows

    def _enrich_fecha_from_detail(self, row: dict[str, Any]) -> dict[str, Any]:
        if row.get("fecha"):
            return row
        try:
            html = self._fetch(row["url"])
        except urllib.error.URLError:
            return row
        m = RE_FECHA_DETAIL.search(html)
        if m:
            fecha = _fecha_from_blob(m.group(1))
            if fecha:
                row["fecha"] = fecha
        return row

    def _collect_portal_proyectos(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        for page in self.seed_pages:
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue
            origen = "exposicion_publica" if "exposicion-publica" in page else (
                "planeamiento_vigente" if "planeamiento-vigente" in page else "convenios"
            )
            for row in self._parse_listado(html, origen):
                key = row.get("url") or row["item_id"]
                merged[key] = row
        for row in list(merged.values()):
            self._enrich_fecha_from_detail(row)
        return list(merged.values())

    def _parse_sede_tablon(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        chunks = html.split('<td class="listaPublicacionesDescripcion">')
        for chunk in chunks[1:]:
            id_m = re.search(r'method=view[^"]*id=(\d+)', chunk)
            if not id_m:
                continue
            pub_id = id_m.group(1)
            titulo = _strip_html(chunk.split("</td>", 1)[0])
            if not titulo or len(titulo) < 10:
                continue
            fecha_m = RE_SEDE_FECHA.search(chunk)
            fecha = _parse_fecha_dmy(fecha_m.group(1)) if fecha_m else None
            url = f"{self.sede_base}/opensiac/action/infopublica?method=view&id={pub_id}"
            rows.append(
                {
                    "pub_id": pub_id,
                    "titulo": titulo[:500],
                    "blob": titulo,
                    "fecha": fecha,
                    "url": url,
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_tablon_sede(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_SEDE)
        except urllib.error.URLError:
            return []
        return [r for r in self._parse_sede_tablon(html) if RE_PROYECTO.search(r.get("blob", ""))]

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(TRAMITES)
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for m in RE_TRAMITE.finditer(html):
            slug_part, content_id = m.group(1), m.group(2)
            if content_id in seen:
                continue
            seen.add(content_id)
            title = slug_part.replace("-", " ").title()
            if not any(
                k in slug_part
                for k in (
                    "licencia",
                    "licencias",
                    "demolicion",
                    "edificacion",
                    "obra",
                    "urban",
                    "actividad",
                    "comunicacion",
                    "declaracion",
                )
            ):
                continue
            url = self._abs_url(
                f"/urbanismo/es/informacion-y-normativa/tramites/detalle-tramites/"
                f"{slug_part}/contenido/{content_id}"
            )
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": title if "licencia" in slug_part else "trámite urbanístico",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramites_catalogo",
                }
            )
        return rows

    def _load_desarrollo_index(self) -> list[dict[str, Any]]:
        if self._desarrollo_cache is not None:
            return self._desarrollo_cache
        params = urllib.parse.urlencode(
            {
                "where": "1=1",
                "outFields": "DENOMINAC,COD_PGOM,IDRUD",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultRecordCount": "500",
            }
        )
        url = f"{DESARROLLO_QUERY}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._desarrollo_cache = []
            return self._desarrollo_cache
        rows: list[dict[str, Any]] = []
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not isinstance(geom, dict):
                continue
            denom = str(props.get("DENOMINAC") or "").strip()
            cod = str(props.get("COD_PGOM") or "").strip()
            if not denom:
                continue
            rows.append(
                {
                    "denom": denom,
                    "denom_norm": _norm_ascii(denom),
                    "cod": cod,
                    "cod_norm": _norm_ascii(cod),
                    "geom": geom,
                }
            )
        rows.sort(key=lambda r: len(r["denom_norm"]), reverse=True)
        self._desarrollo_cache = rows
        return rows

    def _fetch_geometry(self, titulo: str, blob: str = "") -> dict[str, Any] | None:
        cache_key = _norm_ascii(f"{titulo}|{blob}")
        if cache_key in self._geom_cache:
            return self._geom_cache[cache_key]

        text = f"{titulo} {blob}"
        text_norm = _norm_ascii(text)
        tokens = [t for t in re.split(r"[^\w]+", text_norm) if len(t) >= 4]
        cod_hints: set[str] = set()
        for m in RE_COD_PGOM.finditer(text):
            for g in m.groups():
                if g:
                    cod_hints.add(g.upper())

        result: dict[str, Any] | None = None
        for row in self._load_desarrollo_index():
            denom_norm = row["denom_norm"]
            if len(denom_norm) < 4:
                continue
            compact_denom = denom_norm.replace(" ", "")
            compact_text = text_norm.replace(" ", "")
            cod_norm = row["cod_norm"]
            match = False
            if cod_norm and cod_norm.replace(" ", "") in compact_text.replace(" ", ""):
                match = True
            elif compact_denom in compact_text:
                match = True
            elif denom_norm in text_norm:
                match = True
            else:
                for hint in cod_hints:
                    if hint in cod_norm.replace(" ", "").upper() or hint in denom_norm.upper():
                        match = True
                        break
                if not match:
                    for tok in tokens:
                        if tok in denom_norm and len(tok) >= 5:
                            match = True
                            break
            if not match:
                continue
            geom = row["geom"]
            query = (
                f"{DESARROLLO_QUERY}?"
                + urllib.parse.urlencode(
                    {
                        "where": f"DENOMINAC='{row['denom'].replace(chr(39), chr(39)+chr(39))}'",
                        "outFields": "DENOMINAC,COD_PGOM",
                        "returnGeometry": "true",
                        "outSR": "4326",
                        "f": "geojson",
                        "resultRecordCount": "1",
                    }
                )
            )
            result = {
                "geom_geojson": geom,
                "geometry_crs": "EPSG:4326",
                "geometry_axis_order": "xy",
                "geometry_source": "portal_visor_arcgis",
                "geometry_source_url": query,
                "coord_source": "portal_geometry_centroid",
                "cod_pgom": row["cod"],
                "ambito_gis": row["denom"],
            }
            break

        self._geom_cache[cache_key] = result
        return result

    def _enrich_geometry(self, rec: dict[str, Any]) -> dict[str, Any]:
        if record_geometry(rec):
            return rec
        geom_fields = self._fetch_geometry(
            str(rec.get("titulo") or ""),
            str(rec.get("descripcion") or rec.get("blob") or ""),
        )
        if geom_fields:
            rec.update(geom_fields)
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob.replace("licencia", "")):
            if "planeam" not in blob.lower() and "plan " not in blob.lower():
                return None
        key = row.get("url") or row.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row.get("titulo"),
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        exp = RE_EXPEDIENTE.search(blob)
        if exp:
            rec["expediente"] = exp.group(1).strip()
        if row.get("descripcion"):
            rec["descripcion"] = row["descripcion"]
        return self._enrich_geometry(rec)

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_PROYECTO.search(blob) and "licencia" not in blob.lower() and "licenz" not in blob.lower():
            return None
        tipo = "licencia"
        low = blob.lower()
        if "suspensi" in low and "licencia" in low:
            tipo = "suspensión cautelar de licencias"
        elif "demolici" in low:
            tipo = "licencia de demolición"
        elif "comunicaci" in low:
            tipo = "comunicación previa"
        key = row.get("url") or row.get("titulo", "")
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo"),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_tramites()
        seen = {r["id"] for r in rows}
        for item in self._collect_tablon_sede():
            lic = self._to_licencia(item)
            if lic and lic["id"] not in seen:
                rows.append(lic)
                seen.add(lic["id"])
        for item in self._collect_portal_proyectos():
            lic = self._to_licencia(item)
            if lic and lic["id"] not in seen:
                rows.append(lic)
                seen.add(lic["id"])
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "tramites+tablon+exposicion",
            "tramites": sum(1 for r in rows if r.get("origen") == "tramites_catalogo"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        portal = self._collect_portal_proyectos()
        tablon = self._collect_tablon_sede()
        by_url: dict[str, dict[str, Any]] = {}
        for item in portal + tablon:
            key = item.get("url") or item.get("titulo", "")
            if key:
                by_url[key] = item
        rows: list[dict[str, Any]] = []
        for item in by_url.values():
            proy = self._to_proyecto(item)
            if proy:
                rows.append(proy)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "portal+tablon",
            "exposicion": sum(1 for r in rows if r.get("origen") == "exposicion_publica"),
            "vigente": sum(1 for r in rows if r.get("origen") == "planeamiento_vigente"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
