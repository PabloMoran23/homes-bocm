from __future__ import annotations

import hashlib
import http.cookiejar
import io
import json
import re
import ssl
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.agullent.es"
SEDE_BASE = "https://agullent.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
MUNICIPIO = "Agullent"
ID_PREFIX = "agullent"

URBANISMO_URL = f"{WEB_BASE}/es/transparencia/urbanismo"
PUAM_URL = f"{WEB_BASE}/es/transparencia/plan-urbano-actuacion-municipal"
LISTADO_ANUNCIOS_URL = f"{WEB_BASE}/es/listado/anuncis-bans-i-edictes"
SHAPE_ZIP_URL = f"{WEB_BASE}/sites/www.agullent.es/files/SHAPE%20AGULLENT.zip"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    PUAM_URL,
    LISTADO_ANUNCIOS_URL,
    f"{WEB_BASE}/es/transparencia/anuncios-bandos-edictos",
    f"{WEB_BASE}/es/transparencia/convenios-urbanisticos",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|llicencia|licències|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|inicio de obra|"
    r"compatibilidad urban|ambiental funcionamiento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|urba)|pgou|puam|convenio|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental)|memoria|planos|fotovolt|planta solar|"
    r"central fotovoltaica|aprobaci[oó]n (?:inicial|definitiva)|consolidaci[oó]n|"
    r"normas subsidiarias|zonificaci[oó]n|clasificaci[oó]n del suelo)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|convocat[oò]ria de el ple|eleccions|"
    r"modificacions pressupost|auxiliar administrati|professor/a|borsa de treball|"
    r"premis millors expedients acad)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://agullent\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://www\.agullent\.es)?/sites/www\.agullent\.es/files/[^"]+\.(?:pdf|PDF))"',
    re.I,
)
RE_AVISO_HREF = re.compile(
    r'href="((?:https://www\.agullent\.es)?/es/(?:aviso|aviso-transparencia)/[^"#?]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_EXPEDIENTE_CODE = re.compile(r"(?i)(?:expedient|exp\.?|expte\.?)\s*[:.]?\s*([\d/_-]+)")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _abs_web_url(path: str) -> str:
    if path.startswith("http"):
        return path
    return f"{WEB_BASE}{path}"


def _merge_geometries(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for g in geoms:
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


class AgullentAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal portalesmunicipales + sede espublico gestiona + shapefile planeamiento."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.shape_zip_url = str(self.config.get("shape_zip_url") or SHAPE_ZIP_URL)
        local_shape = self.config.get("shape_local_path")
        if local_shape:
            self.shape_local_path = Path(str(local_shape))
        else:
            self.shape_local_path = (
                Path(__file__).resolve().parents[2]
                / "data/municipios/agullent/geometry/SHAPE_AGULLENT.zip"
            )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 24))
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._shape_cache: dict[str, dict[str, Any]] | None = None

    def _request_with_retry(self, url: str, timeout: int = 60) -> bytes:
        ua = self.config.get("user_agent", "poc-bocm-agullent/1.0")
        last_err: Exception | None = None
        for attempt in range(4):
            time.sleep(self.delay_s)
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    return resp.read()
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as exc:
                last_err = exc
                time.sleep(0.5 * (attempt + 1))
        raise urllib.error.URLError(last_err or "fetch failed")

    def _fetch(self, url: str) -> str:
        return self._request_with_retry(url, timeout=45).decode("utf-8", errors="replace")

    def _fetch_bytes(self, url: str) -> bytes:
        return self._request_with_retry(url, timeout=90)

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _shape_to_geojson(self, shape: Any, transformer: Any) -> dict[str, Any] | None:
        if not shape.points:
            return None
        parts = list(shape.parts) + [len(shape.points)]
        rings: list[list[list[float]]] = []
        for i in range(len(parts) - 1):
            ring: list[list[float]] = []
            for j in range(parts[i], parts[i + 1]):
                x, y = shape.points[j]
                lon, lat = transformer.transform(x, y)
                ring.append([lon, lat])
            if len(ring) >= 3:
                rings.append(ring)
        if not rings:
            return None
        if len(rings) == 1:
            return {"type": "Polygon", "coordinates": rings}
        return {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}

    def _load_shape_cache(self) -> dict[str, dict[str, Any]]:
        if self._shape_cache is not None:
            return self._shape_cache

        cache: dict[str, dict[str, Any]] = {}
        try:
            import shapefile  # pyshp
            from pyproj import Transformer
        except ImportError:
            self._shape_cache = cache
            return cache

        raw: bytes | None = None
        if self.shape_local_path.is_file():
            raw = self.shape_local_path.read_bytes()
        if raw is None:
            try:
                raw = self._fetch_bytes(self.shape_zip_url)
            except urllib.error.URLError:
                self._shape_cache = cache
                return cache

        transformer = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)
        try:
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    zf.extractall(tmp)
                shp_path = next(Path(tmp).rglob("*.shp"))
                reader = shapefile.Reader(str(shp_path))
        except (zipfile.BadZipFile, StopIteration, OSError, shapefile.ShapefileException):
            self._shape_cache = cache
            return cache

        grouped: dict[str, list[dict[str, Any]]] = {}
        meta: dict[str, dict[str, str]] = {}
        for sr in reader.iterShapeRecords():
            rec = sr.record.as_dict()
            exp = str(rec.get("expediente") or "").strip()
            if not exp:
                continue
            geom = self._shape_to_geojson(sr.shape, transformer)
            if geom:
                grouped.setdefault(exp, []).append(geom)
            if exp not in meta:
                meta[exp] = {
                    "denominaci": str(rec.get("denominaci") or "").strip(),
                    "clas_suelo": str(rec.get("clas_suelo") or "").strip(),
                    "zon_suelo": str(rec.get("zon_suelo") or "").strip(),
                }

        for exp, geoms in grouped.items():
            merged = _merge_geometries(geoms)
            if not merged:
                continue
            cache[exp] = {
                "geom_geojson": merged,
                "geometry_source": "portal_shapefile",
                "geometry_source_url": self.shape_zip_url,
                "coord_source": "portal_geometry_centroid",
                "denominaci": meta.get(exp, {}).get("denominaci"),
                "clas_suelo": meta.get(exp, {}).get("clas_suelo"),
                "zon_suelo": meta.get(exp, {}).get("zon_suelo"),
            }

        self._shape_cache = cache
        return cache

    def _geometry_for_expediente(self, expediente: str | None) -> dict[str, Any] | None:
        if not expediente:
            return None
        code = expediente.strip()
        cache = self._load_shape_cache()
        if code in cache:
            return dict(cache[code])
        for key, val in cache.items():
            if key.endswith(code) or code.endswith(key):
                return dict(val)
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        exp = str(rec.get("expte") or rec.get("expediente") or "")
        if not exp:
            m = RE_EXPEDIENTE_CODE.search(str(rec.get("titulo") or "") + " " + str(rec.get("url") or ""))
            if m:
                exp = m.group(1).replace("/", "").replace("_", "").strip()
        geom = self._geometry_for_expediente(exp)
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_shape_proyectos(self) -> list[dict[str, Any]]:
        cache = self._load_shape_cache()
        rows: list[dict[str, Any]] = []
        for exp, meta in cache.items():
            titulo = meta.get("denominaci") or f"Expediente urbanístico {exp}"
            zon = meta.get("zon_suelo") or ""
            if zon and zon not in titulo:
                titulo = f"{titulo} ({zon})"
            rec = {
                "id": _stable_id("proy", f"shape-{exp}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": "planeamiento",
                "url": self.shape_zip_url,
                "source": "ayuntamiento",
                "expte": exp,
                "origen": "shapefile",
                "geom_geojson": meta["geom_geojson"],
                "geometry_source": meta["geometry_source"],
                "geometry_source_url": meta["geometry_source_url"],
                "coord_source": meta["coord_source"],
            }
            centroid = geometry_centroid(meta["geom_geojson"])
            if centroid:
                rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

    def _collect_web_links(self) -> list[dict[str, Any]]:
        seen_urls: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(url: str, titulo: str, origen: str, tipo: str = "urbanismo") -> None:
            full = _abs_web_url(url)
            if full in seen_urls:
                return
            seen_urls.add(full)
            blob = f"{titulo} {full}"
            fecha = _fecha_from_blob(blob)
            rec = {
                "id": _stable_id("proy", full),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": tipo,
                "url": full,
                "source": "ayuntamiento",
                "origen": origen,
            }
            m = RE_EXPEDIENTE_CODE.search(blob)
            if m:
                rec["expte"] = m.group(1).replace("/", "").replace("_", "").strip()
            rows.append(rec)

        pages = list(self.seed_pages)
        aviso_pages: list[str] = []
        for page in pages[:self.max_crawl_pages]:
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                continue

            for m in RE_AVISO_HREF.finditer(html):
                path = m.group(1)
                aviso_url = path if path.startswith("http") else _abs_web_url(path)
                if aviso_url not in aviso_pages:
                    aviso_pages.append(aviso_url)

            for m in RE_PDF_HREF.finditer(html):
                pdf_path = m.group(1)
                pdf_url = _abs_web_url(pdf_path)
                titulo = unescape(Path(pdf_path.split("/files/", 1)[-1]).stem.replace("%20", " "))
                titulo = re.sub(r"[_-]+", " ", titulo).strip()
                if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                    continue
                tipo = "licencia" if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo) else "urbanismo"
                if "puam" in titulo.lower() or "pla urba" in titulo.lower():
                    tipo = "planeamiento"
                add(pdf_url, titulo, "web_pdf", tipo)

        for page in aviso_pages[:self.max_crawl_pages]:
            try:
                html = self._fetch(page)
            except urllib.error.URLError:
                titulo = page.rsplit("/", 1)[-1].replace("-", " ")
                if RE_PROYECTO.search(titulo) or RE_LICENCIA.search(titulo):
                    add(page, titulo, "web_aviso")
                continue
            h1 = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
            titulo = _strip_html(h1.group(1)) if h1 else page.rsplit("/", 1)[-1]
            if RE_PROYECTO.search(titulo) or RE_LICENCIA.search(titulo):
                add(page, titulo, "web_aviso")

        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Agullent",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos y anuncios en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — licencias y certificaciones",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Formularios licencias obra mayor/menor y actividades",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "llicencia", "urban", "actividad", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "ambiental" in proc or "ambiental" in blob.lower():
            tipo = "licencia ambiental"
        elif "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None

        tipo = "urbanismo"
        if re.search(r"(?i)planeamiento|puam|plan parcial", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)informaci[oó]n p[uú]blica|fotovolt", blob):
            tipo = "información pública"

        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._enrich_geometry(rec)
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
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_web_links():
            if item.get("tipo") != "licencia":
                continue
            lic = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": item.get("fecha"),
                "tipo": "licencia / anuncio",
                "distrito": None,
                "lat": item.get("lat"),
                "lon": item.get("lon"),
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": item.get("origen"),
            }
            if lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "web_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
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

        for rec in self._collect_shape_proyectos():
            add(rec)

        for item in self._collect_web_links():
            if item.get("tipo") == "licencia":
                continue
            self._enrich_geometry(item)
            add(item)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "shapefile": sum(1 for r in rows if r.get("origen") == "shapefile"),
            "web": sum(1 for r in rows if str(r.get("origen") or "").startswith("web")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
