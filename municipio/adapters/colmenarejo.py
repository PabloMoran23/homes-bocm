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

WP_BASE = "https://www.ayto-colmenarejo.com"
SEDE_BASE = "https://sede.ayto-colmenarejo.org/eAdmin"
TRANSP_BASE = "https://transparencia.ayto-colmenarejo.org"
MUNICIPIO = "Colmenarejo"
ID_PREFIX = "colmenarejo"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
OFICINA_TECNICA_URL = f"{WP_BASE}/?page_id=677"
NORMATIVA_URL = f"{WP_BASE}/?page_id=973"
LICENCIAS_URL = f"{WP_BASE}/?page_id=975"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "COLMENAREJO"

DEFAULT_SEED_PAGES: list[str] = [
    NORMATIVA_URL,
    OFICINA_TECNICA_URL,
    LICENCIAS_URL,
]

DEFAULT_SEARCH_TERMS = (
    "URBANISMO",
    "LICENCIA",
    "INFORMACION PUBLICA",
    "PLANEAMIENTO",
    "PGOU",
    "NNSS",
    "UE-",
    "SE-",
    "BANDO",
    "PARCELA",
    "APROBACION",
    "MODIFICACION",
)

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
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|instalaci|funcionamiento|apertura|segregaci)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"viabilidad urban|titulo habilitante|cambio de titularidad|obra (?:mayor|menor)|"
    r"impreso.*licencia|ordenanza.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"orden de ejecuci|modificaci[oó]n|estudio (?:ac[uú]stico|ambiental)|\b(?:ue|se|s)-\d|"
    r"proyecto de|catalogo|memoria|normas urban|bando.*parcela|parcela.*urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|jurado|selecci[oó]n de personal|"
    r"activaci[oó]n profesional|igualdad|bolsa|iae\b|subvenci[oó]n empleo)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|SE|UA|AD|AN|AI|PAU|SAU|S)-\d+[A-Z0-9.-]*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_expte(text: str) -> str | None:
    m = RE_EXPTE.search(text)
    return m.group(1).strip() if m else None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _fecha_from_url(url: str) -> str | None:
    m = re.search(r"/(?:uploads|upLoads)/(\d{4})/(\d{2})/", url, re.I)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _parse_fecha_dmy(Path(url).name.replace("-", " "))


def _pdf_url(sede_base: str, token: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(title: str, default: str = "urbanismo") -> str:
    n = title.lower()
    if re.search(r"\bue-\d+\b", n) or re.search(r"\bse-\d+\b", n):
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "nnss" in n or "normas subsidiarias" in n or "pgou" in n:
        return "planeamiento"
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "bando" in n:
        return "bando urbanístico"
    if "aprobaci" in n:
        return "aprobación"
    return default


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


def _sector_ilike_parts(text: str) -> list[str]:
    s = text.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio", " nnss", " colmenarejo"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()\"«»]+", low) if len(p) >= 3]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and not re.fullmatch(r"\d{4}", p):
            seen.add(k)
            out.append(p)
    return out[:10]


class ColmenarejoAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ayto-colmenarejo.com + sede eAdmin add4u tablón + SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-colmenarejo/1.0"),
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or (
                "iso-8859-1" if "Tablon.do" in url or "sede.ayto-colmenarejo" in url else "utf-8"
            )
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or self.wp_base + "/", href)

    def _parse_tablon_html(self, html: str) -> dict[str, dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _clean_title(title_raw)
            if not title or RE_EXCLUDE.search(title):
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            doc_token = doc_m.group(1) if doc_m else None
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title,
                "fecha_ini": fecha_ini,
                "url": detail_url,
                "expte": _parse_expte(title),
            }
            if doc_token:
                rec["pdf_url"] = _pdf_url(self.sede_base, doc_token)
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

    def _extract_seed_proyectos(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for m in re.finditer(r"<li[^>]*>(.*?</li>)", html, re.I | re.S):
            block = m.group(1)
            if ".pdf" not in block.lower():
                continue
            ul_m = re.search(r"^(.*?)<ul>(.*)</ul>\s*$", block, re.I | re.S)
            if not ul_m:
                continue
            title = _clean_title(re.sub(r"<[^>]+>", " ", ul_m.group(1)))
            pdfs = RE_PDF_HREF.findall(ul_m.group(2))
            if len(title) < 4 or not pdfs:
                continue
            pdf_url = self._abs_url(pdfs[0], page_url)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "id": _stable_id("proy", pdf_url),
                    "municipio": MUNICIPIO,
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(title) or _fecha_from_url(pdf_url),
                    "tipo": _proyecto_tipo(title),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "wp_seed",
                }
            )

        for m in re.finditer(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>([^<]*)</a>', html, re.I):
            pdf_url = self._abs_url(m.group(1), page_url)
            if pdf_url in seen:
                continue
            anchor = _clean_title(m.group(2))
            name = Path(pdf_url).name
            blob = f"{anchor} {name}".lower()
            if not any(
                k in blob
                for k in (
                    "bocm",
                    "normas",
                    "pgou",
                    "modific",
                    "planeam",
                    "nnss",
                    "acuerdo",
                    "ue-",
                    "se-",
                    "urban",
                    "catalogo",
                    "memoria",
                    "plano",
                    "ordenacion",
                    "invsnu",
                )
            ):
                continue
            title = anchor if len(anchor) > 8 else re.sub(r"[-_.]+", " ", name.replace(".pdf", ""))
            if len(title) < 5:
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "id": _stable_id("proy", pdf_url),
                    "municipio": MUNICIPIO,
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(title) or _fecha_from_url(pdf_url),
                    "tipo": _proyecto_tipo(title),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "wp_pdf",
                }
            )
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            rows.extend(self._extract_seed_proyectos(html, page_url))
        return rows

    def _collect_licencia_forms(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in (LICENCIAS_URL, NORMATIVA_URL):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in re.finditer(r'<a[^>]+href="([^"]+\.pdf)"[^>]*>([^<]*)</a>', html, re.I):
                pdf_url = self._abs_url(m.group(1), page_url)
                anchor = _clean_title(m.group(2))
                blob = f"{anchor} {pdf_url}".lower()
                if not RE_LICENCIA.search(blob) and not any(
                    k in blob for k in ("licencia", "declaracion", "impreso", "ordenanza reguladora")
                ):
                    continue
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                title = anchor if len(anchor) > 5 else re.sub(r"[-_.]+", " ", Path(pdf_url).stem)
                rows.append(
                    {
                        "id": _stable_id("lic", pdf_url),
                        "fecha_concesion": _fecha_from_url(pdf_url),
                        "tipo": title[:120],
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title,
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "source": "ayuntamiento",
                        "nota": "Modelo u ordenanza; no concesión publicada",
                        "origen": "wp_licencias",
                    }
                )
        info_pages = [
            (OFICINA_TECNICA_URL, "Oficina Técnica — licencias y expedientes urbanísticos"),
            (LICENCIAS_URL, "Licencias urbanísticas — documentación y modelos"),
            (TABLON_ALL, "Tablón de anuncios — sede electrónica"),
            (f"{self.sede_base}/Sede.do", "Sede electrónica — presentación de trámites"),
        ]
        for url, title in info_pages:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámites urbanísticos",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa",
                    "origen": "wp_info",
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": self.wfs_type,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "CQL_FILTER": cql,
            "maxFeatures": str(count),
        }
        url = f"{self.wfs_url}?{urllib.parse.urlencode(params)}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        return list((data or {}).get("features") or [])

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache[name.upper()] = f
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache[code_m.group(1).upper()] = f
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
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
        if not same_name:
            same_name = [candidates[0][2]]

        merged = _merge_geometries(same_name)
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39) * 2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
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

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        seen_names: set[str] = set()
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name or name.upper() in seen_names:
                continue
            seen_names.add(name.upper())
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": SITCM_VISOR_URL,
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

    def _title_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        if RE_PROYECTO.search(title) and not re.search(r"(?i)licencia", title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80}|declaraci[oó]n responsable)", title)
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
        for rec in self._collect_licencia_forms():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon_items": len(tablon),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            lic = self._title_to_licencia(rec)
            if lic:
                existing[lic["id"]] = lic
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
                self._enrich_geometry(rec)
                rows.append(rec)

        for rec in self._collect_sit_ambitos():
            add(rec)
        for rec in self._collect_seed_pages():
            add(rec)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            add(self._title_to_proyecto(rec))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_ambitos": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "seed_docs": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "tablon_items": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "status": "ok",
            "with_geometry": result.get("with_geometry", 0),
        }
