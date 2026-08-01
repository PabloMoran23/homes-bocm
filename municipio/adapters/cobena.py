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

WEB_BASE = "https://www.ayto-cobena.org"
SEDE_BASE = "https://sede.ayto-cobena.org"
TABLON_URL = f"{SEDE_BASE}/PortalCiudadano/Tablon/wfrTablon.aspx"
MUNICIPIO = "Cobeña"
ID_PREFIX = "cobena"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "COBEÑA"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/tu-ayuntamiento/normativa/planeamiento",
    f"{WEB_BASE}/tu-ayuntamiento/normativa/planeamiento/nnss-1995",
    f"{WEB_BASE}/tu-ayuntamiento/normativa/planeamiento/p-parcial",
    f"{WEB_BASE}/tu-ayuntamiento/normativa/planeamiento/proy-reparcelacion",
    f"{WEB_BASE}/tu-ayuntamiento/normativa/planeamiento/p-urbanizacion",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|modificaci[oó]n|aprobaci[oó]n|"
    r"proyecto de urbaniz|sector|sau-|ue-|u34-|bocm|anuncio)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|bolsa|tribunal|seguridad|esquema nacional|"
    r"politica de seguridad|pleno|convocatoria sesion|regimen presupuestario)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|SAU|U34|AD|AN|AI|PAU|S)-\d+[A-Z0-9-]*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_LIST_GROUP = re.compile(
    r'class="list-group-item"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
RE_MEDIA_LINK = re.compile(
    r'href="(/media/[^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)
RE_TABLON_ROW = re.compile(r'class="dxgvDataRow[^"]*">(.*?)</tr>', re.S | re.I)


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"bocm[^0-9]*(\d{1,3})[^0-9]+(\d{4})", text or "", re.I)
    if m:
        return f"{m.group(2)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "reparcel" in n:
        return "reparcelación"
    if "urbaniz" in n:
        return "proyecto de urbanización"
    if "plan parcial" in n or re.search(r"\bsau-\d", n):
        return "plan parcial"
    if "modificaci" in n or "nnss" in n or "normas subsidiarias" in n:
        return "modificación planeamiento"
    if "informaci" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    return "planeamiento"


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" bocm", " aprob", " anuncio", " del ", " de cobe"):
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


def _abs_web(href: str) -> str:
    href = unescape(href).replace("&amp;", "&")
    return urllib.parse.urljoin(f"{WEB_BASE}/", href)


class CobenaAyuntamientoAdapter(AyuntamientoAdapter):
    """Fontventa CMS (planeamiento PDFs) + sede ATM tablón + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: dict[str, dict[str, Any]] | None = None
        self._sede_warmed = False

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-cobena/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _warm_sede(self) -> None:
        if self._sede_warmed:
            return
        try:
            self._fetch(f"{self.sede_base}/")
            self._sede_warmed = True
        except urllib.error.URLError:
            pass

    def _fetch_tablon_html(self) -> str:
        self._warm_sede()
        req = urllib.request.Request(
            self.tablon_url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-cobena/1.0"),
                "Referer": f"{self.sede_base}/",
            },
        )
        time.sleep(self.delay_s)
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _page_title(self, html: str, fallback: str = "") -> str:
        m = RE_H1.search(html)
        if m:
            return _strip_html(m.group(1))[:500]
        m = re.search(r"<title>([^<]+)", html, re.I)
        if m:
            t = _strip_html(m.group(1))
            t = re.sub(r"\s*[-|].*Ayto.*$", "", t, flags=re.I).strip()
            if t:
                return t[:500]
        return fallback

    def _collect_planeamiento_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            section = self._page_title(html, page_url.rsplit("/", 1)[-1])

            for m in RE_LIST_GROUP.finditer(html):
                href, label_raw = m.group(1), m.group(2)
                label = _strip_html(label_raw)
                if not label or label.lower().startswith("ver documento"):
                    label = Path(unescape(href)).name.replace("-", " ")
                pdf_url = _abs_web(href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                titulo = label if len(label) > 8 else f"{section}: {label}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{titulo} {pdf_url}"),
                        "tipo": _proyecto_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "planeamiento_web",
                        "section": section,
                    }
                )

            for m in RE_MEDIA_LINK.finditer(html):
                href, label_raw = m.group(1), m.group(2)
                label = _strip_html(label_raw)
                if "list-group-item" in label_raw:
                    continue
                pdf_url = _abs_web(href)
                if pdf_url in seen:
                    continue
                seen.add(pdf_url)
                if label.lower() in ("ver documento", ""):
                    label = Path(unescape(href)).name.replace("-", " ")
                titulo = label if len(label) > 8 else f"{section}: {label}"
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(f"{titulo} {pdf_url}"),
                        "tipo": _proyecto_tipo(titulo),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "planeamiento_web",
                        "section": section,
                    }
                )

            ann = re.search(
                r'href="(/documentos/[^"]+\.pdf)"[^>]*>([^<]+)',
                html,
                re.I,
            )
            if ann:
                pdf_url = _abs_web(ann.group(1))
                if pdf_url not in seen:
                    seen.add(pdf_url)
                    titulo = _strip_html(ann.group(2)) or section
                    rows.append(
                        {
                            "titulo": titulo[:500],
                            "fecha": _fecha_from_blob(titulo),
                            "tipo": _proyecto_tipo(titulo),
                            "url": page_url,
                            "pdf_url": pdf_url,
                            "origen": "planeamiento_web",
                            "section": section,
                        }
                    )

        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch_tablon_html()
        except urllib.error.URLError:
            return []
        if "NO DISPONIBLE" in html:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            raw = _strip_html(m.group(1))
            if not raw or "Cargando" in raw:
                continue
            fecha = _parse_fecha_dmy(raw)
            titulo = raw
            if fecha:
                titulo = raw.split(fecha, 1)[-1].strip()
            titulo = re.sub(r"\s+URBANISMO\s*$", "", titulo, flags=re.I).strip()
            categoria = "URBANISMO" if "URBANISMO" in raw.upper() else ""
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": self.tablon_url,
                    "categoria": categoria,
                    "origen": "tablon_sede",
                    "blob": raw,
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "1.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "CQL_FILTER": cql,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "maxFeatures": str(count),
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
        cache = self._load_wfs_ambitos()
        if not cache:
            return None

        code_m = RE_AMBIT_CODE.search(title or "")
        if code_m:
            key = code_m.group(1).upper().replace(" ", "")
            feat = cache.get(key)
            if feat:
                merged = _merge_geometries([feat])
                if merged:
                    cql = (
                        f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
                        f"AND DS_COD_AMB ILIKE '%{code_m.group(1).replace(chr(39), chr(39)*2)}%'"
                    )
                    return {
                        "geom_geojson": merged,
                        "geometry_source": "portal_wfs",
                        "geometry_source_url": (
                            f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                        ),
                        "coord_source": "portal_geometry_centroid",
                    }

        parts = _sector_ilike_parts(title)
        candidates: list[tuple[int, str, dict[str, Any]]] = []
        for name_key, feat in cache.items():
            props = feat.get("properties") or {}
            amb_name = str(props.get("DS_NOMB_AMB") or name_key)
            amb_low = amb_name.lower()
            score = 0
            for p in parts:
                if p in amb_low:
                    score += len(p)
            if score > 0:
                candidates.append((score, amb_name, feat))
        if not candidates:
            return None
        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_name = candidates[0][1]
        same_name = [
            f
            for _, name, f in candidates
            if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "") == best_name
        ]
        merged = _merge_geometries(same_name or [candidates[0][2]])
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón electrónico — edictos y anuncios urbanísticos",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Concesiones y edictos publicados en sede ATM; requiere sesión",
                "origen": "tablon_sede",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos y licencias",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Presentación de solicitudes; concesiones en tablón cuando proceda",
                "origen": "sede_tramites",
            },
        ]

    def _doc_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("pdf_url") or row["titulo"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row["titulo"]),
            "url": row.get("url") or self.web_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if row.get("categoria") != "URBANISMO" and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["titulo"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row["titulo"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _build_proyectos(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in self._collect_planeamiento_docs():
            rec = self._doc_to_proyecto(row)
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        for row in self._collect_tablon():
            rec = self._tablon_to_proyecto(row)
            if not rec or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        return out

    def _build_licencias(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rec in self._collect_licencia_info_pages():
            if rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        for row in self._collect_tablon():
            rec = self._tablon_to_licencia(row)
            if not rec or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            out.append(rec)
        return out

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return len(rows)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._build_licencias()
        n = self._write_jsonl(out_jsonl, rows)
        return {
            "ok": True,
            "rows": n,
            "source": "ayuntamiento",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._build_proyectos()
        n = self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "ok": True,
            "rows": n,
            "with_geometry": with_geom,
            "source": "ayuntamiento",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
