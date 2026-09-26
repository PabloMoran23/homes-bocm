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

WP_BASE = "https://www.fresnedillasdelaoliva.es"
SEDE_BASE = "https://fresnedillasdelaoliva.sedelectronica.es"
MUNICIPIO = "Fresnedillas de la Oliva"
ID_PREFIX = "fresnedillas-de-la-oliva"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "FRESNEDILLAS DE LA OLIVA"

URBANISMO_CITIZEN_URL = (
    f"{SEDE_BASE}/citizen-service/ba9ebb99-227d-4ca4-897c-de1ef7994bb4"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/ayuntamiento/",
    f"{WP_BASE}/transparencia/",
    URBANISMO_CITIZEN_URL,
    f"{SEDE_BASE}/transparency/",
    f"{SEDE_BASE}/normative",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|vado|cedula|c[eé]dula urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|convenio|urbanizaci[oó]n|unidad(?:es)? de ejecuci[oó]n|actuaci[oó]n|"
    r"estatutos|compensaci[oó]n|bocm|edicto|estudio (?:ac[uú]stico|ambiental)|"
    r"ordenanza|adoquin|firme|viario|suelo|parcela|"
    r"\b(?:UE|UA|AD|AN|AI|PAU|SAU|S)-[\w\d-]+\b|sau pe[nñ]a)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|bolsa|igualdad|jurado|tribunal del jurado|"
    r"pirotecnia|campamento urbano|fiestas|carnaval|navidad|convocatoria.*plaza)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|UA|AD|AN|AI|PAU|SAU|S)-[\w\d-]+|SAU\s+PE[NÑ]A\s+GORDA)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(r'href="([^"]+\.(?:pdf|PDF)[^"]*)"', re.I)
RE_PREVIEW = re.compile(
    r'href="(https://fresnedillasdelaoliva\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(
    r'class="(class_[^"]+)"[^>]*data-label="([^"]*)"[^>]*>(.*?)</td>',
    re.I | re.S,
)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)


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
    return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in re.finditer(r"\b((?:19|20)\d{2})\b", text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
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
    if re.search(r"\bua-\d+\b", n) or "unidad de actuaci" in n:
        return "unidad de actuación"
    if "sau" in n or "suelo urbanizable" in n:
        return "suelo urbanizable"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "plan general" in n or "pgou" in n:
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "urbanizaci" in n or "adoquin" in n or "firme" in n or "viario" in n:
        return "obra viaria"
    if "aprobaci" in n:
        return "aprobación"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del pgou", " nnss", " de fresnedillas"):
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


class FresnedillasDeLaOlivaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + sede espublico gestiona + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency/"
        )
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_CITIZEN_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-fresnedillas-de-la-oliva/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", unescape(href))

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
            if page_title.lower() not in titulo.lower():
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

    def _collect_wp_child_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = (
                f"{self.wp_base}/wp-json/wp/v2/pages"
                f"?parent=4849&per_page=100&page={page}"
                f"&_fields=id,link,title,content,date"
            )
            try:
                pages = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(pages, list) or not pages:
                break
            for p in pages:
                if not isinstance(p, dict):
                    continue
                title = str((p.get("title") or {}).get("rendered") or "").strip()
                link = str(p.get("link") or "").strip()
                content = str((p.get("content") or {}).get("rendered") or "")
                fecha = _iso_date_wp(str(p.get("date") or ""))
                plain = _strip_html(content)
                blob = f"{title} {plain}"
                if not RE_PROYECTO.search(blob):
                    continue
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": fecha,
                        "url": link,
                        "origen": "wp_pleno",
                        "nota": plain[:1200],
                        "blob": blob[:2000],
                    }
                )
            if len(pages) < 100:
                break
            page += 1
        return rows

    def _collect_transparency(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.transparency_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            if url in seen:
                continue
            seen.add(url)
            local = html[max(0, m.start() - 500) : m.end() + 200]
            title_m = re.search(r'title="([^"]+)"', local, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else url
            blob = titulo
            if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": "sede_transparency",
                }
            )
        return rows

    def _collect_wp(self) -> list[dict[str, Any]]:
        by_key: dict[str, dict[str, Any]] = {}
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._parse_page_pdfs(html, page_url):
                key = rec.get("pdf_url") or rec["url"] + "|" + rec["titulo"]
                by_key[key] = rec
        for rec in self._collect_wp_child_pages():
            key = rec["url"] + "|" + rec["titulo"]
            by_key[key] = rec
        for rec in self._collect_transparency():
            key = rec.get("pdf_url") or rec["url"]
            by_key[key] = rec
        return list(by_key.values())

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "class_name" not in row_html:
                continue
            cells: dict[str, str] = {}
            doc_url = self.board_url
            for cm in RE_BOARD_CELL.finditer(row_html):
                label_key = cm.group(1)
                val_html = cm.group(3)
                link_m = re.search(r'href="([^"]+)"', val_html, re.I)
                if link_m:
                    doc_url = urllib.parse.urljoin(f"{self.sede_base}/", link_m.group(1))
                cells[label_key] = _strip_html(val_html)

            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")
            titulo = descripcion or documento

            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "descripcion": descripcion[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": doc_url,
                    "origen": "sede_board",
                }
            )

        if not rows:
            for m in RE_PREVIEW.finditer(html):
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
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo — sede electrónica",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Área URBANISMO en sede espublico gestiona",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo de trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites municipales",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias, comunicaciones previas y declaraciones responsables",
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
            html = self._fetch(self.urbanismo_url)
        except urllib.error.URLError:
            return tramites
        seen_urls: set[str] = set()
        for m in re.finditer(
            r'href="(https://fresnedillasdelaoliva\.sedelectronica\.es/[^"]+)"',
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
                "url": self.urbanismo_url,
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
        blob = row.get("blob") or f"{row['titulo']} {row.get('nota', '')}"
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
            "info": sum(1 for r in rows if r.get("origen") in ("wp_tramite", "sede_tablon", "sede_tramite")),
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
