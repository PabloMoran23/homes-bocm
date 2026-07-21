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

SEDE_BASE = "https://sede.villadelprado.es/eAdmin"
TRANSP_BASE = "https://transparencia.villadelprado.org"
WEB_BASE = "https://www.villadelprado.es"
URBANISMO_URL = f"{TRANSP_BASE}/index.php/urbanismo"
MUNICIPIO = "Villa del Prado"
ID_PREFIX = "villa-del-prado"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VILLA DEL PRADO"

TABLON_ALL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios"
TRAMITES_URL = f"{SEDE_BASE}/Registrar.do?action=inicioPortalTramites"

DEFAULT_SEARCH_TERMS = (
    "URBANISMO",
    "LICENCIA",
    "INFORMACION PUBLICA",
    "PLAN",
    "PGOU",
    "CONVENIO",
    "REPARCEL",
    "APROBACION",
    "PARCELACION",
    "HOYAS",
    "FLORIDA",
)

DEFAULT_TRAMITE_IDS = (5, 8)

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
    r"comunicaci[oó]n previa|primera ocupaci[oó]n|ordenanza.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva)|"
    r"orden de ejecuci|modificaci[oó]n|estudio (?:ac[uú]stico|ambiental)|parcelaci|"
    r"proyecto de|normas? subsidiarias|ponp|sector|bocm|hoyas|florida|nnss|suelo)",
)
RE_MODAL_TITLE = re.compile(
    r'id="modalInformacion(\d+)"[^>]*>.*?<h4[^>]*>([^<]+)',
    re.I | re.S,
)
RE_LINK = re.compile(
    r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM_DATE = re.compile(r"BOCM-(\d{4})(\d{2})(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SKIP_TITLE = re.compile(
    r"(?i)^(indice|cap[ií]tulos?|planos?|hojas?|de acuerdo|bocm)$",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|AD|AN|AI|PAU|S)-\d+[A-Z0-9-]*)\b",
)


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
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    t = re.sub(r"\s+", " ", t).strip()
    if t.lower().startswith("ver documento"):
        t = t[len("ver documento") :].strip()
    return t[:500]


def _strip_html(text: str) -> str:
    return _clean_title(text)


def _abs_url(base: str, href: str) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _doc_url(sede_base: str, code: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(code, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(title: str, url: str = "") -> str:
    blob = f"{title} {url}".lower()
    if "plan parcial" in blob or "sector 02" in blob or "la florida" in blob:
        return "plan parcial"
    if "plan especial" in blob or "nnss" in blob:
        return "plan especial"
    if "parcelaci" in blob or "hoyas" in blob:
        return "parcelación"
    if "normas subsidiarias" in blob or "pgou" in blob or "ordenacion" in blob:
        return "planeamiento"
    if "informaci" in blob:
        return "información pública"
    if "aprobaci" in blob:
        return "aprobación"
    if "bocm" in blob:
        return "publicación BOCM"
    if "estudio" in blob:
        return "estudio"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    s = text.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio", " plano", " sector"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()]+", low) if len(p) >= 3]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and not re.fullmatch(r"\d{4}", p):
            seen.add(k)
            out.append(p)
    return out[:10]


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


class VillaDelPradoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede eAdmin (tablón + trámites) + transparencia Joomla (planeamiento PDFs)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transparencia_base") or TRANSP_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.search_terms = list(self.config.get("search_terms") or DEFAULT_SEARCH_TERMS)
        self.tramite_ids = [int(x) for x in (self.config.get("tramite_ids") or DEFAULT_TRAMITE_IDS)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "iso-8859-1"
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

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
                rec["pdf_url"] = _doc_url(doc_token, self.sede_base)
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

    def _is_proyecto_link(self, href: str, title: str) -> bool:
        if RE_SKIP_TITLE.match(title.strip()):
            return False
        blob = f"{title} {href}"
        if not RE_PROYECTO.search(blob):
            return False
        if title.strip().lower() in {"bocm", "planos", "indice", "de acuerdo"}:
            return False
        return True

    def _collect_transparencia_proyectos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_LINK.finditer(html):
            href_raw, anchor_raw = m.group(1), m.group(2)
            href = _abs_url(self.transp_base, href_raw)
            title = _strip_html(anchor_raw)
            if not title or len(title) < 4:
                continue
            if not self._is_proyecto_link(href, title):
                continue
            key = href
            if key in seen:
                continue
            seen.add(key)
            pdf_url = href if href.lower().endswith(".pdf") else None
            rows.append(
                {
                    "id": _stable_id("proy", key),
                    "municipio": MUNICIPIO,
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(f"{title} {href}"),
                    "tipo": _proyecto_tipo(title, href),
                    "url": self.urbanismo_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "transparencia_urbanismo",
                }
            )
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

    def _wfs_query(self, cql: str, count: int = 20) -> list[dict[str, Any]]:
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
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
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

        keywords = [
            w
            for w in re.findall(r"[a-záéíóúñ]{5,}", title.lower())
            if w not in {"anuncio", "aprob", "definitiva", "inicial", "expediente", "comunidad", "memoria", "plano", "parcial", "sector"}
        ]
        for kw in keywords[:4]:
            feats = self._wfs_query(
                f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '%{kw.replace(chr(39), chr(39)*2)}%'",
                count=5,
            )
            for f in feats:
                name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "")
                if name:
                    score = 8.0 if kw in name.lower() else 4.0
                    candidates.append((score, name, f))

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
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39)*2)}'"
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

    def _title_to_licencia(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        title = rec["titulo"]
        if not RE_LICENCIA.search(title):
            return None
        tipo_m = re.search(r"(?i)(licencia[^,]{0,80}|comunicaci[oó]n previa[^,]{0,80})", title)
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
            self._enrich_geometry(rec)
            add(rec)
        tablon = self._collect_tablon()
        for rec in tablon.values():
            add(self._title_to_proyecto(rec))

        self._write_jsonl(out_jsonl, rows)
        transp = sum(1 for r in rows if r.get("origen") != "tablon")
        return {
            "rows": len(rows),
            "status": "ok",
            "transparencia_docs": transp,
            "tablon_items": len(rows) - transp,
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
