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

WP_BASE = "https://chapineria.madrid"
WP_API = f"{WP_BASE}/wp-json/wp/v2"
SEDE_BASE = "https://chapineria.sedelectronica.es"
MUNICIPIO = "Chapinería"
ID_PREFIX = "chapineria"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "CHAPINERÍA"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/urbanismo/",
    f"{WP_BASE}/area-de-descargas/",
]

URBANISMO_FORM_PREFIX = re.compile(r"(?i)^04\.(0[89]|1[0-9]|2[01])")

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|"
    r"primera ocupaci[oó]n|cedula urban|parcelaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|parcela|suelo|bando|ordenanza|"
    r"ue[-\s]|ambito|valquigoso|pozair)",
)
RE_SKIP = re.compile(
    r"(?i)(impuesto|ibi|iae|cobranza|recaudaci[oó]n|veh[ií]culos|ordenanza fiscal|"
    r"empleo p[uú]blico|subvenciones deportivas|jurado|herederos|selecci[oó]n personal|"
    r"programa de activaci[oó]n profesional)",
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://chapineria\.madrid)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_PREVIEW = re.compile(
    r'href="((?:https://chapineria\.sedelectronica\.es)?/preview-document/[^"]+)"',
    re.I,
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/wp-content/uploads/(\d{4})/(\d{2})/")
RE_UE_CODE = re.compile(r"(?i)\b((?:UE|AD|AN|AI|S)[-\s]?[A-Z0-9]+(?:[-\s][A-Z0-9]+)*)\b")

AMBIT_KEYWORDS = (
    "VALQUIGOSO",
    "POZAIR",
    "LANCHAR",
    "DEHESA",
    "ZARZA",
    "ANAGÜESA",
    "ANAGUESA",
    "ZAGÁN",
    "ZAGAN",
    "PALACIO",
    "ESCUELAS",
    "MADRID",
    "RODETAS",
    "PILANCONES",
    "LAGUNILLOS",
    "TORRECILLA",
    "MOLINO",
    "MADERAS",
    "CONFITES",
    "ALDEA",
    "SAN MARTÍN",
    "SAN MARTIN",
    "INDUSTRIAL",
)


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _iso_date(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw[:10] if len(raw) >= 10 else None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str, base: str = WP_BASE) -> str:
    return unescape(urllib.parse.urljoin(base, href))


def _pdf_tipo(name: str) -> str:
    n = name.lower()
    if "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "declaracion responsable" in n or "declaración responsable" in n:
        return "declaración responsable"
    if "obra mayor" in n:
        return "licencia obra mayor"
    if "primera ocup" in n:
        return "primera ocupación"
    if "cedula urban" in n or "cédula urban" in n:
        return "cédula urbanística"
    if "parcelacion" in n or "parcelación" in n:
        return "parcelación urbanística"
    if "gestion urban" in n or "gestión urban" in n:
        return "gestión urbanística"
    return "trámite urbanismo"


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "bando" in n and "parcela" in n:
        return "bando urbanístico"
    if "ordenanza" in n:
        return "ordenanza"
    if "informaci" in n and "p" in n:
        return "información pública"
    if re.search(r"(?i)\bue[-\s]", title) or "ambito" in n or "ámbito" in n:
        return "ámbito planeamiento"
    if "bocm" in n:
        return "publicación BOCM"
    return "urbanismo"


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


class ChapineriaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo + descargas + sede espublico + SIT WFS ámbitos (NNSS)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_api = str(self.config.get("wp_api_base") or WP_API).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or geom_cfg.get("wfs_base") or WFS_BASE)
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
        self._ambit_cache: list[dict[str, Any]] | None = None
        self._ambit_names: list[str] | None = None

    def _fetch(self, url: str, use_sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        if use_sede or "sedelectronica.es" in url:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _extract_pdfs(self, html: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            url = _abs_url(m.group(1))
            if url in seen:
                continue
            seen.add(url)
            name = unescape(urllib.parse.unquote(Path(url).name))
            name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
            out.append((name[:500], url))
        return out

    def _paginate_wp_posts(self, search: str | None = None) -> list[dict[str, Any]]:
        posts: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = f"{self.wp_api}/posts?per_page=100&page={page}&status=publish"
            if search:
                url += f"&search={urllib.parse.quote(search)}"
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

    @staticmethod
    def _post_title(post: dict[str, Any]) -> str:
        title = post.get("title") or {}
        return unescape(str(title.get("rendered") or "")).strip()

    def _collect_urbanismo_forms(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(f"{WP_BASE}/area-de-descargas/")
        except urllib.error.URLError:
            return rows
        for title, pdf_url in self._extract_pdfs(html):
            stem = Path(urllib.parse.unquote(pdf_url)).name
            if not URBANISMO_FORM_PREFIX.search(stem):
                continue
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": _fecha_from_url(pdf_url),
                    "tipo": _pdf_tipo(title),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": pdf_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "formulario_urbanismo",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", f"{WP_BASE}/urbanismo/"),
                "fecha_concesion": None,
                "tipo": "información urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área de Urbanismo — trámites y normativa",
                "url": f"{WP_BASE}/urbanismo/",
                "source": "ayuntamiento",
                "origen": "web_urbanismo",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios (sede)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y exposiciones públicas en sede espublico",
                "origen": "sede_tablon",
            },
        ]

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for title, pdf_url in self._extract_pdfs(html):
                if pdf_url in seen:
                    continue
                if URBANISMO_FORM_PREFIX.search(Path(urllib.parse.unquote(pdf_url)).name):
                    continue
                if not RE_PROYECTO.search(f"{title} {pdf_url}"):
                    continue
                seen.add(pdf_url)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", pdf_url),
                    "municipio": MUNICIPIO,
                    "titulo": f"{MUNICIPIO}: {title}"[:500],
                    "fecha": _fecha_from_url(pdf_url),
                    "tipo": _pdf_tipo(title),
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "urbanismo_pdf",
                }
                self._attach_geometry(rec)
                rows.append(rec)
        return rows

    def _wp_post_to_proyecto(self, post: dict[str, Any]) -> dict[str, Any] | None:
        title = self._post_title(post)
        content = str((post.get("content") or {}).get("rendered") or "")
        blob = f"{title} {_strip_html(content)}"
        if RE_SKIP.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        url = str(post.get("link") or "").strip()
        if not url:
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": title[:500],
            "fecha": _iso_date(str(post.get("date") or "")),
            "tipo": _proyecto_tipo(title),
            "url": url,
            "source": "ayuntamiento",
            "origen": "wp_noticia",
        }
        pdfs = self._extract_pdfs(content)
        if pdfs:
            rec["pdf_url"] = pdfs[0][1]
        self._attach_geometry(rec)
        return rec

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "preview-document" not in row_html:
                continue
            cells = [_strip_html(c) for c in RE_BOARD_CELL.findall(row_html)]
            cells = [c for c in cells if c]
            if len(cells) < 4 or cells[0] in ("Documento", "Expediente"):
                continue
            preview_m = RE_PREVIEW.search(row_html)
            doc_url = preview_m.group(1) if preview_m else self.board_url
            if doc_url.startswith("/"):
                doc_url = f"{self.sede_base}{doc_url}"
            title_m = re.search(r'title="([^"]*)"', row_html, re.I)
            documento = cells[0]
            expediente = cells[1] if len(cells) > 1 else ""
            procedimiento = cells[2] if len(cells) > 2 else ""
            categoria = cells[3] if len(cells) > 3 else ""
            descripcion = cells[4] if len(cells) > 4 else ""
            fecha_raw = cells[5] if len(cells) > 5 else ""
            titulo = (title_m.group(1).strip() if title_m else "") or descripcion or documento
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "descripcion": descripcion[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": doc_url,
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_SKIP.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec = {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": row.get("origen", "tablon_sede"),
        }
        self._attach_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia (tablón sede)",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen", "tablon_sede"),
        }

    def _load_ambitos(self) -> tuple[list[dict[str, Any]], list[str]]:
        if self._ambit_cache is not None and self._ambit_names is not None:
            return self._ambit_cache, self._ambit_names
        cql = f"DS_MUNICIPIO='{self.wfs_municipio}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "200",
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_base}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._ambit_cache = []
            self._ambit_names = []
            return self._ambit_cache, self._ambit_names
        feats = data.get("features") if isinstance(data, dict) else []
        self._ambit_cache = [f for f in feats or [] if isinstance(f, dict)]
        self._ambit_names = sorted(
            {
                str(f.get("properties", {}).get("DS_NOMB_AMB") or "")
                for f in self._ambit_cache
                if f.get("properties", {}).get("DS_NOMB_AMB")
            }
        )
        return self._ambit_cache, self._ambit_names

    def _collect_sit_ambito_proyectos(self) -> list[dict[str, Any]]:
        feats, _ = self._load_ambitos()
        rows: list[dict[str, Any]] = []
        by_name: dict[str, list[dict[str, Any]]] = {}
        for feat in feats:
            props = feat.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if name:
                by_name.setdefault(name, []).append(feat)
        visor_url = "https://idem.madrid.org/cartografia/sitcm/html/visor.htm"
        for name, group in sorted(by_name.items()):
            merged = _merge_geometries(group)
            if not merged:
                continue
            safe_ambit = name.replace("'", "''")
            cql = f"DS_MUNICIPIO='{self.wfs_municipio}' AND DS_NOMB_AMB='{safe_ambit}'"
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": self.wfs_type,
                    "outputFormat": "application/json",
                    "srsName": "EPSG:4326",
                    "count": "20",
                    "CQL_FILTER": cql,
                }
            )
            query_url = f"{self.wfs_base}?{params}"
            fig = str((group[0].get("properties") or {}).get("DS_FIG_DES") or "planeamiento")
            fecha = _iso_date(str((group[0].get("properties") or {}).get("FC_BOCM") or ""))
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": f"{name} — Normas Subsidiarias ({fig})"[:500],
                "fecha": fecha or "2000-07-10",
                "tipo": "ámbito planeamiento",
                "url": visor_url,
                "source": "ayuntamiento",
                "origen": "sit_wfs_ambito",
                "geom_geojson": merged,
                "geometry_source": "portal_wfs",
                "geometry_source_url": query_url,
                "coord_source": "portal_geometry_centroid",
                "geometry_ambit": name,
            }
            centroid = geometry_centroid(merged)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            rows.append(rec)
        return rows

    def _match_ambit_name(self, title: str, names: list[str]) -> str | None:
        t = title.lower()
        keywords: list[str] = []
        for m in RE_UE_CODE.finditer(title):
            keywords.append(m.group(1).replace(" ", "-").upper())
        for token in AMBIT_KEYWORDS:
            if token.lower() in t:
                keywords.append(token)
        keywords = list(dict.fromkeys(k for k in keywords if k))
        best: str | None = None
        best_score = 0
        for name in names:
            nf = name.lower()
            score = 0
            for kw in keywords:
                kl = kw.lower()
                if kl in nf or nf in kl:
                    score += 10
                else:
                    for part in re.split(r"[\s\-]+", kl):
                        if len(part) >= 4 and part in nf:
                            score += 3
            if score > best_score:
                best_score = score
                best = name
        return best if best_score >= 6 else None

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        feats, names = self._load_ambitos()
        if not feats or not names:
            return None
        ambit = self._match_ambit_name(title, names)
        if not ambit:
            return None
        chosen = [f for f in feats if str(f.get("properties", {}).get("DS_NOMB_AMB")) == ambit]
        merged = _merge_geometries(chosen)
        if not merged:
            return None
        safe_ambit = ambit.replace("'", "''")
        cql = f"DS_MUNICIPIO='{self.wfs_municipio}' AND DS_NOMB_AMB='{safe_ambit}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "20",
                "CQL_FILTER": cql,
            }
        )
        query_url = f"{self.wfs_base}?{params}"
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": query_url,
            "coord_source": "portal_geometry_centroid",
            "geometry_ambit": ambit,
        }

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        title = str(rec.get("titulo") or "")
        geom = self._fetch_geometry(title)
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

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

        for rec in self._collect_urbanismo_forms():
            add(rec)
        for rec in self._collect_licencia_info_pages():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_licencia(item))

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_urbanismo_forms():
            existing[rec["id"]] = rec
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

        for rec in self._collect_sit_ambito_proyectos():
            add(rec)
        for rec in self._collect_seed_pdfs():
            add(rec)
        for post in self._paginate_wp_posts("urbanismo"):
            add(self._wp_post_to_proyecto(post))
        for post in self._paginate_wp_posts("parcela"):
            add(self._wp_post_to_proyecto(post))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "sit_ambitos": sum(1 for r in rows if r.get("origen") == "sit_wfs_ambito"),
            "tablon_items": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
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
