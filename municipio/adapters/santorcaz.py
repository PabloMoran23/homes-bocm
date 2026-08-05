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

WEB_BASE = "https://www.ayuntamientosantorcaz.com"
SEDE_BASE = "https://santorcaz.sedelectronica.es"
MUNICIPIO = "Santorcaz"
ID_PREFIX = "santorcaz"

PGOU_URL = f"{WEB_BASE}/pgou-plan-general-de-ordenacion-urbana"
NORMATIVA_URL = f"{WEB_BASE}/normativa-municipal"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "SANTORCAZ"

RE_PREVIEW = re.compile(
    r'href="(https://santorcaz\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|ordenanza fiscal|tpsu|"
    r"utilizaci[oó]n.*suelo|ocupaci[oó]n.*dominio p[uú]blico|"
    r"aprobaci[oó]n (?:inicial|definitiva)|sector|ue-\d|sau-\d|aa-\d)",
)
RE_SKIP = re.compile(
    r"(?i)(contrataci[oó]n menor|adjudicaci[oó]n contrato|liquidaci[oó]n del contrato|"
    r"presupuesto|cierre y liquidaci[oó]n|dictamen cec|subvenci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_BOCM_DATE = re.compile(r"BOCM[- ]?(?:N[- ]?\d+[- ]?)?(\d{4})(\d{2})(\d{2})", re.I)
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:www\.|cms\.)?ayuntamientosantorcaz\.com)?/Ficheros/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_AMBIT_CODE = re.compile(
    r"(?i)(?:UE[\s\-]?\d+|SAU[\s\-]?\d+|AA[\s\-]?\d+)"
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
    m = RE_BOCM_DATE.search(text or "")
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
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _abs_web(href: str) -> str:
    return urllib.parse.urljoin(f"{WEB_BASE}/", unescape(href).replace("&amp;", "&"))


def _normalize_ambit_code(raw: str) -> str:
    t = raw.upper().replace(" ", "").replace("_", "-")
    t = re.sub(r"UE-?(\d+)", lambda m: f"UE-{m.group(1)}", t)
    t = re.sub(r"SAU-?(\d+)", lambda m: f"SAU-{m.group(1)}", t)
    t = re.sub(r"AA-?(\d+)", lambda m: f"AA-{m.group(1)}", t)
    return t


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


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "ordenanza" in n:
        return "ordenanza urbanística"
    if "informaci" in n and "p" in n:
        return "información pública"
    if re.search(r"ue-|sau-|aa-", n):
        return "ámbito PGOU"
    if "tpsu" in n or "suelo" in n:
        return "normativa urbanística"
    return "urbanismo"


class SantorcazAyuntamientoAdapter(AyuntamientoAdapter):
    """Neosoft web + sede espublico gestiona (tablón) + WFS SITCM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.normativa_url = str(self.config.get("normativa_url") or NORMATIVA_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._ambit_names: list[str] | None = None

    def _fetch(self, url: str, use_sede_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santorcaz/1.0")},
        )
        if use_sede_ssl or "sedelectronica" in url:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-santorcaz/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
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
                r'href="(https://santorcaz\.sedelectronica\.es/preview-document/[^"]+)"',
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

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        try:
            html = self._fetch(self.board_url, use_sede_ssl=True)
        except urllib.error.URLError:
            return []
        for rec in self._parse_board_table(html, "tablon"):
            by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_normativa_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.normativa_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_HREF.finditer(html):
            pdf_url = _abs_web(m.group(1))
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            name = Path(pdf_url).name
            if RE_SKIP.search(name) and not RE_PROYECTO.search(name):
                continue
            if not RE_PROYECTO.search(name):
                continue
            rows.append(
                {
                    "titulo": name.replace("-", " ").replace(".pdf", "")[:500],
                    "pdf_url": pdf_url,
                    "url": self.normativa_url,
                    "fecha": _fecha_from_blob(name),
                    "blob": name,
                }
            )
        return rows

    def _collect_pgou_page(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.pgou_url),
            "municipio": MUNICIPIO,
            "titulo": "Plan General de Ordenación Urbana de Santorcaz",
            "fecha": None,
            "tipo": "PGOU",
            "url": self.pgou_url,
            "source": "ayuntamiento",
            "origen": "pgou_web",
        }

    def _load_ambitos(self) -> tuple[list[dict[str, Any]], list[str]]:
        if self._wfs_cache is not None and self._ambit_names is not None:
            return self._wfs_cache, self._ambit_names
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "200",
                "CQL_FILTER": f"DS_MUNICIPIO='{WFS_MUNICIPIO}'",
            }
        )
        url = f"{WFS_BASE}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_cache = []
            self._ambit_names = []
            return self._wfs_cache, self._ambit_names
        feats = [f for f in (data.get("features") or []) if isinstance(f, dict)]
        self._wfs_cache = feats
        self._ambit_names = sorted(
            {str(f.get("properties", {}).get("DS_NOMB_AMB") or "") for f in feats if f.get("properties")}
        )
        return self._wfs_cache, self._ambit_names

    def _match_ambit_name(self, title: str, names: list[str]) -> str | None:
        codes = [_normalize_ambit_code(m.group(0)) for m in RE_AMBIT_CODE.finditer(title)]
        norm_names = {_normalize_ambit_code(n): n for n in names}
        for code in codes:
            for norm, orig in norm_names.items():
                if code == norm or code.replace("-", "") == norm.replace("-", ""):
                    return orig
        t = title.lower()
        best: str | None = None
        best_score = 0
        for name in names:
            nf = name.lower().replace(" ", "")
            score = 0
            for code in codes:
                cl = code.lower().replace(" ", "")
                if cl in nf or nf in cl:
                    score += 15
            if name.lower() in t:
                score += 12
            if score > best_score:
                best_score = score
                best = name
        return best if best_score >= 12 else None

    def _geometry_from_feature(self, feat: dict[str, Any]) -> dict[str, Any] | None:
        geom = feat.get("geometry")
        if not isinstance(geom, dict) or not geom.get("type"):
            return None
        ambit = str(feat.get("properties", {}).get("DS_NOMB_AMB") or "")
        esc = ambit.replace("'", "''")
        cql = f"DS_MUNICIPIO='{WFS_MUNICIPIO}' AND DS_NOMB_AMB='{esc}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "20",
                "CQL_FILTER": cql,
            }
        )
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{WFS_BASE}?{params}",
            "coord_source": "portal_geometry_centroid",
            "geometry_ambit": ambit,
        }

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
        esc = ambit.replace("'", "''")
        cql = f"DS_MUNICIPIO='{WFS_MUNICIPIO}' AND DS_NOMB_AMB='{esc}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "20",
                "CQL_FILTER": cql,
            }
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": f"{WFS_BASE}?{params}",
            "coord_source": "portal_geometry_centroid",
            "geometry_ambit": ambit,
        }

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_wfs_ambitos(self) -> list[dict[str, Any]]:
        feats, _ = self._load_ambitos()
        rows: list[dict[str, Any]] = []
        for feat in feats:
            props = feat.get("properties") or {}
            ambit = str(props.get("DS_NOMB_AMB") or "").strip()
            if not ambit:
                continue
            row: dict[str, Any] = {
                "id": _stable_id("proy", f"wfs:{ambit}"),
                "municipio": MUNICIPIO,
                "titulo": f"PGOU Santorcaz — {ambit}",
                "fecha": None,
                "tipo": "ámbito PGOU",
                "url": self.pgou_url,
                "source": "ayuntamiento",
                "origen": "wfs_sitcm",
            }
            geom_data = self._geometry_from_feature(feat)
            if geom_data:
                row.update(geom_data)
                centroid = geometry_centroid(geom_data["geom_geojson"])
                if centroid:
                    row["lat"], row["lon"] = centroid
            rows.append(row)
        return rows

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        return [
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
                "nota": "Edictos y anuncios publicados en sede espublico gestiona",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta de expedientes (sede electrónica)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; sin listado público de concesiones",
                "origen": "sede_expedientes",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/transparency"),
                "fecha_concesion": None,
                "tipo": "portal transparencia urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Portal de transparencia — Urbanismo, Obras Públicas y Medio Ambiente",
                "url": f"{self.sede_base}/transparency",
                "source": "ayuntamiento",
                "nota": "Documentación urbanística en portal de transparencia (74 docs)",
                "origen": "sede_transparencia",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
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

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
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
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._attach_geometry(rec)
        return rec

    def _normativa_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        blob = rec.get("blob") or rec.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        row: dict[str, Any] = {
            "id": _stable_id("proy", rec["pdf_url"]),
            "municipio": MUNICIPIO,
            "titulo": rec["titulo"],
            "fecha": rec.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": rec.get("url") or self.normativa_url,
            "pdf_url": rec["pdf_url"],
            "source": "ayuntamiento",
            "origen": "normativa_municipal",
        }
        self._attach_geometry(row)
        return row

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
        for rec in self._collect_licencia_info():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            lic = self._board_to_licencia(item)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "source": "ayuntamiento",
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        pgou = self._collect_pgou_page()
        if pgou["id"] not in seen:
            seen.add(pgou["id"])
            rows.append(pgou)

        for row in self._collect_wfs_ambitos():
            if row["id"] not in seen:
                seen.add(row["id"])
                rows.append(row)

        for item in self._collect_board():
            proy = self._board_to_proyecto(item)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)

        for rec in self._collect_normativa_pdfs():
            proy = self._normativa_to_proyecto(rec)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "source": "ayuntamiento",
            "at": datetime.now(timezone.utc).isoformat(),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
