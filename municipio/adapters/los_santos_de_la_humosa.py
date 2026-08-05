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
from municipio.gis.sitcm import resolve_ambito_geometry

WP_BASE = "https://lossantosdelahumosa.eu"
SEDE_BASE = "https://lossantosdelahumosa.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
MUNICIPIO = "Los Santos de la Humosa"
ID_PREFIX = "los-santos-de-la-humosa"
WFS_MUNICIPIO = "LOS SANTOS DE LA HUMOSA"

DEFAULT_WP_CATEGORIES = (31, 117)
WP_SEARCH_TERMS = ("planeamiento", "nnss", "normas subsidiarias", "sector", "bocm")

RE_PREVIEW = re.compile(
    r'href="(https://lossantosdelahumosa\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"licencia de actividad|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|edicto|reparcel|aprobaci[oó]n|"
    r"modificaci[oó]n|sector|industrial|nnss|normas subsidiarias|"
    r"construcci|suelo|parcela|urbanizaci|bocm|memoria|plano|"
    r"\b(?:UE|AD|AN|AI|PAU|S|U)-\d+\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(convocatoria.*pleno|sesi[oó]n ordinaria.*pleno|pleno.*convocatoria|"
    r"padr[oó]n fiscal|empleo p[uú]blico|campamento urbano|piscina municipal|"
    r"fiestas patronales|encierro|subvencion|licitaci[oó]n|concurso p[uú]blico|"
    r"bar-terraza|peñas|casetas)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|AD|AN|AI|PAU|S|U)-\d+[A-Z0-9-]*)\b",
)
RE_SECTOR_NUM = re.compile(r"(?i)\bsector\s+(\d+)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[./-](\d{2})[./-]")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)

SECTOR_HINTS: dict[str, list[str]] = {
    "3": ["S-3 LOS LLANOS"],
    "8": ["S-8 HENARES (APLAZADO)"],
}


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n or "bocm" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    if "obra" in n:
        return "obras"
    if "licencia" in n:
        return "licencia publicada"
    return "urbanismo"


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


class LosSantosDeLaHumosaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Avada (bando/notas) + tablón espublico sede + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_url = str(self.config.get("transparency_url") or TRANSPARENCY_URL)
        raw_cats = self.config.get("wp_category_ids") or list(DEFAULT_WP_CATEGORIES)
        self.wp_category_ids = [int(c) for c in raw_cats]
        self.wp_search_terms = list(self.config.get("wp_search_terms") or WP_SEARCH_TERMS)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or "https://idem.comunidad.madrid/geoserver3/ows")
        self.wfs_type = str(geom_cfg.get("type_name") or "sitcm:VPLA_V_AMBITO")
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
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-los-santos-de-la-humosa/1.0")},
        )
        use_insecure = self.config.get("insecure_ssl", True) if insecure is None else insecure
        if use_insecure and "lossantosdelahumosa.sedelectronica.es" in url:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url, insecure=False))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _extract_pdfs(self, html: str) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_wp(m.group(1))
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_links: set[str] = set()

        def add_post(post: dict[str, Any], origen: str) -> None:
            link = str(post.get("link") or "").strip()
            if not link or link in seen_links:
                return
            seen_links.add(link)
            title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
            content = str((post.get("content") or {}).get("rendered") or "")
            fecha = _iso_date_wp(str(post.get("date") or ""))
            pdfs = self._extract_pdfs(content)
            rows.append(
                {
                    "titulo": title[:500],
                    "fecha": fecha,
                    "url": link,
                    "pdfs": pdfs,
                    "origen": origen,
                }
            )

        for cat_id in self.wp_category_ids:
            page = 1
            while page <= 5:
                url = (
                    f"{self.wp_base}/wp-json/wp/v2/posts"
                    f"?categories={cat_id}&per_page=100&page={page}"
                )
                try:
                    posts = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(posts, list) or not posts:
                    break
                for post in posts:
                    add_post(post, f"wp_cat_{cat_id}")
                if len(posts) < 100:
                    break
                page += 1

        for term in self.wp_search_terms:
            try:
                posts = self._fetch_json(
                    f"{self.wp_base}/wp-json/wp/v2/posts?search={urllib.parse.quote(term)}&per_page=50"
                )
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                add_post(post, f"wp_search_{term.replace(' ', '_')}")

        return rows

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = [_strip_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) < 4:
                continue
            link_m = RE_PREVIEW.search(tr)
            doc_url = link_m.group(1) if link_m else self.board_url
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or cells[0]
            fecha = _parse_fecha_dmy(cells[5]) if len(cells) > 5 else None
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": cells[1] if len(cells) > 1 else "",
                    "procedimiento": cells[2] if len(cells) > 2 else "",
                    "categoria": cells[3] if len(cells) > 3 else "",
                    "descripcion": cells[4] if len(cells) > 4 else "",
                    "fecha": fecha,
                    "url": doc_url,
                    "pdf_url": doc_url,
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

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
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
                "nota": "Concesiones y exposiciones públicas en sede espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes urbanísticos (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación Cl@ve; no hay listado público",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "sede electrónica trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — catálogo de trámites",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Trámites urbanísticos vía espublico gestiona",
                "origen": "sede_tramites",
            },
        ]

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "CQL_FILTER": cql,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        return data.get("features") or [] if isinstance(data, dict) else []

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
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, title)
        if geom:
            return {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": meta.get("ambito_name"),
            }

        cache = self._load_wfs_ambitos()
        if not cache:
            return None

        sector_m = RE_SECTOR_NUM.search(title or "")
        if sector_m:
            hints = SECTOR_HINTS.get(sector_m.group(1), [])
            feats = [cache[k.upper()] for k in hints if k.upper() in cache]
            merged = _merge_geometries(feats)
            if merged:
                return {
                    "geom_geojson": merged,
                    "geometry_source": "portal_wfs",
                    "geometry_source_url": self.wfs_url,
                    "coord_source": "portal_geometry_centroid",
                    "ambito_sit": hints[0] if hints else f"S-{sector_m.group(1)}",
                }

        code_m = RE_AMBIT_CODE.search(title or "")
        if code_m:
            key = code_m.group(1).upper().replace(" ", "")
            feat = cache.get(key)
            if feat:
                merged = _merge_geometries([feat])
                if merged:
                    return {
                        "geom_geojson": merged,
                        "geometry_source": "portal_wfs",
                        "geometry_source_url": self.wfs_url,
                        "coord_source": "portal_geometry_centroid",
                    }
        return None

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

    def _board_blob(self, row: dict[str, Any]) -> str:
        return " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._board_blob(row)
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
            "tipo": _proyecto_tipo(row["titulo"]),
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
        blob = f"{row['titulo']} {' '.join(row.get('pdfs') or [])}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
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
        for board in self._collect_board():
            add(self._board_to_licencia(board))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite", "sede_tramites")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
        after_rows = self._load_jsonl(out_jsonl)
        added = max(0, len(after_rows) - before)
        for rec in after_rows:
            existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for wp in self._collect_wp_posts():
            add(self._wp_to_proyecto(wp))
        for board in self._collect_board():
            add(self._board_to_proyecto(board))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
