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

WP_BASE = "https://pezueladelastorres.es"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://pezueladelastorres.sedelectronica.es"
MUNICIPIO = "Pezuela de las Torres"
ID_PREFIX = "pezuela-de-las-torres"

DOCUMENTACION_URL = f"{SEDE_BASE}/dossier"
PLANEAMIENTO_URL = f"{WP_BASE}/plan-general-de-urbanismo/"
URBANISMO_SEED_PAGES: list[str] = [
    PLANEAMIENTO_URL,
    f"{SEDE_BASE}/transparency/eea024da-381f-4703-8fac-404b38b6a46c/",
    f"{SEDE_BASE}/transparency/43a9a703-9ce0-4af1-9c61-91f799edf8cb/",
    f"{SEDE_BASE}/transparency/089c7eac-a897-4f3d-9d98-21199a80b52a/",
    f"{SEDE_BASE}/transparency/",
]

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "PEZUELA DE LAS TORRES"

RE_PREVIEW = re.compile(
    r'href="(https://pezueladelastorres\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://pezueladelastorres\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|ocupaci[oó]n (?:de |en )?v[ií]a|parcelaci[oó]n|segregaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|reurbaniz|plaza mayor|almendro|"
    r"patrimonio|desbroce.*parcel|bulevar|autov[ií]a|suelo|convenio urban|"
    r"\b(?:UE|UA|AD|AN|AI|PAU|S|SAU)-\d+\b)",
)
RE_WP_EXCLUDE = re.compile(
    r"(?i)(colonias urbanas|arte urbano|autob[uú]s|mapa concesional|"
    r"mercadillo|cine|fiestas|cabalga|empleo|concurso|deporte)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|proceso selectivo|"
    r"plusvalia|basura|residuos|vehiculos|notificaci[oó]n expediente|igualdad|"
    r"jurado|juez de paz|pe[oó]n)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|UA|AD|AN|AI|PAU|S|SAU)-\d+[A-Z0-9-]*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?pezueladelastorres\.es)?/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_LINK_ANCHOR = re.compile(
    r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>',
    re.I,
)


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


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "reurbaniz" in n or "plaza mayor" in n or "almendro" in n:
        return "actuación urbanística"
    if "bando" in n and "parcel" in n:
        return "bando municipal"
    if "convenio" in n:
        return "convenio"
    if re.search(r"\bsau-\d+\b", n):
        return "suelo urbanizable"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    s = text.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio", " nnss"):
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


class PezuelaDeLasTorresAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Divi (PGOU + noticias) + sede espublico gestiona + ámbitos SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency"
        )
        self.documentacion_url = str(self.config.get("documentacion_url") or DOCUMENTACION_URL)
        self.urbanismo_seed_pages = [
            str(u) for u in (self.config.get("urbanismo_seed_pages") or URBANISMO_SEED_PAGES)
        ]
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

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-pezuela-de-las-torres/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{WP_BASE}/", href)

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r'<tbody[^>]*id="[^"]*">(.*?)</tbody>', html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = re.search(
                r'href="(https://pezueladelastorres\.sedelectronica\.es/preview-document/[^"]+)"',
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
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": _strip_html(cells[4]),
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
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
            local = html[max(0, m.start() - 80) : m.end() + 400]
            title_m = re.search(
                rf'href="{re.escape(url)}"[^>]*title="([^"]*)"',
                local,
                re.I,
            )
            if not title_m:
                title_m = re.search(r'title="([^"]*)"', local, re.I)
            text_m = re.search(
                rf'href="{re.escape(url)}"[^>]*class="gIconLink"[^>]*>([^<]+)</a>',
                local,
                re.I,
            )
            if title_m:
                titulo = unescape(title_m.group(1).strip())
            elif text_m:
                titulo = unescape(text_m.group(1).strip())
            else:
                titulo = url
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
        for url, origen in ((self.board_url, "tablon"), (f"{self.sede_base}/info", "info_tablon")):
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            href, titulo = m.group(1), unescape(m.group(2).strip())
            url = href if href.startswith("http") else f"{self.sede_base}{href}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_documentacion_forms(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.documentacion_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf = self._abs_wp(m.group(1))
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
            if not RE_LICENCIA.search(name):
                continue
            rows.append(
                {
                    "titulo": name[:500],
                    "url": self.documentacion_url,
                    "pdf_url": pdf,
                    "fecha": _fecha_from_blob(pdf),
                    "origen": "formulario_web",
                }
            )
        return rows

    def _paginate_wp_posts(self) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        page = 1
        while page <= 8:
            url = f"{WP_API}/posts?per_page=100&page={page}&status=publish"
            try:
                batch = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(batch, list) or not batch:
                break
            posts.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return posts

    def _post_to_proyecto(self, post: dict[str, Any]) -> dict[str, Any] | None:
        title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
        if not title or RE_WP_EXCLUDE.search(title):
            return None
        if not RE_PROYECTO.search(title):
            return None
        url = str(post.get("link") or "").strip()
        if not url:
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": _iso_date_wp(str(post.get("date") or "")),
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
            "origen": "wp_posts",
        }
        content = str((post.get("content") or {}).get("rendered") or "")
        pdfs = [self._abs_wp(m.group(1)) for m in RE_PDF_HREF.finditer(content)]
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        self._enrich_geometry(rec)
        return rec

    def _collect_wp_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for post in self._paginate_wp_posts():
            rec = self._post_to_proyecto(post)
            if rec:
                rows.append(rec)
        return rows

    def _collect_urbanismo_html(self) -> list[dict[str, Any]]:
        """WP REST API bloqueada; extraer PDFs y enlaces de páginas urbanismo."""
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.urbanismo_seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            h1_m = re.search(r'<h1[^>]*>([^<]+)', html, re.I)
            section = unescape(h1_m.group(1).strip()) if h1_m else page_url
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_wp(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                label_m = re.search(
                    rf'href=["\']{re.escape(pdf)}["\'][^>]*>([^<]+)<',
                    html,
                    re.I,
                )
                label = unescape(label_m.group(1).strip()) if label_m else Path(pdf).name
                blob = f"{section} {label}"
                if RE_EXCLUDE.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if not re.search(r"(?i)ordenanza|pgou|consulta|anuncio|bulevar|peatonal", blob):
                        continue
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": f"{section} — {label}"[:500],
                    "fecha": _fecha_from_blob(pdf),
                    "tipo": _proyecto_tipo(blob),
                    "url": page_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "wp_urbanismo",
                }
                self._enrich_geometry(rec)
                rows.append(rec)
            for m in RE_LINK_ANCHOR.finditer(html):
                href, label = m.group(1), unescape(m.group(2).strip())
                if not href or href.startswith("#") or href.startswith("mailto:"):
                    continue
                url = self._abs_wp(href)
                if url in seen or not url.startswith(WP_BASE):
                    continue
                blob = f"{section} {label}"
                if not RE_PROYECTO.search(blob):
                    continue
                if RE_EXCLUDE.search(blob):
                    continue
                seen.add(url)
                rec = {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": f"{section} — {label}"[:500],
                    "fecha": None,
                    "tipo": _proyecto_tipo(blob),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "wp_urbanismo",
                }
                self._enrich_geometry(rec)
                rows.append(rec)
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
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
                "nota": "Anuncios y exposiciones públicas en sede electrónica",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.documentacion_url),
                "fecha_concesion": None,
                "tipo": "formularios licencia y obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Documentación — solicitudes de licencia y obra",
                "url": self.documentacion_url,
                "source": "ayuntamiento",
                "nota": "Formularios PDF; concesiones individuales en tablón cuando se publiquen",
                "origen": "formulario_web",
            },
            {
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "portal transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia — Urbanismo y actividades",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "nota": "Sección URBANISMO y ACTIVIDADES en sede espublico",
                "origen": "transparencia",
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
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([f])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": PLANEAMIENTO_URL,
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

    def _form_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        return {
            "id": _stable_id("lic", row.get("pdf_url") or row["titulo"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "formulario licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("url") or self.documentacion_url,
            "source": "ayuntamiento",
            "nota": "Formulario de solicitud; no concesión publicada",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

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

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|actuaci[oó]n urban|modificaci[oó]n del planeamiento|urban",
            row["titulo"],
        ):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
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
        for item in self._collect_documentacion_forms():
            rec = self._form_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "formularios": sum(1 for r in rows if r.get("origen") == "formulario_web"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_documentacion_forms():
            rec = self._form_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
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

        for rec in self._collect_wp_proyectos():
            add(rec)
        for rec in self._collect_urbanismo_html():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._tramite_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_posts"),
            "wp_urbanismo": sum(1 for r in rows if r.get("origen") == "wp_urbanismo"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
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
