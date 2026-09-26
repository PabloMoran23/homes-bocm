from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_bbox, geometry_centroid, has_area_geometry, record_geometry

SEDE_BASE = "https://monachil.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
WEB_BASE = "https://monachil.es"
URBANISMO_URL = f"{WEB_BASE}/urbanismo"
GEOVISTAS_WFS = "https://app.geovistas.es/maps/wmsc/1695"
GEOVISTAS_NNSS = "https://app.geovistas.es/maps/widget/1695"
GEOVISTAS_INVENTARIO = "https://app.geovistas.es/maps/widget/1692"
SITUA_SEARCH = "https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf"
MUNICIPIO = "Monachil"
ID_PREFIX = "monachil"

WP_SEARCH_TERMS = (
    "estudio",
    "informaci",
    "planeam",
    "ordenanza",
    "obra",
    "parcela",
    "urban",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|establecimiento hosteler)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de ordenaci[oó]n)|memoria|planos|boja|bop|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|ordenanza|evaluaci[oó]n ambiental|geovistas|inventario)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"resoluci[oó]n convocatoria|cobranza iae|padrones)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://monachil\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_HREF = re.compile(r'href=["\']([^"\']+)["\']', re.I)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_SKIP_HREF = re.compile(
    r"(?i)(facebook|instagram|youtube|#|javascript:|politica-de-|aviso-legal|witcreativo|"
    r"feed|wp-json|favicon|comercio\.monachil)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,5}/\d{4})")


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"/(20\d{2})/(\d{2})/", url or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-01"
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{text} {url}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "nnss" in b or "normas subsidiarias" in b:
        return "normas subsidiarias"
    if "estudio de detalle" in b:
        return "estudio de detalle"
    if "estudio de ordenaci" in b:
        return "estudio de ordenación"
    if "evaluaci" in b and "ambiental" in b:
        return "evaluación ambiental"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "memoria" in b and ("avance" in b or "planeam" in b):
        return "memoria planeamiento"
    if "inventario" in b and "inmueble" in b:
        return "inventario patrimonio"
    if "licencia" in b:
        return "licencia publicada"
    if "planeam" in b or "pgou" in b:
        return "planeamiento"
    return "urbanismo"


class MonachilAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress monachil.es + sede espublico gestiona + GeoVistas RNNSS (WMS/WFS)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.geovistas_wfs = str(self.config.get("geovistas_wfs") or GEOVISTAS_WFS)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: dict[str, list[dict[str, Any]]] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-monachil/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-monachil/1.0"),
                "Accept": "application/json",
            },
        )
        with self._opener.open(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_web(self, href: str) -> str:
        href = unescape(href.replace("&amp;", "&"))
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    def _wfs_features(self, layer: str, count: int = 50) -> list[dict[str, Any]]:
        if layer in self._wfs_cache:
            return self._wfs_cache[layer]
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer,
                "outputFormat": "geojson",
                "srsName": "EPSG:4326",
                "count": str(count),
            }
        )
        url = f"{self.geovistas_wfs}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_cache[layer] = []
            return []
        feats = [f for f in (data.get("features") or []) if isinstance(f, dict)]
        self._wfs_cache[layer] = feats
        return feats

    def _largest_area_polygon(self, layer: str, count: int = 80) -> dict[str, Any] | None:
        best: dict[str, Any] | None = None
        best_area = -1.0
        for feat in self._wfs_features(layer, count=count):
            geom = feat.get("geometry")
            if not isinstance(geom, dict) or not has_area_geometry({"geom_geojson": geom}):
                continue
            bbox = geometry_bbox(geom)
            if not bbox:
                continue
            min_lng, min_lat, max_lng, max_lat = bbox
            area = abs(max_lng - min_lng) * abs(max_lat - min_lat)
            if area > best_area:
                best_area = area
                best = geom
        return best

    def _municipio_zoning_geom(self) -> dict[str, Any] | None:
        return self._largest_area_polygon("ms:Zonificacion", count=120)

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = f"{rec.get('titulo') or ''} {rec.get('tipo') or ''}".lower()
        origen = str(rec.get("origen") or "")

        if origen in {"geovistas", "situa", "web_urbanismo"} or "nnss" in blob or "geovistas" in blob:
            geom = self._municipio_zoning_geom()
            if geom:
                url = (
                    f"{self.geovistas_wfs}?service=WFS&version=2.0.0&request=GetFeature"
                    "&typeNames=ms:Zonificacion&outputFormat=geojson&srsName=EPSG:4326&count=120"
                )
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = url
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen
                return

        if "suelo urbano" in blob or "límite suelo" in blob:
            geom = self._municipio_zoning_geom()
            if geom:
                url = (
                    f"{self.geovistas_wfs}?service=WFS&version=2.0.0&request=GetFeature"
                    "&typeNames=ms:Zonificacion&outputFormat=geojson&srsName=EPSG:4326&count=120"
                )
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = url
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen

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
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictos publicados en espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo y licencias — sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y declaraciones responsables vía sede",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "declaración responsable ejecución de obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Modelos y tramitación declaraciones responsables de obra",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF en monachil.es/urbanismo",
                "origen": "web_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/transparency"),
                "fecha_concesion": None,
                "tipo": "portal transparencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia — información urbanística (5.1.5)",
                "url": f"{self.sede_base}/transparency",
                "source": "ayuntamiento",
                "nota": "Expedientes en información pública según BOP (carga dinámica)",
                "origen": "sede_transparencia",
            },
        ]

    def _collect_urbanismo_page(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(url: str, titulo: str, tipo: str | None = None, fecha: str | None = None) -> None:
            abs_url = self._abs_web(url)
            if abs_url in seen or RE_SKIP_HREF.search(abs_url):
                return
            blob = f"{titulo} {abs_url}"
            if not RE_PROYECTO.search(blob) and tipo is None:
                return
            seen.add(abs_url)
            rows.append(
                {
                    "url": abs_url,
                    "titulo": titulo[:500],
                    "tipo": tipo or _proyecto_tipo(blob),
                    "fecha": fecha or _fecha_from_blob(titulo, abs_url),
                    "blob": blob,
                    "origen": "web_urbanismo",
                }
            )

        add(
            GEOVISTAS_NNSS,
            "Mapa interactivo RNNSS (Normas Subsidiarias) — GeoVistas",
            "normas subsidiarias",
            "2000-01-01",
        )
        add(
            GEOVISTAS_INVENTARIO,
            "Inventario municipal de bienes inmuebles — visor GeoVistas",
            "inventario patrimonio",
            "2024-03-14",
        )
        add(
            SITUA_SEARCH,
            "Consulta planeamiento — SITUADIFUSION (Junta de Andalucía)",
            "planeamiento",
        )

        for m in RE_LINK.finditer(html):
            href = unescape(m.group(1).replace("&amp;", "&"))
            titulo = _strip_html(m.group(2))
            if not titulo or len(titulo) < 4:
                continue
            if href.startswith("#"):
                continue
            if RE_SKIP_HREF.search(href):
                continue
            abs_url = self._abs_web(href)
            if "geovistas" in abs_url or abs_url.endswith(".pdf") or "box.com" in abs_url or "dropbox" in abs_url:
                add(abs_url, titulo)

        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        seen_ids: set[int] = set()
        rows: list[dict[str, Any]] = []
        for term in WP_SEARCH_TERMS:
            page = 1
            while page <= 3:
                qs = urllib.parse.urlencode(
                    {
                        "search": term,
                        "per_page": "50",
                        "page": str(page),
                        "_fields": "id,link,title,date",
                    }
                )
                url = f"{self.web_base}/wp-json/wp/v2/posts?{qs}"
                try:
                    posts = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not posts:
                    break
                for post in posts:
                    pid = int(post.get("id") or 0)
                    if pid in seen_ids:
                        continue
                    seen_ids.add(pid)
                    titulo = _strip_html((post.get("title") or {}).get("rendered") or "")
                    link = str(post.get("link") or "")
                    fecha = str(post.get("date") or "")[:10] or None
                    blob = f"{titulo} {link}"
                    if RE_BOARD_NON_URBAN.search(blob):
                        continue
                    if not RE_PROYECTO.search(blob):
                        continue
                    if re.search(r"(?i)campamento urbano|desbroce de solares|espacio joven", blob):
                        continue
                    rows.append(
                        {
                            "url": link,
                            "titulo": titulo[:500],
                            "fecha": fecha,
                            "blob": blob,
                            "origen": "wp_noticia",
                        }
                    )
                page += 1
        return rows

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or ""):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and "planeamiento" not in (row.get("procedimiento") or "").lower():
            return None
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._enrich_geometry(rec)
        return rec

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("blob") or row.get("titulo") or ""
        expte_m = RE_EXPTE.search(blob)
        rec = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": expte_m.group(1) if expte_m else None,
            "origen": row.get("origen"),
        }
        if row.get("origen") == "geovistas" or "geovistas" in row.get("url", ""):
            rec["origen"] = "geovistas"
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") not in ("tablon",)),
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

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            rec = self._board_to_proyecto(item)
            if rec:
                add(rec)
        for item in self._collect_urbanismo_page():
            add(self._seed_to_proyecto(item))
        for item in self._collect_wp_posts():
            add(self._seed_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": sum(1 for r in rows if has_area_geometry(r)),
            "web_urbanismo": sum(1 for r in rows if r.get("origen") == "web_urbanismo"),
            "wp_noticia": sum(1 for r in rows if r.get("origen") == "wp_noticia"),
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
