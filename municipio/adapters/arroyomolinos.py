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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid

WP_BASE = "https://www.ayto-arroyomolinos.org"
SEDE_BASE = "https://arroyomolinos.sedelectronica.es"
MUNICIPIO = "Arroyomolinos"
ID_PREFIX = "arroyomolinos"

URBANISMO_RSS = (
    f"{WP_BASE}/ayuntamiento/concejalias/urbanismo-medio-ambiente-y-transportes/"
    "urbanismo/noticias/rss.xml"
)
URBANISMO_PAGE = (
    f"{WP_BASE}/ayuntamiento/concejalias/urbanismo-medio-ambiente-y-transportes/urbanismo"
)
TRAMITES_URL = f"{WP_BASE}/servicios/tramites-municipales/tramites-urbanismo"
ARCHIVE_BASE = (
    f"{WP_BASE}/ayuntamiento/concejalias/urbanismo-medio-ambiente-y-transportes/"
    "urbanismo/archivos"
)
DEFAULT_ARCHIVE_YEARS = tuple(str(y) for y in range(2017, 2026))

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "ARROYOMOLINOS"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"calas|fotovolta|piscina|reapertura)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|expte|reparcel|modificaci[oó]n|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|aprobaci[oó]n.*(?:plan|inicial|definitiva)|"
    r"edicto|mejora urbana|dotaci[oó]n de redes|sau-|ue-?\d|apd-|bocm)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(empleo p[uú]blico|oposici[oó]n|polic[ií]a local|subvenci[oó]n|"
    r"carnaval|veh[ií]culo abandonado|iae|cobranza|matrimonio|bando tv|"
    r"luminarias led|aparcamiento|paso de peatones|piscinas comunitarias)",
)
RE_EXCLUDE_PROY = re.compile(
    r"(?i)(reapertura de las piscinas|luminarias led|aparcamiento de la avenida|"
    r"paso de peatones|direcci[oó]n general de carreteras)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|SAU|APD|AD|AN|AI|PAU|S|PE)-?\d+[A-Z0-9-]*)\b",
)
RE_EXPTE = re.compile(r"(?i)(?:expte\.?|expediente)\s*[:.]?\s*(\d+/\d{4})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PREVIEW = re.compile(
    r'href="(https://arroyomolinos\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https?://www\.ayto-arroyomolinos\.org)?/[^"]+\.pdf[^"]*)"',
    re.I,
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime(
                    "%Y-%m-%d"
                )
            except ValueError:
                pass
    years = [
        int(y.group(1))
        for y in RE_YEAR.finditer(text or "")
        if 1980 <= int(y.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _parse_rss_date(text: str) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_wp(href: str) -> str:
    return urllib.parse.urljoin(f"{WP_BASE}/", unescape(href))


def _pdf_title_from_url(url: str) -> str:
    path = urllib.parse.unquote(url.split("?")[0].rstrip("/"))
    if path.endswith("/view"):
        path = path[:-5]
    name = Path(path).name
    if name.lower().endswith(".pdf"):
        name = name[:-4]
    return _clean_title(name.replace("-", " ").replace("_", " ")) or url


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan especial" in n or re.search(r"\bpe\b", n):
        return "plan especial"
    if "plan parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "pgou" in n or "planeamiento" in n:
        return "planeamiento"
    if "informaci" in n or "bocm" in n:
        return "información pública"
    if "convenio" in n or "reparcel" in n:
        return "convenio urbanístico"
    if "impacto ambiental" in n or "fotovolta" in n:
        return "evaluación ambiental"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    s = text.strip()
    low = s.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio", " expte"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()&]+", low) if len(p) >= 3]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        k = p.lower()
        if k not in seen and not re.fullmatch(r"\d{4}", p):
            seen.add(k)
            out.append(p)
    return out[:10]


class ArroyomolinosAyuntamientoAdapter(AyuntamientoAdapter):
    """Plone urbanismo (RSS + archivos) + sede espublico tablón + WFS SITCM (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.archive_years = list(self.config.get("archive_years") or DEFAULT_ARCHIVE_YEARS)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-arroyomolinos/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        if "sedelectronica" in url:
            with self._opener.open(req, timeout=60) as resp:
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any | None:
        try:
            return json.loads(self._fetch(url))
        except (json.JSONDecodeError, urllib.error.URLError):
            return None

    def _parse_board_table(self, html: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 4:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or _strip_html(cells[0])
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": _strip_html(cells[1]) if len(cells) > 1 else "",
                    "procedimiento": _strip_html(cells[2]) if len(cells) > 2 else "",
                    "categoria": _strip_html(cells[3]) if len(cells) > 3 else "",
                    "descripcion": _strip_html(cells[4]) if len(cells) > 4 else "",
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])) if len(cells) > 5 else None,
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []
        return self._parse_board_table(html)

    def _collect_rss(self) -> list[dict[str, Any]]:
        try:
            xml_text = self._fetch(URBANISMO_RSS)
            root = ET.fromstring(xml_text)
        except (urllib.error.URLError, ET.ParseError):
            return []
        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title = _clean_title(item.findtext("title") or "")
            guid = (item.findtext("guid") or "").strip()
            url = guid or URBANISMO_PAGE
            fecha = _parse_rss_date(item.findtext("pubDate") or "")
            encoded = ""
            enc_el = item.find("{http://purl.org/rss/1.0/modules/content/}encoded")
            if enc_el is not None and enc_el.text:
                encoded = enc_el.text
            pdf_links = [_abs_wp(h) for h in RE_PDF_HREF.findall(encoded)]
            expte_m = RE_EXPTE.search(title)
            rows.append(
                {
                    "titulo": title,
                    "fecha": fecha,
                    "url": url,
                    "pdf_url": pdf_links[0] if pdf_links else None,
                    "expte": expte_m.group(1) if expte_m else None,
                    "origen": "urbanismo_rss",
                }
            )
        return rows

    def _collect_archives(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for year in self.archive_years:
            url = f"{ARCHIVE_BASE}/{year}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for href in RE_PDF_HREF.findall(html):
                pdf_url = _abs_wp(href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                title = _pdf_title_from_url(pdf_url)
                fecha = _parse_fecha_dmy(pdf_url) or f"{year}-01-01"
                rows.append(
                    {
                        "titulo": title,
                        "fecha": fecha,
                        "url": pdf_url,
                        "pdf_url": pdf_url,
                        "origen": f"archivo_{year}",
                    }
                )
        return rows

    def _collect_tramites_info(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRAMITES_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for href in RE_PDF_HREF.findall(html):
            pdf_url = _abs_wp(href)
            title = _pdf_title_from_url(pdf_url)
            rows.append(
                {
                    "titulo": title,
                    "fecha": _parse_fecha_dmy(pdf_url),
                    "url": pdf_url,
                    "pdf_url": pdf_url,
                    "tipo": _proyecto_tipo(title),
                    "origen": "tramites_info",
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 20) -> list[dict[str, Any]]:
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
        data = self._fetch_json(url)
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=150)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper().replace(" ", ""), f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        if RE_EXCLUDE.search(title):
            return None
        cache = self._load_wfs_ambitos()
        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for m in RE_AMBIT_CODE.finditer(title):
            code = m.group(1).upper().replace(" ", "")
            feat = cache.get(code)
            if not feat:
                norm = re.sub(r"([A-Z]+)-?(\d+)", r"\1-\2", code)
                feat = cache.get(norm)
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
                score = sum(1 for p in parts if p in name.lower())
                if score:
                    candidates.append((score * 10.0, name, f))

        if not candidates:
            return None
        candidates.sort(key=lambda x: (-x[0], x[1]))
        best = candidates[0][2]
        geom = best.get("geometry")
        if not isinstance(geom, dict):
            return None
        props = best.get("properties") or {}
        amb = str(props.get("DS_NOMB_AMB") or "")
        cql = f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB='{amb.replace(chr(39), chr(39)*2)}'"
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{self.wfs_url}?CQL_FILTER={urllib.parse.quote(cql)}",
            "coord_source": "portal_geometry_centroid",
        }

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", TRAMITES_URL),
                "fecha_concesion": None,
                "tipo": "trámites licencias de obra",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo — formularios y documentación",
                "url": TRAMITES_URL,
                "source": "ayuntamiento",
                "origen": "tramites_info",
            },
        ]

    def _row_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expte") or row.get("expediente") or row.get("url") or row["titulo"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or row.get("tipo") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expte") or row.get("expediente") or None,
            "url": row.get("url") or self.board_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "tipo")
        )
        if RE_EXCLUDE_PROY.search(blob) or RE_EXCLUDE.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("expte") or row.get("expediente") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row["titulo"]),
            "url": row.get("url") or URBANISMO_PAGE,
            "source": "ayuntamiento",
            "expte": row.get("expte") or row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
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
        for rec in self._licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._row_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites_info():
            rec = self._row_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "tramites_info")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board() + self._collect_tramites_info():
            rec = self._row_to_licencia(item)
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

        for src in (
            self._collect_rss(),
            self._collect_archives(),
            self._collect_board(),
            self._collect_tramites_info(),
        ):
            for item in src:
                add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "rss": sum(1 for r in rows if r.get("origen") == "urbanismo_rss"),
            "archivos": sum(1 for r in rows if str(r.get("origen", "")).startswith("archivo_")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
