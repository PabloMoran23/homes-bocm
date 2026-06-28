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
from municipio.geometry import record_geometry

BASE = "https://www.colladovillalba.es"
SEDE_BASE = "https://sedeelectronica.ayto-colladovillalba.org"
MUNICIPIO = "Collado Villalba"
ID_PREFIX = "collado-villalba"

DEFAULT_TABLON_SUBSECTIONS = ("AYTO.URB", "AYTO.EDICTOS")
DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/proyectos",
    f"{BASE}/pgou",
    f"{BASE}/modificaciones-pgou",
    f"{BASE}/plan-general-de-ordenacion-urbana",
]
TRAMITES_CATALOG = (
    f"{SEDE_BASE}/portal/noEstatica.do?opc_id=119&ent_id=1&idioma=1"
)
TABLON_PAGE = f"{SEDE_BASE}/portal/noEstatica.do?opc_id=268&ent_id=1&idioma=1"
GEOMETRY_LAYER = (
    "https://services-eu1.arcgis.com/4eGF8kfNzyifeBtz/arcgis/rest/services/"
    "Locales_CV_v2_ZonasUrbanisticas/FeatureServer/22"
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|c[eé]dula|obras? con proyecto|legalizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|parcelaci|desafect|"
    r"aprobaci[oó]n (?:inicial|definitiva)|modificaci[oó]n|estudio de detalle|"
    r"memoria|planos|sector|pol[ií]gono|casco antiguo|ordenanza.*urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_TIME = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\s+\d{2}:\d{2}")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_LINK = re.compile(
    r'href="((?:https://www\.colladovillalba\.es)?/documents/[^"?]+\.pdf[^"]*)"',
    re.I,
)
RE_DOC_LINK_ANY = re.compile(
    r'href="((?:https://www\.colladovillalba\.es)?/documents/[^"?]+)"',
    re.I,
)
RE_TRAMITE_ROW = re.compile(r'(?=<div class="col-lg-8 col-md-7)', re.I)
RE_STREET = re.compile(
    r"(?i)(?:calle|cl\.?|av\.?|avenida|plaza|paseo|camino|carretera)\s+([A-ZÁÉÍÓÚÑ][\w\s\-']{2,40})"
)
RE_PARCEL = re.compile(r"(?i)\bP-(\d+)\b")
RE_LIC_TRAMITE = re.compile(
    r"(?i)(licencia|c[eé]dula|declaraci[oó]n responsable|dr generica|obra con proyecto|"
    r"cambio de uso|segregaci|primera ocupaci|vado|calas|legalizaci)",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY_TIME, RE_FECHA_DMY):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                continue
    return None


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2030
    ]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _title_from_pdf_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0])
    name = Path(path).name
    if not name.lower().endswith(".pdf"):
        parts = [p for p in path.split("/") if p and not re.fullmatch(r"[0-9a-f-]{36}", p)]
        if parts:
            name = parts[-1]
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return name.replace("+", " ").strip()[:500]


def _proyecto_tipo(title: str, tipo_raw: str = "") -> str:
    blob = f"{title} {tipo_raw}".lower()
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "plan parcial" in blob or "plan ordenacion sector" in blob:
        return "plan parcial"
    if "plan especial" in blob:
        return "plan especial"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "reparcel" in blob or "parcelaci" in blob:
        return "reparcelación"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "pgou" in blob or "plan general" in blob:
        return "PGOU"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    if "licencia" in blob or "obra" in blob:
        return "licencia publicada"
    if "edicto" in blob or "desafect" in blob:
        return "edicto"
    return "urbanismo"


class ColladoVillalbaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay (planeamiento PDF) + sede tablón electrónico JSON + catálogo trámites."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_opc_id = int(self.config.get("tablon_opc_id", 268))
        self.tablon_subsections = tuple(
            self.config.get("tablon_subsections") or DEFAULT_TABLON_SUBSECTIONS
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.tramites_url = str(self.config.get("tramites_catalog_url") or TRAMITES_CATALOG)
        geom_cfg = self.config.get("geometry") or {}
        self.geometry_layer = str(geom_cfg.get("base_url") or GEOMETRY_LAYER)

    def _fetch(self, url: str, *, sede: bool = False, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-collado-villalba/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or ("iso-8859-1" if sede else "utf-8")
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, payload: dict[str, str]) -> dict[str, Any]:
        url = f"{self.sede_base}/sede/tablonElectronico.do"
        body = urllib.parse.urlencode(payload).encode()
        text = self._fetch(url, sede=True, data=body)
        return json.loads(text)

    def _abs_portal(self, href: str) -> str:
        return unescape(urllib.parse.urljoin(f"{BASE}/", href))

    def _abs_sede(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

    def _exp_url(self, exp: dict[str, Any], docs: list[dict[str, Any]] | None = None) -> str:
        if docs:
            doc_url = str(docs[0].get("docUrl") or "")
            if doc_url:
                return self._abs_sede(doc_url)
        return TABLON_PAGE

    def _tablon_consultar(self, subseccion: str) -> dict[str, Any]:
        return self._fetch_json(
            {
                "opcion": "consultar",
                "opc_id": str(self.tablon_opc_id),
                "ent_id": "1",
                "subseccion": subseccion,
            }
        )

    def _tablon_detalle(self, subseccion: str, exp_id: str) -> dict[str, Any]:
        return self._fetch_json(
            {
                "opcion": "verDetalleExpediente",
                "opc_id": str(self.tablon_opc_id),
                "ent_id": "1",
                "subseccion": subseccion,
                "expId": exp_id,
            }
        )

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sub in self.tablon_subsections:
            try:
                obj = self._tablon_consultar(sub)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for exp in obj.get("listaExpedientes") or []:
                exp_id = str(exp.get("idExp") or "")
                if not exp_id or exp_id in seen:
                    continue
                seen.add(exp_id)
                exp = dict(exp)
                exp["subseccion"] = sub
                rows.append(exp)
        return rows

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        street_m = RE_STREET.search(title or "")
        parcel_m = RE_PARCEL.search(title or "")
        where_parts: list[str] = []
        if street_m:
            street = street_m.group(1).strip().upper().replace("'", "''")
            where_parts.append(f"UPPER(nombre_via) LIKE '%{street[:30]}%'")
        if parcel_m:
            ref = parcel_m.group(1)
            where_parts.append(f"parcela_catastral LIKE '%{ref}%'")
        if not where_parts:
            return None

        where = " OR ".join(where_parts)
        params = {
            "where": where,
            "outFields": "parcela_catastral,nombre_via,primer_numero_policia",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "geojson",
            "resultRecordCount": "1",
        }
        query_url = f"{self.geometry_layer}/query?{urllib.parse.urlencode(params)}"
        try:
            text = self._fetch(query_url)
            data = json.loads(text)
        except (urllib.error.URLError, json.JSONDecodeError):
            return None

        features = data.get("features") or []
        if not features:
            return None
        geom = features[0].get("geometry")
        if not isinstance(geom, dict) or not geom.get("type"):
            return None
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_visor_arcgis",
            "geometry_source_url": query_url,
            "coord_source": "portal_geometry_centroid",
        }

    def _exp_to_proyecto(self, exp: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{exp.get('tipoDes', '')} {exp.get('nombre', '')}"
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not re.search(
            r"(?i)obra|planeam|plan|reparcel|convenio|edicto|desafect", blob
        ):
            return None

        title = str(exp.get("nombre") or "").strip()[:500]
        fecha = _parse_fecha_dmy(str(exp.get("fechaPublicacion") or "")) or _parse_fecha_dmy(
            str(exp.get("fechaCreacion") or "")
        )
        expte = f"{exp.get('anno')}/{exp.get('codigo')}"
        docs: list[dict[str, Any]] = []
        try:
            det = self._tablon_detalle(str(exp.get("subseccion")), str(exp.get("idExp")))
            docs = det.get("listaDocumentos") or []
        except (urllib.error.URLError, json.JSONDecodeError):
            pass

        rec: dict[str, Any] = {
            "id": _stable_id("proy", str(exp.get("idExp"))),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": fecha,
            "tipo": _proyecto_tipo(title, str(exp.get("tipoDes") or "")),
            "url": self._exp_url(exp, docs),
            "source": "ayuntamiento",
            "expte": expte,
            "origen": f"tablon_{exp.get('subseccion')}",
        }
        if docs:
            rec["documentos"] = [str(d.get("docNom") or "")[:200] for d in docs[:8]]
        geom = self._fetch_geometry(title)
        if geom:
            rec.update(geom)
        return rec

    def _exp_to_licencia(self, exp: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{exp.get('tipoDes', '')} {exp.get('nombre', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        title = str(exp.get("nombre") or "").strip()[:500]
        fecha = _parse_fecha_dmy(str(exp.get("fechaPublicacion") or "")) or _parse_fecha_dmy(
            str(exp.get("fechaCreacion") or "")
        )
        return {
            "id": _stable_id("lic", str(exp.get("idExp"))),
            "fecha_concesion": fecha,
            "tipo": str(exp.get("tipoDes") or "licencia")[:120],
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "url": TABLON_PAGE,
            "source": "ayuntamiento",
            "expte": f"{exp.get('anno')}/{exp.get('codigo')}",
            "origen": f"tablon_{exp.get('subseccion')}",
        }

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for pat in (RE_DOC_LINK, RE_DOC_LINK_ANY):
                for m in pat.finditer(html):
                    href = m.group(1)
                    if not href.lower().endswith(".pdf") and "/documents/" not in href.lower():
                        continue
                    url = self._abs_portal(href)
                    if url in seen:
                        continue
                    seen.add(url)
                    title = _title_from_pdf_url(url)
                    if not title or len(title) < 5:
                        continue
                    rows.append(
                        {
                            "titulo": title,
                            "url": url,
                            "fecha": _parse_fecha_dmy(url) or _iso_from_year(title),
                            "origen": page_url,
                        }
                    )
        return rows

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title = row["titulo"]
        if not RE_PROYECTO.search(title):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(title),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "liferay_pdf",
        }
        geom = self._fetch_geometry(title)
        if geom:
            rec.update(geom)
        return rec

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramites_url, sede=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        blocks = RE_TRAMITE_ROW.split(html)
        for block in blocks:
            title_m = re.search(r'title="(\d+\s+[^"]+)"', block)
            if not title_m:
                title_m = re.search(
                    r'title="([^"]*(?:Licencia|licencia|C[eé]dula|DR Generica|Declaraci[oó]n)[^"]*)"',
                    block,
                    re.I,
                )
            ficha_m = re.search(r"fichaInformativa\.do\?asu_cod=[^\"'<>]+", block)
            if not title_m or not ficha_m:
                continue
            title = unescape(title_m.group(1).strip())
            if not RE_LIC_TRAMITE.search(title):
                continue
            url = self._abs_sede(f"/sede/{ficha_m.group(0)}")
            if url in seen:
                continue
            seen.add(url)
            rows.append({"url": url, "titulo": title[:500]})
        return rows

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        url = row["url"]
        title = str(row.get("titulo") or "").strip()
        if not title or not RE_LIC_TRAMITE.search(title):
            return None
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": None,
            "tipo": "trámite informativo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": title,
            "url": url,
            "source": "ayuntamiento",
            "origen": "sede_tramite",
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _merge_rows(self, *groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for group in groups:
            for row in group:
                rid = str(row.get("id") or "")
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                out.append(row)
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        lic_rows: list[dict[str, Any]] = []
        for exp in self._collect_tablon():
            rec = self._exp_to_licencia(exp)
            if rec:
                lic_rows.append(rec)
        for tram in self._collect_tramites():
            rec = self._tramite_to_licencia(tram)
            if rec:
                lic_rows.append(rec)
        rows = self._merge_rows(lic_rows)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon_")),
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        proy_rows: list[dict[str, Any]] = []
        for exp in self._collect_tablon():
            rec = self._exp_to_proyecto(exp)
            if rec:
                proy_rows.append(rec)
        for pdf in self._collect_seed_pdfs():
            rec = self._pdf_to_proyecto(pdf)
            if rec:
                proy_rows.append(rec)
        rows = self._merge_rows(proy_rows)
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if str(r.get("origen", "")).startswith("tablon_")),
            "liferay_pdf": sum(1 for r in rows if r.get("origen") == "liferay_pdf"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
