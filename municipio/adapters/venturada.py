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

WP_BASE = "https://venturada.org"
SEDE_BASE = "https://venturada.sedelectronica.es"
MUNICIPIO = "Venturada"
ID_PREFIX = "venturada"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VENTURADA"

WP_URBANISMO_CATEGORIES = (40, 19, 73)  # urbanismo, urbanismo-y-obras, bandos-municipales

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/areas/urbanismo/",
    f"{WP_BASE}/normativa/ordenanzas/",
    f"{WP_BASE}/licencia-reformas/",
    f"{WP_BASE}/tramites/",
    f"{WP_BASE}/tramites/descarga-de-impresos-municipales/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|1[aª] ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|convenio|urbanizaci[oó]n|unidad(?:es)? de ejecuci[oó]n|actuaci[oó]n|"
    r"estatutos|compensaci[oó]n|bocm|edicto|estudio (?:ac[uú]stico|ambiental)|"
    r"ordenanza|zona-\d|pol[ií]gono|c[eé]dula urban|"
    r"\b(?:UE|AD|AN|AI|PAU|S)-[\w\d-]+\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|bolsa|igualdad|guerra civil|naturaleza viva|"
    r"mirador|nevera|finca riosequillo|bolet[ií]n informativo la fragua)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|AD|AN|AI|PAU|S)-[\w\d-]+)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(r'href="([^"]+\.(?:pdf|PDF)[^"]*)"', re.I)
RE_ACCORDION_PANEL = re.compile(
    r'vc_tta-title-text">([^<]+)</span>.*?vc_tta-panel-body">(.*?)</div></div></div></div></div></div>',
    re.I | re.S,
)
RE_LINK_TEXT_PDF = re.compile(
    r'(?:<a[^>]+href="([^"]+\.(?:pdf|PDF)[^"]*)"[^>]*>([^<]+)</a>|'
    r'<a[^>]+class="pdfemb-viewer"[^>]+data-[^>]+>([^<]+)</a>)',
    re.I | re.S,
)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)
RE_BOARD_PREVIEW = re.compile(
    r'href="(https://venturada\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"BOCM-(\d{8})", url, re.I)
    if m:
        raw = m.group(1)
        try:
            return datetime(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bue-[\w-]+\b", n) or "unidad de ejecuci" in n:
        return "unidad de ejecución"
    if "urbanizaci" in n or "compensaci" in n or "estatutos" in n:
        return "urbanización"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "plan general" in n or "pgou" in n or "avance" in n:
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "aprobaci" in n:
        return "aprobación"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del pgou", " nnss", " de venturada"):
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


class VenturadaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor + sede espublico gestiona + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency/"
        )
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-venturada/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _parse_accordion_panels(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_ACCORDION_PANEL.finditer(html):
            title = unescape(m.group(1).strip())
            body = m.group(2)
            pdfs: list[tuple[str, str]] = []
            for pm in RE_LINK_TEXT_PDF.finditer(body):
                if pm.group(1):
                    pdfs.append((self._abs_wp(pm.group(1)), unescape(pm.group(2).strip())))
                elif pm.group(3):
                    label = unescape(pm.group(3).strip())
                    pdf_m = re.search(r'href="([^"]+\.(?:pdf|PDF)[^"]*)"', body[pm.start() : pm.end() + 200], re.I)
                    if pdf_m:
                        pdfs.append((self._abs_wp(pdf_m.group(1)), label))
            for pdf_m in RE_PDF_HREF.finditer(body):
                pdf_url = self._abs_wp(pdf_m.group(1))
                if not any(u == pdf_url for u, _ in pdfs):
                    name = unescape(Path(urllib.parse.urlparse(pdf_url).path).name)
                    pdfs.append((pdf_url, name))
            blob = _strip_html(body)
            if pdfs:
                for pdf_url, label in pdfs:
                    titulo = f"{title} — {label}" if label and label.lower() not in title.lower() else title
                    rows.append(
                        {
                            "titulo": titulo[:500],
                            "fecha": _fecha_from_url(pdf_url),
                            "url": page_url,
                            "pdf_url": pdf_url,
                            "origen": "wp_accordion",
                        }
                    )
            elif RE_PROYECTO.search(title) or RE_PROYECTO.search(blob):
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": None,
                        "url": page_url,
                        "origen": "wp_accordion",
                        "nota": blob[:300] if blob else None,
                    }
                )
        return rows

    def _parse_page_pdfs(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        h1_m = RE_H1.search(html)
        page_title = _strip_html(h1_m.group(1)) if h1_m else page_url
        seen: set[str] = set()
        for m in re.finditer(
            r'<a[^>]+href="([^"]+\.(?:pdf|PDF)[^"]*)"[^>]*>([^<]*)</a>',
            html,
            re.I,
        ):
            pdf_url = self._abs_wp(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            label = unescape(m.group(2).strip()) or Path(urllib.parse.urlparse(pdf_url).path).name
            titulo = label if len(label) > 8 else f"{page_title} — {label}"
            if page_title.lower() not in titulo.lower() and "bocm" not in titulo.lower():
                titulo = f"{page_title} — {titulo}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_url(pdf_url),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "origen": "wp_pdf",
                }
            )
        intro = _strip_html(html[html.find("<body") : html.find("</body")])[:800]
        if RE_PROYECTO.search(intro) and not rows:
            rows.append(
                {
                    "titulo": page_title[:500],
                    "fecha": None,
                    "url": page_url,
                    "origen": "wp_page",
                    "nota": intro[:400],
                }
            )
        return rows

    def _collect_wp_api_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for cat_id in WP_URBANISMO_CATEGORIES:
            page = 1
            while page <= 5:
                url = (
                    f"{self.wp_base}/wp-json/wp/v2/posts"
                    f"?categories={cat_id}&per_page=100&page={page}&_fields=id,link,title,date"
                )
                try:
                    posts = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(posts, list) or not posts:
                    break
                for p in posts:
                    if not isinstance(p, dict):
                        continue
                    title = str((p.get("title") or {}).get("rendered") or "").strip()
                    link = str(p.get("link") or "").strip()
                    fecha = _iso_date_wp(str(p.get("date") or ""))
                    if not title or not link:
                        continue
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": fecha,
                            "url": link,
                            "origen": "wp_api",
                        }
                    )
                if len(posts) < 100:
                    break
                page += 1
        return rows

    def _collect_wp(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            items = self._parse_accordion_panels(html, page_url)
            items.extend(self._parse_page_pdfs(html, page_url))
            for rec in items:
                key = rec.get("pdf_url") or rec["url"] + "|" + rec["titulo"]
                by_key[key] = rec
        for rec in self._collect_wp_api_posts():
            key = rec["url"] + "|" + rec["titulo"]
            by_key[key] = rec
        return list(by_key.values())

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if tbody_m:
            for row_m in RE_BOARD_ROW.finditer(tbody_m.group(1)):
                row_html = row_m.group(1)
                if "emptyRow" in row_html:
                    continue
                cells: dict[str, str] = {}
                doc_url = self.board_url
                for cm in RE_BOARD_CELL.finditer(row_html):
                    label, val = cm.group(1), cm.group(2)
                    link_m = re.search(r'href="([^"]+)"', val, re.I)
                    if link_m:
                        doc_url = urllib.parse.urljoin(f"{self.sede_base}/", link_m.group(1))
                    cells[label] = _strip_html(val)
                titulo = cells.get("Descripción") or cells.get("Documento") or ""
                if not titulo:
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": cells.get("Expediente", ""),
                        "procedimiento": cells.get("Procedimiento", ""),
                        "categoria": cells.get("Categoría", ""),
                        "fecha": _parse_fecha_dmy(cells.get("Fecha de Publicación", "")),
                        "url": doc_url,
                        "origen": "sede_board",
                    }
                )
        if not rows:
            for m in RE_BOARD_PREVIEW.finditer(html):
                url = m.group(1)
                local = html[max(0, m.start() - 400) : m.end() + 200]
                title_m = re.search(r'title="([^"]*)"', local, re.I)
                titulo = unescape(title_m.group(1).strip()) if title_m else url
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "expediente": "",
                        "procedimiento": "",
                        "categoria": "",
                        "fecha": _fecha_from_blob(titulo),
                        "url": url,
                        "pdf_url": url,
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tramites: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", f"{self.wp_base}/licencia-reformas/"),
                "fecha_concesion": None,
                "tipo": "trámite licencia de obra / reformas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencia de reformas y obras en vivienda",
                "url": f"{self.wp_base}/licencia-reformas/",
                "source": "ayuntamiento",
                "nota": "Información y enlace a sede electrónica",
                "origen": "wp_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo en sede electrónica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencia obra, declaración responsable, cédula urbanística",
                "origen": "sede_tramite",
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
                "nota": "Anuncios y exposiciones públicas (espublico gestiona)",
                "origen": "sede_tablon",
            },
        ]
        try:
            html = self._fetch(f"{self.wp_base}/areas/urbanismo/")
        except urllib.error.URLError:
            return tramites
        seen_urls: set[str] = set()
        for m in re.finditer(
            r'href="(https://venturada\.sedelectronica\.es/[^"]+)"',
            html,
            re.I,
        ):
            url = m.group(1)
            if url in seen_urls:
                continue
            local = html[max(0, m.start() - 300) : m.end() + 300]
            if not RE_LICENCIA.search(local):
                continue
            seen_urls.add(url)
            label_m = re.search(
                r"(?:licencia|declaraci[oó]n|c[eé]dula)[^<]{0,120}",
                _strip_html(local),
                re.I,
            )
            titulo = label_m.group(0).strip() if label_m else "Trámite urbanismo (sede)"
            tramites.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite sede electrónica",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_tramite",
                }
            )
        return tramites

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

        title_upper = title.upper()
        for name, feat in cache.items():
            if len(name) < 4:
                continue
            if name in title_upper:
                candidates.append((80.0, name, feat))

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
                "url": f"{self.wp_base}/areas/urbanismo/",
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

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row["titulo"]
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"] + "|" + row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("nota"):
            rec["nota"] = row["nota"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
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

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria")
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
            "info": sum(1 for r in rows if r.get("origen") in ("wp_tramite", "sede_tablon")),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
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

        for item in self._collect_wp():
            add(self._wp_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "board": sum(1 for r in rows if r.get("origen") == "sede_board"),
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


def _fecha_from_blob(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _fecha_from_url(text)
