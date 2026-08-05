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

WP_BASE = "https://www.torresdelaalameda.org"
SEDE_BASE = "https://torresdelaalameda.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
URBANISMO_URL = f"{WP_BASE}/concejalias/concejalia-de-urbanismo-vias-y-obras/tramites-urbanismo/"
LICENCIAS_URL = f"{WP_BASE}/concejalias/concejalia-de-urbanismo-vias-y-obras/licencias/"
PGOU_URL = f"{WP_BASE}/pgou-torres-de-la-alameda/"
DEPARTAMENTO_URL = f"{WP_BASE}/concejalias/concejalia-de-urbanismo-vias-y-obras/departamento-de-urbanismo/"
CATALOG_URL = f"{SEDE_BASE}/catalog/t/e5deabcc-f0c5-455a-9bec-47304aa7f36c"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"
MUNICIPIO = "Torres de la Alameda"
ID_PREFIX = "torres-de-la-alameda"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "TORRES DE LA ALAMEDA"

DEFAULT_WP_CATEGORIES = (40,)

RE_PREVIEW = re.compile(
    r'href="(https://torresdelaalameda\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|cedula urban|c[eé]dula urban|ocupaci[oó]n.*dominio)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|parcela|bando|unidad(?:es)? de ejecuci[oó]n|desarrollo urban|"
    r"live!|cordish|participaci[oó]n ciudadana.*urban|"
    r"\b(?:UE|AD|AN|AI|PAU|S|UA|SAU)-\d+[A-Z0-9-]*\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(convocatoria.*pleno|sesi[oó]n ordinaria.*pleno|pleno.*convocatoria|"
    r"junta de gobierno|comisi[oó]n informativa|comisi[oó]n especial de cuentas|"
    r"padr[oó]n|presupuest|empleo|jurado|selecci[oó]n de personal|"
    r"activaci[oó]n profesional|igualdad|bolsa|matrimonio|boda|tribut|personal|"
    r"modificaci[oó]n.*cr[eé]dito|plan estrat[eé]gico.*recursos humanos)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|AD|AN|AI|PAU|S|UA|SAU)-\d+[A-Z0-9-]*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


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


def _iso_date_wp(text: str) -> str | None:
    if not text:
        return None
    try:
        return text[:10]
    except (TypeError, IndexError):
        return None


def _fecha_from_url(url: str) -> str | None:
    m = re.search(r"/(\d{4})[./-](\d{2})[./-]", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _parse_fecha_dmy(Path(url).name)


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bua-\d+\b", n) or "unidad de actuaci" in n:
        return "unidad de actuación"
    if re.search(r"\bsau-\d+\b", n) or "sector" in n:
        return "sector"
    if re.search(r"\bue-\d+\b", n) or "unidad de ejecuci" in n:
        return "unidad de ejecución"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "pgou" in n or "planeamiento" in n:
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "bando" in n:
        return "bando urbanístico"
    if "participaci" in n:
        return "participación ciudadana"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del ", " de torres"):
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


class TorresDeLaAlamedaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress torresdelaalameda.org + sede espublico + ámbitos SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.licencias_url = str(self.config.get("licencias_url") or LICENCIAS_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.catalog_url = str(self.config.get("catalog_url") or CATALOG_URL)
        raw_cats = self.config.get("wp_category_ids") or list(DEFAULT_WP_CATEGORIES)
        self.wp_category_ids = [int(c) for c in raw_cats]
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

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        use_insecure = self.config.get("insecure_ssl", True) if insecure is None else insecure
        ctx = self._ssl_ctx if use_insecure else ssl.create_default_context()
        opener = (
            self._opener
            if use_insecure
            else urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx))
        )
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-torres-de-la-alameda/1.0")},
        )
        with opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str, *, insecure: bool | None = None) -> Any:
        return json.loads(self._fetch(url, insecure=insecure))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_wp(m.group(1))
            if "favicon" in u.lower() or "logo" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = [_strip_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) < 4:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or cells[0]
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": cells[1] if len(cells) > 1 else "",
                    "procedimiento": cells[2] if len(cells) > 2 else "",
                    "categoria": cells[3] if len(cells) > 3 else "",
                    "descripcion": cells[4] if len(cells) > 4 else "",
                    "fecha": _parse_fecha_dmy(cells[5]) if len(cells) > 5 else None,
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": "sede_board",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board(html)

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_links: set[str] = set()
        for cat_id in self.wp_category_ids:
            page = 1
            while page <= 5:
                url = f"{self.wp_base}/wp-json/wp/v2/posts?categories={cat_id}&per_page=100&page={page}"
                try:
                    posts = self._fetch_json(url, insecure=False)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(posts, list) or not posts:
                    break
                for post in posts:
                    link = str(post.get("link") or "").strip()
                    if not link or link in seen_links:
                        continue
                    seen_links.add(link)
                    title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                    content = str((post.get("content") or {}).get("rendered") or "")
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": _iso_date_wp(str(post.get("date") or "")),
                            "url": link,
                            "pdfs": self._extract_pdfs(content),
                            "origen": f"wp_cat_{cat_id}",
                        }
                    )
                if len(posts) < 100:
                    break
                page += 1
        return rows

    def _collect_pgou_seed(self) -> list[dict[str, Any]]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", "pgou-torres"),
            "municipio": MUNICIPIO,
            "titulo": "Plan General de Ordenación Urbana (PGOU) — Torres de la Alameda",
            "fecha": "2021-11-12",
            "tipo": "planeamiento",
            "url": self.pgou_url,
            "source": "ayuntamiento",
            "origen": "wp_pgou",
            "nota": "Documentación y participación ciudadana en web municipal; ámbitos en SITCM",
        }
        self._enrich_geometry(rec)
        return [rec]

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "trámites urbanísticos",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias y trámites de Urbanismo",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Información sobre licencias, DR, comunicaciones y fianzas",
                "origen": "wp_urbanismo",
            },
            {
                "id": _stable_id("lic", self.licencias_url),
                "fecha_concesion": None,
                "tipo": "licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias — Concejalía de Urbanismo",
                "url": self.licencias_url,
                "source": "ayuntamiento",
                "nota": "Guía de procedimientos de licencias",
                "origen": "wp_licencias",
            },
            {
                "id": _stable_id("lic", self.catalog_url),
                "fecha_concesion": None,
                "tipo": "catálogo trámites sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites urbanísticos — sede electrónica",
                "url": self.catalog_url,
                "source": "ayuntamiento",
                "nota": "Presentación telemática de solicitudes",
                "origen": "sede_catalog",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y edictos publicados en sede",
                "origen": "sede_tablon",
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
            code = str(props.get("DS_COD_AMB") or "").strip()
            if name:
                cache[name.upper()] = f
            if code:
                cache[code.upper()] = f
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

    def _board_blob(self, row: dict[str, Any]) -> str:
        return " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._board_blob(row)
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
            "origen": "sede_board",
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._board_blob(row)
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
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "expte": row.get("expediente") or None,
            "source": "ayuntamiento",
            "origen": "sede_board",
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdfs"):
            rec["pdf_url"] = row["pdfs"][0]
            if len(row["pdfs"]) > 1:
                rec["pdf_urls"] = row["pdfs"][:20]
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._licencia_info_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._licencia_info_pages():
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

        for rec in self._collect_sit_ambitos():
            add(rec)
        for rec in self._collect_pgou_seed():
            add(rec)
        for item in self._collect_wp_posts():
            add(self._wp_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        sit_n = sum(1 for r in rows if r.get("origen") == "sit_wfs")
        wp_n = sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_"))
        tablon_n = sum(1 for r in rows if r.get("origen") == "sede_board")
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_ambitos": sit_n,
            "wp_posts": wp_n,
            "tablon_items": tablon_n,
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
