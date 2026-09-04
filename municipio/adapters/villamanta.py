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
from municipio.gis.sitcm import WFS_BASE, _merge_geometries, resolve_ambito_geometry

WP_BASE = "https://www.villamanta.es"
SEDE_BASE = "https://sede.villamanta.es"
MUNICIPIO = "Villamanta"
ID_PREFIX = "villamanta"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VILLAMANTA"

TABLON_URL = f"{WP_BASE}/tu-ayuntamiento/tablon-de-anuncios/"
NNSS_URL = f"{WP_BASE}/tu-ayuntamiento/normativa-municipal/normas-subsidiarias-urbanismo/"
SOLICITUDES_URL = f"{WP_BASE}/ciudadanos/solicitudes-y-modelos/"
ORDENANZAS_URL = f"{WP_BASE}/tu-ayuntamiento/normativa-municipal/ordenanzas/"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"
QUERCUS_VISOR_URL = "http://81.46.222.82:8080/quercus/sig-alberche/index-28174.php"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|segregaci[oó]n|ocupaci[oó]n de v[ií]a|industrias y actividades)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|utilidad p[uú]blica|impacto ambiental|fotovolta|solar|"
    r"exposici[oó]n p[uú]blica|memoria|cat[aá]logo|ordenaci[oó]n|"
    r"cap[ií]tulo|plano|sau[\s_]*\d|unidad(?:es)? de ejecuci[oó]n|sector)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(presupuest|nombramiento|personal laboral|estabilizaci[oó]n|empleo|"
    r"coto de caza|coto 202|caza m-|ampliaci[oó]n coto|cambio de titularidad.*coto|"
    r"juez de paz|cuenta general|delegaci[oó]n del sr\. alcalde|"
    r"padr[oó]n|fiestas|certamen|equus|museo)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:SAU|UE|AD|AN|AI|PAU|S)[\s_\-]*\d+[A-Z0-9\-]*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ES = re.compile(
    r"(\d{1,2})\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|octubre|noviembre|diciembre)\s+de\s+(\d{4})",
    re.I,
)
RE_BOCM_DATE = re.compile(r"BOCM[-_]?(\d{4})[-_]?(\d{2})[-_]?(\d{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)
RE_PDF_LINK = re.compile(
    r'<a[^>]+href=["\']([^"\']+\.pdf[^"\']*)["\'][^>]*>([^<]*)</a>',
    re.I,
)

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_ES.search(text or "")
    if m:
        mes = MESES.get(m.group(2).lower())
        if mes:
            try:
                return datetime(int(m.group(3)), mes, int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"(\d{2})-(\d{2})-(\d{2})(?:\.pdf|$)", text or "")
    if m:
        try:
            year = 2000 + int(m.group(3)) if int(m.group(3)) < 70 else 1900 + int(m.group(3))
            return datetime(year, int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _abs_url(href: str, base: str = WP_BASE) -> str:
    return urllib.parse.urljoin(f"{base.rstrip('/')}/", unescape(href).replace("&amp;", "&"))


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "nnss" in n or "normas subsidiarias" in n or "capítulo" in n or "capitulo" in n:
        return "normas subsidiarias"
    if "memoria" in n:
        return "memoria planeamiento"
    if "catálogo" in n or "catalogo" in n:
        return "catálogo patrimonio"
    if "plano" in n or "ordenación" in n or "ordenacion" in n:
        return "planeamiento"
    if re.search(r"\bsau[\s_]*\d", n):
        return "suelo apto para urbanizar"
    if "impacto ambiental" in n or "fotovolta" in n or "solar" in n:
        return "evaluación ambiental"
    if "utilidad pública" in n or "exposici" in n:
        return "información pública"
    if "unidad" in n and "ejecuci" in n:
        return "unidad de ejecución"
    return "urbanismo"


class VillamantaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress rt-theme-20 + sede eAdmin (tablón inaccesible) + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.nnss_url = str(self.config.get("nnss_url") or NNSS_URL)
        self.solicitudes_url = str(self.config.get("solicitudes_url") or SOLICITUDES_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villamanta/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _wfs_query(self, cql: str, count: int = 80) -> list[dict[str, Any]]:
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

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache[name.upper()] = f
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache[re.sub(r"[\s_]+", "", code_m.group(1).upper())] = f
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if geom:
            ambit = meta.get("ambito_name") or ""
            cql = (
                f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                f"AND DS_NOMB_AMB='{str(ambit).replace(chr(39), chr(39) * 2)}'"
            )
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                ),
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": ambit,
            }
        cache = self._load_wfs_ambitos()
        for m in RE_AMBIT_CODE.finditer(titulo or ""):
            key = re.sub(r"[\s_]+", "", m.group(1).upper())
            feat = cache.get(key)
            if not feat:
                continue
            merged = _merge_geometries([feat])
            if not merged:
                continue
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "")
            cql = (
                f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
            )
            return {
                "geom_geojson": merged,
                "geometry_source": "portal_wfs",
                "geometry_source_url": (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                ),
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": name,
            }
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        cen = geometry_centroid(geom["geom_geojson"])
        if cen:
            rec.setdefault("lat", cen[0])
            rec.setdefault("lon", cen[1])

    def _parse_tablon_cards(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for part in re.split(r'(?=<div class="vc_col-sm-4)', html):
            if "vc_btn3" not in part:
                continue
            strong = re.search(r"<strong[^>]*>(.*?)</strong>", part, re.S | re.I)
            if not strong:
                continue
            title = re.sub(r"\s+", " ", _strip_html(strong.group(1))).strip()
            pdf_m = re.search(r'href="([^"]+\.pdf[^"]*)"', part, re.I)
            if not title or not pdf_m:
                continue
            pdf_url = _abs_url(pdf_m.group(1))
            plain = _strip_html(part)
            fecha = _parse_fecha_dmy(plain) or _parse_fecha_dmy(pdf_url)
            rows.append(
                {
                    "titulo": title[:500],
                    "pdf_url": pdf_url,
                    "fecha": fecha,
                    "url": self.tablon_url,
                    "origen": "tablon_cards",
                }
            )
        return rows

    def _parse_tablon_h2(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in re.finditer(r"<h2[^>]*>([^<]+)</h2>(.*?)(?=<h2|$)", html, re.S | re.I):
            title = _strip_html(m.group(1))
            body = m.group(2)
            pdfs = re.findall(r'href="([^"]+\.pdf[^"]*)"', body, re.I)
            if not title or not pdfs:
                continue
            fecha = _parse_fecha_dmy(body) or _parse_fecha_dmy(title)
            for pdf in pdfs:
                pdf_url = _abs_url(pdf)
                rows.append(
                    {
                        "titulo": title[:500],
                        "pdf_url": pdf_url,
                        "fecha": fecha or _parse_fecha_dmy(pdf_url),
                        "url": self.tablon_url,
                        "origen": "tablon_h2",
                    }
                )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._parse_tablon_cards(html) + self._parse_tablon_h2(html):
            key = item["pdf_url"]
            if key in seen:
                continue
            seen.add(key)
            rows.append(item)
        return rows

    def _collect_nnss_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.nnss_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_LINK.finditer(html):
            pdf_url = _abs_url(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            label = _strip_html(m.group(2)) or Path(urllib.parse.unquote(pdf_url)).stem
            label = re.sub(r"\s*\[Ver PDF\]\s*", "", label, flags=re.I).strip()
            rows.append(
                {
                    "titulo": f"NNSS Villamanta — {label}"[:500],
                    "pdf_url": pdf_url,
                    "fecha": _parse_fecha_dmy(pdf_url) or "2026-02-01",
                    "url": self.nnss_url,
                    "origen": "nnss",
                }
            )
        return rows

    def _collect_licencia_forms(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.solicitudes_url),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitudes y modelos — sección Urbanismo",
                "url": self.solicitudes_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF de licencias; no concesiones publicadas",
                "origen": "portal_tramites",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — presentación telemática",
                "url": f"{self.sede_base}/PortalCiudadano/Menus/wfrBienvenida.aspx",
                "source": "ayuntamiento",
                "nota": "Maggioli eAdmin (sede.villamanta.es); tablón no accesible sin sesión",
                "origen": "sede",
            },
        ]
        try:
            html = self._fetch(self.solicitudes_url)
        except urllib.error.URLError:
            return rows
        urban_block = ""
        m = re.search(
            r'<h4>\s*Urbanismo\s*</h4>.*?<div class="vc_toggle_content">(.*?)</div>\s*</div>',
            html,
            re.S | re.I,
        )
        if m:
            urban_block = m.group(1)
        else:
            urban_block = html
        seen = {r.get("pdf_url") for r in rows if r.get("pdf_url")}
        for m in RE_PDF_LINK.finditer(urban_block):
            pdf_url = _abs_url(m.group(1))
            if pdf_url in seen:
                continue
            label = _strip_html(m.group(2)) or Path(urllib.parse.unquote(pdf_url)).stem
            blob = f"{label} {pdf_url}"
            if not RE_LICENCIA.search(blob):
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": _parse_fecha_dmy(pdf_url),
                    "tipo": label[:120] or "formulario urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": f"Formulario: {label}"[:500],
                    "url": self.solicitudes_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "nota": "Modelo descargable; no concesión publicada",
                    "origen": "formularios_portal",
                }
            )
        return rows

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
                "url": self.nnss_url,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
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

    def _item_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{item.get('titulo', '')} {item.get('pdf_url', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = item.get("pdf_url") or item.get("url", "") + item.get("titulo", "")
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"],
            "fecha": item.get("fecha"),
            "tipo": _proyecto_tipo(item["titulo"]),
            "url": item.get("pdf_url") or item.get("url"),
            "source": "ayuntamiento",
            "origen": item.get("origen"),
        }
        if item.get("pdf_url"):
            rec["pdf_url"] = item["pdf_url"]
        self._enrich_geometry(rec)
        return rec

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
        rows = self._collect_licencia_forms()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if r.get("origen") in ("portal_tramites", "sede")),
            "forms": sum(1 for r in rows if r.get("origen") == "formularios_portal"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_forms():
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
            add(self._item_to_proyecto(item))
        for item in self._collect_nnss_pdfs():
            add(self._item_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon")),
            "nnss": sum(1 for r in rows if r.get("origen") == "nnss"),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
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
