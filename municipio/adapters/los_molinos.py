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
from municipio.gis.sitcm import WFS_BASE, resolve_municipio_wfs

WP_BASE = "https://www.ayuntamiento-losmolinos.es"
SEDE_BASE = "https://sede.ayuntamiento-losmolinos.es/eAdmin"
TRANSP_BASE = "https://transparencia.ayuntamiento-losmolinos.es"
MUNICIPIO = "Los Molinos"
ID_PREFIX = "los-molinos"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TRAMITES_URL = f"{SEDE_BASE}/Registrar.do?action=listadoEntradas"
URBANISMO_URL = f"{WP_BASE}/?page_id=36668"

DEFAULT_TRANSPARENCIA_PAGES: list[dict[str, Any]] = [
    {"page_id": 185, "section": "planeamiento", "tipo": "planeamiento"},
]

DEFAULT_WP_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    f"{WP_BASE}/?p=40276",
    f"{WP_BASE}/?p=10954",
]

DEFAULT_SEARCH_TERMS = (
    "URBANISMO",
    "LICENCIA",
    "INFORMACION PUBLICA",
    "PLAN",
    "PGOU",
    "AVANCE",
    "UA-",
    "SAU-",
    "ESTUDIO",
    "CONVENIO",
    "REPARCEL",
    "APROBACION",
)

DEFAULT_TRAMITE_IDS = (34, 35, 36, 37, 51)

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
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento|obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable.*obra|"
    r"comunicaci[oó]n previa|ordenanza.*licencia|primera ocupaci|obra mayor|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"modificaci[oó]n|estudio (?:ac[uú]stico|ambiental|de detalle)|ua-\d|sau-|ue-\d|"
    r"avance|normas subsidiarias|memoria|planos|bocm)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|iae|cobranza|tribut|presupuest|empleo|igualdad|notificaci[oó]n telem)",
)
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UA|SAU|UE|AD|AN|AI|PAU|S)-[\w\d.\-]+)\b")
RE_MODAL_TITLE = re.compile(
    r'id="modalInformacion(\d+)"[^>]*>.*?<h4[^>]*>([^<]+)',
    re.I | re.S,
)
RE_ABRIR_CODE = re.compile(r"abrir\(['\"]([^'\"]+)['\"]\)")
RE_ABRIR_TITLE = re.compile(
    r"abrir\(['\"]([^'\"]+)['\"]\)[^>]*>([^<]+)</a>",
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://www\.ayuntamiento-losmolinos\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
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
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "avance" in n and "pgou" in n:
        return "avance PGOU"
    if "plan parcial" in n or "plan especial" in n or "pgou" in n or re.search(r"ua-\d|sau-|ue-\d", n):
        return "planeamiento"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "informaci" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    if "memoria" in n:
        return "memoria"
    return default


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del ", " de los molinos", " finca "):
        if marker in low:
            low = low.split(marker, 1)[-1 if marker == " finca " else 0]
    parts = [p for p in re.split(r"[\s,;/|()\"«»]+", low) if len(p) >= 4]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and k not in {"molinos", "general", "avance", "bloque", "documento"}:
            seen.add(k)
            out.append(p)
    return out[:8]


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class LosMolinosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo + sede eAdmin (tablón + trámites) + transparencia + SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.tramite_ids = [int(x) for x in (self.config.get("tramite_ids") or DEFAULT_TRAMITE_IDS)]
        self.transp_pages = list(
            self.config.get("transparencia_pages") or DEFAULT_TRANSPARENCIA_PAGES
        )
        self.wp_seed_pages = [str(u) for u in (self.config.get("wp_seed_pages") or DEFAULT_WP_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_municipio = str(
            geom_cfg.get("municipio_filter")
            or resolve_municipio_wfs(MUNICIPIO)
            or "LOS MOLINOS"
        )
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-los-molinos/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or (
                "utf-8" if "ayuntamiento-losmolinos" in url else "iso-8859-1"
            )
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href).replace("&amp;", "&"))

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

    def _extract_transparencia_docs(self, html: str) -> list[tuple[str, str]]:
        by_code: dict[str, str] = {}
        for code, anchor_title in RE_ABRIR_TITLE.findall(html):
            title = _clean_title(anchor_title)
            if title and title.lower() != "ver documento":
                by_code[code] = title
        for m in re.finditer(r"<h[234][^>]*>([^<]+)</h[234]>", html, re.I):
            section = _clean_title(m.group(1))
            if section:
                for code in RE_ABRIR_CODE.findall(m.group(0)):
                    by_code.setdefault(code, section)
        return [(title, code) for code, title in by_code.items()]

    def _collect_transparencia_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page in self.transp_pages:
            page_id = int(page["page_id"])
            section = str(page.get("section") or page_id)
            default_tipo = str(page.get("tipo") or "urbanismo")
            page_url = f"{self.transp_base}/?page_id={page_id}"
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for title, code in self._extract_transparencia_docs(html):
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", code),
                    "municipio": MUNICIPIO,
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(title),
                    "tipo": _proyecto_tipo(title, default_tipo),
                    "url": page_url,
                    "pdf_url": _doc_url(self.sede_base, code),
                    "source": "ayuntamiento",
                    "origen": section,
                    "doc_code": code,
                }
                self._enrich_geometry(rec)
                rows.append(rec)
        return rows

    def _collect_wp_docs(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        proyectos: list[dict[str, Any]] = []
        licencias: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.wp_seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_WP_PDF.finditer(html):
                href = m.group(1)
                pdf_url = self._abs_wp(href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                name = Path(urllib.parse.unquote(pdf_url.split("?")[0])).stem.replace("-", " ").replace("_", " ")
                titulo = name[:500]
                blob = f"{titulo} {pdf_url}"
                if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                    licencias.append(
                        {
                            "id": _stable_id("lic", pdf_url),
                            "fecha_concesion": _parse_fecha_dmy(pdf_url),
                            "tipo": titulo[:120],
                            "distrito": None,
                            "lat": None,
                            "lon": None,
                            "titulo": titulo,
                            "url": page_url,
                            "pdf_url": pdf_url,
                            "source": "ayuntamiento",
                            "origen": "urbanismo_wp",
                            "nota": "Modelo/formulario informativo; no concesión publicada",
                        }
                    )
                elif RE_PROYECTO.search(blob) and not RE_EXCLUDE.search(blob):
                    rec: dict[str, Any] = {
                        "id": _stable_id("proy", pdf_url),
                        "municipio": MUNICIPIO,
                        "titulo": titulo,
                        "fecha": _parse_fecha_dmy(pdf_url),
                        "tipo": _proyecto_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "source": "ayuntamiento",
                        "origen": "urbanismo_wp",
                    }
                    self._enrich_geometry(rec)
                    proyectos.append(rec)
        return proyectos, licencias

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

    def _wfs_query(self, cql: str, count: int = 20) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "sitcm:VPLA_V_AMBITO",
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
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        if RE_EXCLUDE.search(title):
            return None

        cache = self._load_wfs_ambitos()
        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for m in RE_AMBIT_CODE.finditer(title):
            code = m.group(1).upper()
            feat = cache.get(code)
            if feat:
                candidates.append((100.0, code, feat))

        parts = _sector_ilike_parts(title)
        muni = self.wfs_municipio.replace("'", "''")
        if parts:
            pattern = "%" + "%".join(p.replace("'", "''") for p in parts[:6]) + "%"
            feats = self._wfs_query(
                f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '{pattern}'",
                count=10,
            )
            title_low = title.lower()
            for f in feats:
                name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "")
                if not name:
                    continue
                score = sum(5 for p in parts if p.lower() in name.lower())
                if name.lower() in title_low:
                    score += 30
                candidates.append((float(score), name, f))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_score, best_name, _ = candidates[0]
        if best_score < 5:
            return None

        same_name = [
            f
            for _, name, f in candidates
            if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "") == best_name
        ]
        merged = _merge_geometries(same_name or [candidates[0][2]])
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39)*2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}",
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": best_name,
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

    def _title_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80}|ordenanza.*licencia)", title)
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
        if RE_EXCLUDE.search(title):
            return None
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
        self._enrich_geometry(out)
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
        _, wp_lic = self._collect_wp_docs()
        for rec in wp_lic:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
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
        _, wp_lic = self._collect_wp_docs()
        for rec in wp_lic:
            existing[rec["id"]] = rec
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

        wp_proy, _ = self._collect_wp_docs()
        for rec in wp_proy:
            add(rec)
        for rec in self._collect_transparencia_proyectos():
            add(rec)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            add(self._title_to_proyecto(rec))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_docs": len(wp_proy),
            "tablon_items": sum(1 for r in rows if r.get("origen") == "tablon"),
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
