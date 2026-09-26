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

WP_BASE = "https://horcajuelodelasierra.es"
SEDE_BASE = "https://horcajuelodelasierra.sedelectronica.es"
EADMIN_URL = (
    "https://sedehorcajuelodelasierra.eadministracion.es/"
    "PortalCiudadano/Menus/wfrBienvenida.aspx?param=MjgmMDcx"
)
MUNICIPIO = "Horcajuelo de la Sierra"
ID_PREFIX = "horcajuelo-de-la-sierra"
WFS_MUNICIPIO = "HORCAJUELO DE LA SIERRA"
CD_MUNICIPIO = "071"
VISOR_URL = "https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=071"

ORDENACION_URL = (
    f"{WP_BASE}/portal-transparencia/ordenacion-del-territorio-y-obras-publicas/"
)
ORDENANZAS_URL = f"{WP_BASE}/ayuntamiento/normativa-municipal/ordenanzas-municipales/"
TRAMITES_URL = f"{WP_BASE}/ayuntamiento/tramites/"
LICENCIA_PDF = f"{WP_BASE}/wp-content/uploads/2025/12/MODELO-DE-LICENCIA-URBANISTICA.pdf"
ORDENANZA_LICENCIAS_PDF = (
    f"{WP_BASE}/wp-content/uploads/2025/10/ORDENANZA_4_LICENCIAS_Y_D_RESPONSABLE.pdf"
)

DEFAULT_SEED_PAGES: list[str] = [
    ORDENACION_URL,
    ORDENANZAS_URL,
    TRAMITES_URL,
]

RE_PREVIEW = re.compile(
    r'href="(https://horcajuelodelasierra\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|"
    r"obra mayor|primera ocupaci[oó]n|modelo de licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|edicto|reparcel|aprobaci[oó]n|modificaci[oó]n|"
    r"sector|convenio|urbanizaci[oó]n|unidad(?:es)? de ejecuci[oó]n|actuaci[oó]n|"
    r"expediente|catalogo|cat[aá]logo|ordenaci[oó]n|calificaci[oó]n|clasificaci[oó]n|"
    r"memoria|planos|nurbanistic|patrimonio|nucleo|n[uú]cleo|viario|equipamiento|"
    r"acuerdo|decreto|bocm|ampliaci[oó]n|conservaci[oó]n|edificaci[oó]n tradicional)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(fiestas|empleo|piscina|navidad|halloween|whatsapp|subvenci[oó]n|"
    r"arrendamiento vivienda|concurso|mesa|convocatoria pleno|ibi\b|basura|"
    r"vehiculos|cementerio|matrimonio|uniones de hecho|fotocopiadora|"
    r"hayedo|reserva de la biosfera|turismo|senda|ermita|molino)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(r'href="((?:https?://[^"]+|/[^"]+)\.pdf[^"]*)"', re.I)
RE_H1 = re.compile(r"<h1[^>]*>([^<]+)", re.I)


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "pgou" in n or "plan general" in n or "avance" in n:
        return "plan general"
    if "catalogo" in n or "catálogo" in n:
        return "catálogo urbanístico"
    if "memoria" in n:
        return "memoria urbanística"
    if "planos" in n or "ordenaci" in n or "clasificaci" in n or "calificaci" in n:
        return "planos de ordenación"
    if "nucleo" in n or "núcleo" in n:
        return "ordenanza núcleo"
    if "viario" in n:
        return "ordenanza viario"
    if "equipamiento" in n:
        return "equipamientos urbanos"
    if "conservaci" in n:
        return "conservación edificación"
    if "acuerdo" in n:
        return "acuerdo plenario"
    return "planeamiento"


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


def _normalize_token(s: str) -> str:
    t = unescape(s or "").upper()
    t = re.sub(r"[ÁÀÄ]", "A", t)
    t = re.sub(r"[ÉÈË]", "E", t)
    t = re.sub(r"[ÍÌÏ]", "I", t)
    t = re.sub(r"[ÓÒÖ]", "O", t)
    t = re.sub(r"[ÚÙÜ]", "U", t)
    t = re.sub(r"[^A-Z0-9]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


class HorcajueloDeLaSierraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Avada + transparencia PDFs + espublico sede + WFS ORDENANZA_REF_23 (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.eadmin_url = str(self.config.get("eadmin_url") or EADMIN_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or "https://idem.comunidad.madrid/geoserver3/ows")
        self.wfs_type = str(geom_cfg.get("type_name") or "sitcm:VPLA_V_ORDENANZA_REF_23")
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self.cd_municipio = str(geom_cfg.get("cd_municipio") or CD_MUNICIPIO)
        self.visor_url = str(geom_cfg.get("visor_url") or VISOR_URL)
        self._wfs_ordenanzas: dict[str, list[dict[str, Any]]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

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

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            h1_m = RE_H1.search(html)
            page_title = _strip_html(h1_m.group(1)) if h1_m else page_url
            pdfs = self._extract_pdfs(html)
            for pdf_url in pdfs:
                label = Path(urllib.parse.urlparse(pdf_url).path).name.replace("-", " ").replace("_", " ")
                rows.append(
                    {
                        "titulo": f"{page_title} — {label}"[:500],
                        "fecha": _fecha_from_url(pdf_url) or ("2023-07-01" if "/2023/07/" in pdf_url else None),
                        "url": page_url,
                        "pdf_url": pdf_url,
                        "origen": "wp_seed_pdf",
                    }
                )
            if page_url == ORDENACION_URL and not any(r.get("origen") == "wp_pgou_index" for r in rows):
                rows.append(
                    {
                        "titulo": "Ordenación del territorio — avance PGOU / NNSS Horcajuelo de la Sierra",
                        "fecha": "2023-07-01",
                        "url": ORDENACION_URL,
                        "origen": "wp_pgou_index",
                        "nota": "Documentación completa de planeamiento (acuerdo, memoria, catálogo, normas, planos)",
                    }
                )
        return rows

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr or "emptyRow" in tr:
                continue
            cells = [_strip_html(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(cells) < 2:
                continue
            link_m = RE_PREVIEW.search(tr)
            doc_url = link_m.group(1) if link_m else self.board_url
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = (title_m.group(1).strip() if title_m else "") or cells[0]
            fecha = _parse_fecha_dmy(cells[5]) if len(cells) > 5 else _parse_fecha_dmy(titulo)
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
                "tipo": "tablón de anuncios sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Exposiciones públicas y anuncios (espublico gestiona)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.eadmin_url),
                "fecha_concesion": None,
                "tipo": "sede e-Administración",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tramitación electrónica de licencias urbanísticas",
                "url": self.eadmin_url,
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de concesiones",
                "origen": "eadmin_tramite",
            },
            {
                "id": _stable_id("lic", TRAMITES_URL),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (formularios)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites — formularios de urbanismo",
                "url": TRAMITES_URL,
                "source": "ayuntamiento",
                "nota": "Modelo de licencia urbanística descargable",
                "origen": "wp_tramite",
            },
            {
                "id": _stable_id("lic", LICENCIA_PDF),
                "fecha_concesion": "2025-12-01",
                "tipo": "modelo licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Modelo de licencia urbanística",
                "url": LICENCIA_PDF,
                "source": "ayuntamiento",
                "origen": "wp_form_pdf",
            },
            {
                "id": _stable_id("lic", ORDENANZA_LICENCIAS_PDF),
                "fecha_concesion": "2025-10-01",
                "tipo": "ordenanza licencias y declaración responsable",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Ordenanza 4 — Licencias y declaración responsable",
                "url": ORDENANZA_LICENCIAS_PDF,
                "source": "ayuntamiento",
                "origen": "wp_ordenanza",
            },
        ]

    def _wfs_query(self, cql: str, count: int = 200) -> list[dict[str, Any]]:
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

    def _load_wfs_ordenanzas(self) -> dict[str, list[dict[str, Any]]]:
        if self._wfs_ordenanzas is not None:
            return self._wfs_ordenanzas
        cql = f"CD_MUNICIPIO='{self.cd_municipio.replace(chr(39), chr(39)*2)}'"
        feats = self._wfs_query(cql, count=200)
        grouped: dict[str, list[dict[str, Any]]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_ORD") or "").strip()
            if name:
                grouped.setdefault(name, []).append(f)
        self._wfs_ordenanzas = grouped
        return grouped

    def _match_ordenanza(self, title: str) -> str | None:
        title_norm = _normalize_token(title)
        if not title_norm:
            return None
        aliases = {
            "AMPLIACIÓN DE NÚCLEO": ("AMPLIACION NUCLEO", "NUCLEO", "AMPLIACION"),
            "CONSERVACIÓN DE LA EDIFICACIÓN TRADICIONAL": (
                "CONSERVACION EDIFICACION TRADICIONAL",
                "EDIFICACION TRADICIONAL",
                "CONSERVACION",
            ),
            "EQUIPAMIENTOS Y SERVICIOS URBANOS": ("EQUIPAMIENTOS", "SERVICIOS URBANOS", "EQUIPAMIENTO"),
            "NUEVA EDIFICACIÓN EN NÚCLEO TRADICIONAL": (
                "NUEVA EDIFICACION NUCLEO TRADICIONAL",
                "NUCLEO TRADICIONAL",
            ),
            "VIARIO Y ESPACIOS LIBRES": ("VIARIO", "ESPACIOS LIBRES"),
        }
        best_name: str | None = None
        best_score = 0
        for name, tokens in aliases.items():
            score = 0
            name_norm = _normalize_token(name)
            if name_norm in title_norm or title_norm in name_norm:
                score += 10
            for tok in tokens:
                if tok in title_norm:
                    score += 5
            if score > best_score:
                best_score = score
                best_name = name
        return best_name if best_score >= 5 else None

    def _geometry_from_ordenanza(self, ordenanza_name: str) -> dict[str, Any] | None:
        grouped = self._load_wfs_ordenanzas()
        feats = grouped.get(ordenanza_name) or []
        merged = _merge_geometries(feats)
        if not merged:
            return None
        cql = (
            f"CD_MUNICIPIO='{self.cd_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_ORD='{ordenanza_name.replace(chr(39), chr(39)*2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ordenanza_sit": ordenanza_name,
        }

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        match = self._match_ordenanza(title)
        if match:
            return self._geometry_from_ordenanza(match)
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

    def _collect_sit_ordenanzas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for name, feats in self._load_wfs_ordenanzas().items():
            clas = str((feats[0].get("properties") or {}).get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {clas}" if clas else name
            merged = _merge_geometries(feats)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit_ord:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": str((feats[0].get("properties") or {}).get("FC_REF") or "")[:10] or None,
                "tipo": _proyecto_tipo(name),
                "url": self.visor_url,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ordenanza_sit": name,
            }
            if merged:
                cql = (
                    f"CD_MUNICIPIO='{self.cd_municipio.replace(chr(39), chr(39)*2)}' "
                    f"AND DS_NOMB_ORD='{name.replace(chr(39), chr(39)*2)}'"
                )
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
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
        return " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))

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

    def _item_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('pdf_url') or ''} {row.get('nota') or ''}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["url"]
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
            "info": sum(
                1
                for r in rows
                if r.get("origen")
                in ("sede_tablon", "eadmin_tramite", "wp_tramite", "wp_form_pdf", "wp_ordenanza")
            ),
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

        for seed in self._collect_seed_pages():
            add(self._item_to_proyecto(seed))
        for board in self._collect_board():
            add(self._board_to_proyecto(board))
        for rec in self._collect_sit_ordenanzas():
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
