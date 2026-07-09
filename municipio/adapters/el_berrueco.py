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

SEDE_BASE = "https://elberrueco.sedelectronica.es"
MUNICIPIO = "El Berrueco"
ID_PREFIX = "el-berrueco"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "EL BERRUECO"

VISUALURB_UE10_URL = (
    "https://www.visualurb.es/el-berrueco-abril-2021-aprobacion-definitiva-de-la-"
    "modificacion-puntual-con-ordenacion-pormenorizada-de-las-normas-subsidiarias-"
    "de-planeamiento-municipal-de-el-berrueco/"
)

RE_PREVIEW = re.compile(
    r'href="(https://elberrueco\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="(https://elberrueco\.sedelectronica\.es/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|unidad(?:es)? de ejecuci[oó]n|"
    r"\b(?:UE|AD|AN|AI|PAU|S)-\d+\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleado|plusvalia|basura|"
    r"residuos|vehiculos|notificaci[oó]n expediente|igualdad|cineg[eé]t)",
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:UE|AD|AN|AI|PAU|S)-\d+[A-Z0-9-]*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_FECHA_VISUALURB = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")


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
    m = RE_FECHA_VISUALURB.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bue-\d+\b", n) or "unidad de ejecuci" in n:
        return "unidad de ejecución"
    if "informaci" in n:
        return "información pública"
    if "planeamiento" in n or "pgou" in n or "nnss" in n or "normas subsidiarias" in n:
        return "planeamiento"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "convenio" in n:
        return "convenio"
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


class ElBerruecoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona: tablón + catálogo trámites + ámbitos SIT WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.transparency_url = str(
            self.config.get("transparency_url") or f"{self.sede_base}/transparency/"
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

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-el-berrueco/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

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
                r'href="(https://elberrueco\.sedelectronica\.es/preview-document/[^"]+)"',
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
        for url, origen in ((self.board_url, "tablon"), (f"{self.sede_base}/info.0", "info_tablon")):
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
            url, titulo = m.group(1), unescape(m.group(2).strip())
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
                "id": _stable_id("lic", self.transparency_url),
                "fecha_concesion": None,
                "tipo": "portal transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia — Urbanismo, obras públicas y medio ambiente",
                "url": self.transparency_url,
                "source": "ayuntamiento",
                "nota": "Documentación PGOU/NNSS y modificaciones (navegación Wicket)",
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
                "url": self.transparency_url,
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

    def _collect_visualurb_seed(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(VISUALURB_UE10_URL)
        except urllib.error.URLError:
            return []
        title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
        titulo = _strip_html(title_m.group(1)) if title_m else (
            "Aprobación definitiva modificación puntual NNSS UE-10 El Egio"
        )
        titulo = re.sub(r"\s*-\s*VisualUrb\s*$", "", titulo, flags=re.I).strip()
        fecha = _fecha_from_blob(html[:3000])
        rec: dict[str, Any] = {
            "id": _stable_id("proy", VISUALURB_UE10_URL),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": "modificación planeamiento",
            "url": VISUALURB_UE10_URL,
            "source": "ayuntamiento",
            "origen": "visualurb_publicacion",
            "nota": "Publicación en VisualUrb; documentación en transparencia sede",
        }
        self._enrich_geometry(rec)
        return [rec]

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
            if row.get("categoria") != "Órganos de gobierno":
                return None
            if not re.search(r"(?i)pleno|convocatoria|acuerdo", blob):
                return None
        tipo = _proyecto_tipo(blob)
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": tipo,
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
        if RE_EXCLUDE.search(row["titulo"]):
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
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "transparencia")),
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._tramite_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)
        for rec in self._collect_visualurb_seed():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "visualurb": sum(1 for r in rows if r.get("origen") == "visualurb_publicacion"),
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
