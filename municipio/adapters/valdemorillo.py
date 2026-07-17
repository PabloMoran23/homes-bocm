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

WP_BASE = "https://aytovaldemorillo.com"
SEDE_BASE = "https://aytovaldemorillo.sedelectronica.es"
MUNICIPIO = "Valdemorillo"
ID_PREFIX = "valdemorillo"

URBANISMO_PAGE_ID = 31606
URBANISMO_URL = f"{WP_BASE}/urbanismo/"
BOARD_URL = f"{SEDE_BASE}/board/"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VALDEMORILLO"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"licencia de obra|licencia de alineaci[oó]n|licencia de segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|parcela|suelo|normas subsidiarias|"
    r"nnss|unidad(?:es)? de actuaci[oó]n|\b(?:UA|SAU|UE|AD)-\d+)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://aytovaldemorillo\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="(https://aytovaldemorillo\.com/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://aytovaldemorillo\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_AMBIT_CODE = re.compile(r"(?i)\b((?:UA|SAU|UE|AD)-\d+[A-Z0-9-]*)\b")
RE_BOCM_DATE = re.compile(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _doc_tipo(name: str) -> str:
    n = name.lower()
    if "nnss" in n or "normas subsidiarias" in n or "nurbanisticas" in n:
        return "normas subsidiarias"
    if "pgou" in n or "avance" in n:
        return "PGOU"
    if "memoria" in n:
        return "memoria PGOU"
    if "indice" in n or "índice" in n:
        return "índice PGOU"
    if "plano" in n:
        return "planos PGOU"
    if "acuerdo" in n:
        return "acuerdo pleno"
    if "catalogo" in n or "catálogo" in n:
        return "catálogo PGOU"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    return "documento urbanismo"


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


class ValdemorilloAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor + sede eHome (mantenimiento jul-2026) + SITCM WFS ámbitos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.urbanismo_page_id = int(self.config.get("urbanismo_page_id") or URBANISMO_PAGE_ID)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valdemorillo/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _urbanismo_html(self) -> str:
        try:
            page = self._fetch_json(f"{WP_BASE}/wp-json/wp/v2/pages/{self.urbanismo_page_id}")
            return str(page.get("content", {}).get("rendered") or "")
        except (urllib.error.URLError, json.JSONDecodeError, KeyError):
            try:
                return self._fetch(self.urbanismo_url)
            except urllib.error.URLError:
                return ""

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
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
        self._wfs_cache = cache
        return cache

    def _geometry_from_feature(self, feat: dict[str, Any], name: str) -> dict[str, Any] | None:
        merged = _merge_geometries([feat])
        if not merged:
            return None
        muni = self.wfs_municipio.replace("'", "''")
        safe_name = name.replace("'", "''")
        cql = f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB='{safe_name}'"
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
        }

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        cache = self._load_wfs_ambitos()
        for m in RE_AMBIT_CODE.finditer(titulo or ""):
            feat = cache.get(m.group(1).upper())
            if feat:
                name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "")
                geom = self._geometry_from_feature(feat, name)
                if geom:
                    return geom
        title_low = (titulo or "").lower()
        for key, feat in cache.items():
            if len(key) < 4 or key.startswith(("UA", "SAU", "UE", "AD")):
                continue
            if key.lower() in title_low:
                name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or key)
                geom = self._geometry_from_feature(feat, name)
                if geom:
                    return geom
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            centroid = geometry_centroid(geom["geom_geojson"])
            if centroid and not rec.get("lat"):
                rec["lat"], rec["lon"] = centroid

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        if "mantenimiento" in html.lower() or "indeterminada" in html.lower():
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            cells = [_strip_html(c) for c in RE_BOARD_CELL.findall(row_html)]
            cells = [c for c in cells if c]
            if len(cells) < 4 or cells[0] in ("Documento", "Expediente"):
                continue
            documento = cells[0]
            expediente = cells[1] if len(cells) > 1 else ""
            procedimiento = cells[2] if len(cells) > 2 else ""
            descripcion = cells[4] if len(cells) > 4 else documento
            fecha_raw = cells[5] if len(cells) > 5 else ""
            preview_m = RE_PREVIEW_LINK.search(row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            titulo = descripcion or documento
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"
            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": f"{documento} {expediente} {procedimiento} {descripcion}",
                }
            )
        return rows

    def _collect_urbanismo_pdfs(self) -> list[dict[str, Any]]:
        html = self._urbanismo_html()
        if not html:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            pdf = m.group(1)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            if not RE_PROYECTO.search(name) and "urban" not in name.lower():
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("proy", pdf),
                "municipio": MUNICIPIO,
                "titulo": f"Valdemorillo urbanismo: {name}"[:500],
                "fecha": _fecha_from_blob(pdf) or "2022-02-01",
                "tipo": _doc_tipo(name),
                "url": self.urbanismo_url,
                "pdf_url": pdf,
                "source": "ayuntamiento",
                "origen": "wp_urbanismo",
            }
            self._attach_geometry(rec)
            rows.append(rec)
        return rows

    def _collect_pgou_media(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for term in ("pgou", "bando", "nnss", "nurbanisticas"):
            try:
                items = self._fetch_json(
                    f"{WP_BASE}/wp-json/wp/v2/media?search={urllib.parse.quote(term)}&per_page=50"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(items, list):
                continue
            for item in items:
                url = str(item.get("source_url") or "")
                if not url.lower().endswith(".pdf") or url in seen:
                    continue
                title = str((item.get("title") or {}).get("rendered") or Path(url).name)
                if not RE_PROYECTO.search(f"{title} {url}"):
                    continue
                seen.add(url)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": unescape(title)[:500],
                    "fecha": _fecha_from_blob(url) or _fecha_from_blob(title) or "2026-05-22",
                    "tipo": _doc_tipo(title),
                    "url": self.urbanismo_url,
                    "pdf_url": url,
                    "source": "ayuntamiento",
                    "origen": "wp_media",
                }
                self._attach_geometry(rec)
                rows.append(rec)
        return rows

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for feat in feats:
            props = feat.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name or name.upper() in seen:
                continue
            seen.add(name.upper())
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs:{name}"),
                "municipio": MUNICIPIO,
                "titulo": f"Ámbito planeamiento: {name}"[:500],
                "fecha": None,
                "tipo": "unidad de actuación",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "origen": "sitcm_wfs",
            }
            geom = self._geometry_from_feature(feat, name)
            if geom:
                rec.update(geom)
                centroid = geometry_centroid(geom["geom_geojson"])
                if centroid:
                    rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        html = self._urbanismo_html()
        rows: list[dict[str, Any]] = []
        for m in RE_CATALOG.finditer(html):
            url, title = m.group(1), _strip_html(m.group(2))
            if not title:
                continue
            rows.append(
                {
                    "url": url,
                    "titulo": title[:500],
                    "blob": title,
                }
            )
        return rows

    def _catalog_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        tipo = "trámite licencia"
        if re.search(r"(?i)declaraci[oó]n responsable", blob):
            tipo = "declaración responsable"
        elif re.search(r"(?i)obra mayor", blob):
            tipo = "licencia obra mayor"
        elif re.search(r"(?i)obra menor", blob):
            tipo = "licencia obra menor"
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_catalogo",
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sede",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": "urbanismo",
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": "tablon_sede",
        }
        self._attach_geometry(rec)
        return rec

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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for row in self._collect_catalog_tramites():
            rec = self._catalog_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        if not rows:
            rows.append(
                {
                    "id": _stable_id("lic", self.urbanismo_url),
                    "fecha_concesion": None,
                    "tipo": "trámites urbanismo (formularios)",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Formularios y trámites de licencia (Urbanismo)",
                    "url": self.urbanismo_url,
                    "source": "ayuntamiento",
                    "nota": "Catálogo sede en mantenimiento jul-2026; enlaces en web municipal",
                }
            )
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "catalog_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for rec in self._collect_urbanismo_pdfs():
            add(rec)
        for rec in self._collect_pgou_media():
            add(rec)
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs_ambitos": sum(1 for r in rows if r.get("origen") == "sitcm_wfs"),
            "wp_docs": sum(1 for r in rows if r.get("origen", "").startswith("wp")),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
