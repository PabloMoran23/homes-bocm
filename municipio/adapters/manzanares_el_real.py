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

WP_BASE = "https://manzanareselreal.es"
SEDE_BASE = "https://manzanareselreal.sedelectronica.es"
MUNICIPIO = "Manzanares el Real"
ID_PREFIX = "manzanares-el-real"

URBANISMO_URL = f"{WP_BASE}/ordenacion-del-territorio/urbanismo/"
BOARD_URL = f"{SEDE_BASE}/board"
NORMATIVA_DOSSIER = (
    f"{SEDE_BASE}/transparency/70fa3e9b-9aec-443a-9c20-882f0ecd03df/"
)
PGOU_SERVICE_URL = (
    f"{SEDE_BASE}/citizen-service/1b89ac11-06c5-41e5-bcfe-aa2b2a56b298"
)
WP_URBANISMO_API = f"{WP_BASE}/wp-json/wp/v2/posts?categories=41&per_page=100"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "MANZANARES EL REAL"

RE_PREVIEW = re.compile(
    r'href="(https://manzanareselreal\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_DOSSIER_LINK = re.compile(
    r'href="(https://manzanareselreal\.sedelectronica\.es/preview-document/[a-f0-9-]+)"'
    r'[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|domino|parcela|proyecto de actuaci|"
    r"estudio de detalle|modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|"
    r"edicto|bocm|ordenanza|delimitaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|plusvalia|basura|"
    r"residuos|vehiculos|igualdad|cineg[eé]t|festival|gymkana|concurso)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:P|UE|AD|AN|AI|PAU|S)-\d+[A-Z0-9-]*)\b",
)
RE_PLAN_PARCIAL = re.compile(r"(?i)\bP\.\s*(\d+)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    m = re.search(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "informaci" in n and "p[uú]blica" in n:
        return "información pública"
    if "pgou" in n or "plan general" in n:
        return "planeamiento"
    if "plan parcial" in n or re.search(r"\bp\.\s*\d+", n):
        return "plan parcial"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "domino" in n or "parcela" in n:
        return "expediente urbanístico"
    if "convenio" in n:
        return "convenio"
    return "urbanismo"


def _doc_tipo(name: str) -> str:
    return _proyecto_tipo(name)


def _sector_ilike_parts(text: str) -> list[str]:
    s = text.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio", " nnss", " plan parcial"):
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


class ManzanaresElRealAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Ganesa + sede eHome (espublico) + ámbitos SITCM WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.normativa_dossier = str(
            self.config.get("normativa_dossier") or NORMATIVA_DOSSIER
        )
        self.pgou_service_url = str(
            self.config.get("pgou_service_url") or PGOU_SERVICE_URL
        )
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get(
                    "user_agent", "poc-bocm-manzanares-el-real/1.0"
                )
            },
        )
        use_insecure = insecure if insecure is not None else self.sede_base in url
        if use_insecure:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, insecure: bool | None = None) -> Any:
        raw = self._fetch(url, insecure=insecure)
        if raw.startswith("\ufeff"):
            raw = raw.lstrip("\ufeff")
        return json.loads(raw)

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        body = tbody_m.group(1) if tbody_m else html
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", body, re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 4:
                continue
            link_m = re.search(
                r'href="(https://manzanareselreal\.sedelectronica\.es/preview-document/[^"]+)"',
                tr,
                re.I,
            )
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]) if len(cells) > 1 else "",
                    "procedimiento": _strip_html(cells[2]) if len(cells) > 2 else "",
                    "categoria": _strip_html(cells[3]) if len(cells) > 3 else "",
                    "descripcion": _strip_html(cells[4]) if len(cells) > 4 else "",
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])) if len(cells) > 5 else None,
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": "",
                    "categoria": "",
                    "descripcion": titulo,
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(self.board_url, insecure=True)
        except urllib.error.URLError:
            return []
        items = self._parse_board_table(html, "tablon_sede")
        if not items:
            items = self._parse_board_links(html, "tablon_sede")
        for rec in items:
            by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_normativa_dossier(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.normativa_dossier, insecure=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DOSSIER_LINK.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "tipo": _doc_tipo(titulo),
                    "origen": "transparencia_normativa",
                }
            )
        return rows

    def _collect_wp_urbanismo(self) -> list[dict[str, Any]]:
        try:
            posts = self._fetch_json(WP_URBANISMO_API, insecure=False)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(posts, list):
            return []
        rows: list[dict[str, Any]] = []
        for post in posts:
            if not isinstance(post, dict):
                continue
            title = str((post.get("title") or {}).get("rendered") or "")
            title = unescape(re.sub(r"<[^>]+>", "", title)).strip()
            if not title:
                continue
            link = str(post.get("link") or self.urbanismo_url)
            fecha = str(post.get("date") or "")[:10] or None
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": link,
                    "tipo": _proyecto_tipo(title),
                    "origen": "urbanismo_web",
                }
            )
        return rows

    def _collect_pgou_service(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "Aprobación inicial Plan General de Ordenación Urbana",
                "fecha": "2026-05-19",
                "url": self.pgou_service_url,
                "tipo": "planeamiento",
                "origen": "pgou_servicio_sede",
            }
        ]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "trámite licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — noticias y normativa",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Sección web urbanismo; trámites en sede electrónica",
                "origen": "urbanismo_web",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — solicitud de licencia urbanística",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes",
                "origen": "sede_tramites",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios vigentes en sede electrónica",
                "origen": "tablon_sede",
            },
        ]

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
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
            data = self._fetch_json(url, insecure=False)
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

        for m in RE_PLAN_PARCIAL.finditer(title):
            code = f"P-{m.group(1)}"
            feat = cache.get(code.upper())
            if feat:
                candidates.append((95.0, code, feat))

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
            titulo = f"{name}"
            if fig:
                titulo = f"{name} — {fig}"
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": self.normativa_dossier,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
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

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "documento urbanismo",
            "url": row.get("url") or key,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob):
            return None
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

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
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
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_tablon_sede"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
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

        for doc in self._collect_normativa_dossier():
            add(self._doc_to_proyecto(doc))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))
        for post in self._collect_wp_urbanismo():
            add(self._doc_to_proyecto(post))
        for pgou in self._collect_pgou_service():
            add(self._doc_to_proyecto(pgou))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "normativa": sum(1 for r in rows if r.get("origen") == "transparencia_normativa"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "web": sum(1 for r in rows if r.get("origen") == "urbanismo_web"),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
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
