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
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.castrillodelval.es"
SEDE_BASE = "https://castrillodelval.sedelectronica.es"
MUNICIPIO = "Castrillo del Val"
ID_PREFIX = "castrillo-del-val"

WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
WFS_C_MUN = "09086"
WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_PLANPUBLICA_SEEDS: list[tuple[str, str]] = [
    (
        "https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=S&provincia=9&municipio=086",
        "Planeamiento en información pública (Junta CYL)",
    ),
    (
        "https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=9&municipio=086",
        "Archivo planeamiento urbanístico aprobado (Junta CYL)",
    ),
]

RE_PREVIEW = re.compile(
    r'href="(?:https://castrillodelval\.sedelectronica\.es)?/preview-document/([a-f0-9-]+)"',
    re.I,
)
RE_TRANSPARENCY = re.compile(
    r'href="(?:https://castrillodelval\.sedelectronica\.es)?(/transparency/[a-f0-9-]+/?)"',
    re.I,
)
RE_NOTICIA = re.compile(r'href="(/noticia/[^"]+)"', re.I)
RE_PLANPUBLICA_ROW = re.compile(
    r"<tr[^>]*>(.*?)</tr>",
    re.S | re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|lic\.\s*urb|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"impuesto sobre construcciones)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|normas urban|modificaci[oó]n|"
    r"informaci[oó]n p[uú]blica|expediente|expdte|expte|proyecto de actuaci|estudio de detalle|"
    r"aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|actuaci[oó]n urban|"
    r"ocupaci[oó]n|enajenaci[oó]n|instrumento|planos|memoria|bocyl|nnss|num\b|ordenanza fiscal)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(presupuest|pleno|acta del pleno|subvenci[oó]n|empleo|meteorol[oó]g|"
    r"piscina|vuelta burgos|bascula|bonos transporte|sodebur|incendio forestal|"
    r"reglamento de administraci[oó]n electr[oó]nica|ludoteca|cursos deportivos|"
    r"compostaje|telefono cita)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ES = re.compile(r"(\d{1,2})\s+\w+,\s+(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)</h1>", re.I)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    iso = _parse_fecha_iso(text)
    if iso:
        return iso
    m = RE_FECHA_ES.search(text or "")
    if m:
        try:
            return datetime(int(m.group(2)), 8, int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and ("puntual" in n or "nnss" in n or "num" in n):
        return "modificación puntual NNSS"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "plan parcial" in n or "pp-" in n:
        return "plan parcial"
    if "sector" in n:
        return "sector"
    if "ordenanza fiscal" in n and "construcc" in n:
        return "ordenanza fiscal construcciones"
    if "ocupaci" in n:
        return "ocupación / expropiación"
    if "lic" in n and "urb" in n:
        return "licencia urbanística"
    if "planeam" in n or "pgou" in n:
        return "planeamiento"
    return "urbanismo"


class CastrilloDelValAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal Toools + sede espublico tablón + PlanPublica CyL + IDECyL WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        raw_seeds = self.config.get("seed_urls") or DEFAULT_PLANPUBLICA_SEEDS
        self.seed_urls: list[tuple[str, str]] = []
        for item in raw_seeds:
            if isinstance(item, dict):
                self.seed_urls.append((str(item["url"]), str(item.get("titulo") or item["url"])))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                self.seed_urls.append((str(item[0]), str(item[1])))
            else:
                self.seed_urls.append((str(item), str(item)))
        self.transparency_seeds = [
            str(u) for u in (self.config.get("transparency_seeds") or [])
        ]
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_c_mun = str(self.config.get("wfs_c_mun") or WFS_C_MUN)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-castrillo-del-val/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _preview_url(self, doc_id: str) -> str:
        return f"{self.sede_base}/preview-document/{doc_id}"

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "120",
                "CQL_FILTER": f"c_mun = '{self.wfs_c_mun}'",
            }
        )
        return f"{self.wfs_base}?{params}"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        for layer, default_tipo in WFS_LAYERS:
            url = self._wfs_query_url(layer)
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                titulo = _strip_html(str(props.get("n_titulo") or ""))
                if not titulo:
                    sector = str(props.get("n_sector") or "").strip()
                    num = str(props.get("n_num_sect") or "").strip()
                    titulo = f"{sector} ({num})" if sector else num
                if not titulo:
                    titulo = str(props.get("c_id_sect") or props.get("c_plan") or layer)
                instrum = str(props.get("n_instrum") or props.get("c_instrum") or "")
                blob = f"{titulo} {instrum}"
                fecha = _parse_fecha_iso(str(props.get("f_bocyl") or "")) or _parse_fecha_iso(
                    str(props.get("f_aprob") or "")
                )
                doc_url = str(props.get("url_doc_info") or "").strip() or url
                key = str(props.get("c_id_sect") or props.get("c_plan") or props.get("fid") or titulo)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"wfs:{layer}:{key}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(blob) if blob.strip() else default_tipo,
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "origen": "idecyl_wfs",
                    "wfs_layer": layer,
                    "sector_id": props.get("c_id_sect"),
                    "instrumento": instrum or None,
                }
                if isinstance(geom, dict) and geom.get("type"):
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
        self._wfs_cache = rows
        return rows

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = f"{rec.get('titulo') or ''} {rec.get('expte') or ''}".lower()
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            if blob and wfs_title and (blob in wfs_title or wfs_title in blob):
                self._copy_geometry(wfs_rec, rec)
                return
        for token in re.split(r"[\s,/()-]+", blob):
            if len(token) < 4:
                continue
            for wfs_rec in self._collect_wfs_proyectos():
                wfs_title = str(wfs_rec.get("titulo") or "").lower()
                if token in wfs_title:
                    self._copy_geometry(wfs_rec, rec)
                    return

    @staticmethod
    def _copy_geometry(src: dict[str, Any], dst: dict[str, Any]) -> None:
        for key in (
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if src.get(key) is not None:
                dst[key] = src[key]

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            url = self._preview_url(link_m.group(1)) if link_m else self.board_url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": _strip_html(cells[4]),
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
                    "url": url,
                    "pdf_url": url if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board_table(html, "tablon")

    def _parse_transparency_docs(self, html: str, folder_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = [_strip_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            link_m = RE_PREVIEW.search(tr)
            if not link_m:
                continue
            titulo = cells[0] if cells else ""
            if not titulo:
                continue
            url = self._preview_url(link_m.group(1))
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "folder_url": folder_url,
                    "origen": "transparencia",
                }
            )
        return rows

    def _collect_transparency(self, seed_urls: list[str]) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        seen_folders: set[str] = set()
        for seed in seed_urls:
            folder = seed if seed.startswith("http") else f"{self.sede_base}{seed}"
            if folder in seen_folders:
                continue
            seen_folders.add(folder)
            try:
                html = self._fetch(folder)
            except urllib.error.URLError:
                continue
            for rec in self._parse_transparency_docs(html, folder):
                by_url[rec["url"]] = rec
            for m in RE_TRANSPARENCY.finditer(html):
                sub = m.group(1)
                sub_url = sub if sub.startswith("http") else f"{self.sede_base}{sub}"
                if sub_url in seen_folders:
                    continue
                seen_folders.add(sub_url)
                try:
                    sub_html = self._fetch(sub_url)
                except urllib.error.URLError:
                    continue
                for rec in self._parse_transparency_docs(sub_html, sub_url):
                    by_url[rec["url"]] = rec
        return list(by_url.values())

    def _parse_planpublica(self, html: str, seed_url: str, seed_titulo: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in RE_PLANPUBLICA_ROW.findall(html):
            if "titulo" not in tr.lower() and "instrumento" not in tr.lower():
                continue
            cells = [_strip_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) < 3:
                continue
            blob = " ".join(cells)
            if not RE_PROYECTO.search(blob):
                continue
            titulo = cells[-1] if cells else blob
            if len(titulo) < 8:
                continue
            fecha = _fecha_from_blob(blob)
            key = f"planpublica:{seed_url}:{titulo}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": seed_url,
                    "origen": "planpublica",
                    "seed_titulo": seed_titulo,
                    "blob": blob[:500],
                }
            )
        return rows

    def _collect_planpublica(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for url, titulo in self.seed_urls:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for rec in self._parse_planpublica(html, url, titulo):
                key = rec["titulo"]
                by_key[key] = rec
        return list(by_key.values())

    def _collect_noticia_links(self) -> list[str]:
        try:
            html = self._fetch(f"{WEB_BASE}/noticias")
        except urllib.error.URLError:
            return []
        links = sorted({m.group(1) for m in RE_NOTICIA.finditer(html)})
        return [urllib.parse.urljoin(f"{WEB_BASE}/", path) for path in links]

    def _parse_noticia(self, url: str) -> dict[str, Any] | None:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return None
        h1_m = RE_H1.search(html)
        titulo = unescape(h1_m.group(1).strip()) if h1_m else ""
        if not titulo:
            return None
        fecha = _fecha_from_blob(html) or _fecha_from_blob(titulo)
        expte_m = RE_EXPTE.search(titulo) or RE_EXPTE.search(_strip_html(html))
        transparency_urls = [
            f"{self.sede_base}{m.group(1)}" for m in RE_TRANSPARENCY.finditer(html)
        ]
        return {
            "titulo": titulo[:500],
            "fecha": fecha,
            "url": url,
            "expte": expte_m.group(1) if expte_m else None,
            "transparency_urls": transparency_urls,
            "origen": "drupal_noticia",
        }

    def _collect_noticias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._collect_noticia_links():
            rec = self._parse_noticia(url)
            if not rec:
                continue
            blob = rec["titulo"]
            if RE_EXCLUDE.search(blob):
                continue
            if not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
                continue
            rows.append(rec)
        return rows

    def _all_transparency_seeds(self, noticias: list[dict[str, Any]]) -> list[str]:
        seeds = list(self.transparency_seeds)
        for rec in noticias:
            seeds.extend(rec.get("transparency_urls") or [])
        return list(dict.fromkeys(seeds))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if not RE_LICENCIA.search(blob):
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
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _noticia_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        key = row.get("expte") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia urbanística",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expte"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _transparency_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        key = row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "pdf_url": row.get("pdf_url"),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob):
            return None
        is_urbanismo = row.get("categoria", "").lower() in ("urbanismo", "anuncios")
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob) and not is_urbanismo:
            return None
        if not is_urbanismo and not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _planpublica_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo') or ''} {row.get('blob') or ''}"
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["titulo"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "seed_titulo": row.get("seed_titulo"),
        }
        self._enrich_geometry(rec)
        return rec

    def _noticia_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if RE_LICENCIA.search(row["titulo"]) and not RE_PROYECTO.search(row["titulo"]):
            return None
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        key = row.get("expte") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expte"),
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "pdf_url": row.get("pdf_url"),
            "folder_url": row.get("folder_url"),
        }
        expte_m = RE_EXPTE.search(blob)
        if expte_m:
            rec["expte"] = expte_m.group(1)
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
        noticias = self._collect_noticias()
        transparency_seeds = self._all_transparency_seeds(noticias)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_transparency(transparency_seeds):
            rec = self._transparency_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in noticias:
            rec = self._noticia_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "noticias": sum(1 for r in rows if r.get("origen") == "drupal_noticia"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
        added = after - before
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, added),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, added), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        noticias = self._collect_noticias()
        transparency_seeds = self._all_transparency_seeds(noticias)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_transparency(transparency_seeds):
            add(self._transparency_to_proyecto(item))
        for item in noticias:
            add(self._noticia_to_proyecto(item))
        for item in self._collect_planpublica():
            add(self._planpublica_to_proyecto(item))
        for item in self._collect_wfs_proyectos():
            add(item)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "noticias": sum(1 for r in rows if r.get("origen") == "drupal_noticia"),
            "planpublica": sum(1 for r in rows if r.get("origen") == "planpublica"),
            "idecyl_wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
