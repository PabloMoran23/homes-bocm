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
from municipio.gis.sitcm import _merge_geometries, resolve_ambito_geometry

WP_BASE = "https://www.mirafloresdelasierra.es"
SEDE_BASE = "https://mirafloresdelasierra.sedelectronica.es"
MUNICIPIO = "Miraflores de la Sierra"
ID_PREFIX = "miraflores-de-la-sierra"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "MIRAFLORES DE LA SIERRA"

URBANISMO_URL = f"{WP_BASE}/servicios-municipales/urbanismo/"
SOLICITUDES_URL = f"{WP_BASE}/tramites/solicitudes-e-inscripciones/"
BOARD_URL = f"{SEDE_BASE}/board/"

DEFAULT_SEED_PAGES: list[str] = [
    URBANISMO_URL,
    SOLICITUDES_URL,
    f"{WP_BASE}/ayuntamiento/ordenanzas-municipales/",
]

RE_PREVIEW = re.compile(
    r'href="(https://mirafloresdelasierra\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://mirafloresdelasierra\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|"
    r"primera ocupaci[oó]n|terrazas|veladores|actividad)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"edicto|bocm|ordenanza|normas urban|gu[ií]a.*tramitaci|"
    r"\b(?:PU|PP|UE|UA|AD|AN|AI|PAU|S)-[\w\d-]+\b)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|funcionario|proceso selectivo|"
    r"plusvalia|basura|residuos|vehiculos|igualdad|polic[ií]a local|"
    r"monitor deportivo|pleno|convocatoria pln|tribunal calificador|"
    r"ornitol[oó]gica|fiesta|cine |teatro|alumbrado exterior|cielo nocturno)",
)
RE_PDF_HREF = re.compile(
    r'href=["\']((?:https?://(?:www\.)?mirafloresdelasierra\.es)?/[^"\']+\.pdf[^"\']*)["\']',
    re.I,
)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads|images)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bpp-\d+\b", n):
        return "plan parcial"
    if re.search(r"\bpu-\d+\b", n):
        return "plan urbanístico"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "pgou" in n or "plan general" in n:
        return "planeamiento"
    if "ordenanza" in n or "normas urban" in n:
        return "ordenanza urbanística"
    if "guía" in n and "tramitaci" in n:
        return "guía tramitación"
    if "informaci" in n:
        return "información pública"
    if "modificaci" in n:
        return "modificación planeamiento"
    return "urbanismo"


class MirafloresDeLaSierraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Elementor + sede espublico gestiona + ámbitos SITCM WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.solicitudes_url = str(self.config.get("solicitudes_url") or SOLICITUDES_URL)
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

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-miraflores-de-la-sierra/1.0")},
        )
        with self._opener.open(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

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
                        "pdf_url": doc_url if "preview-document" in doc_url else None,
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

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{self.sede_base}/dossier")
        except urllib.error.URLError:
            return []
        if len(html) < 100:
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
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            m = re.search(r"<h1[^>]*>([^<]+)", html, re.I)
            if m:
                page_title = _strip_html(m.group(1))
            for m in RE_PDF_HREF.finditer(html):
                pdf = self._abs_wp(m.group(1))
                if pdf in seen:
                    continue
                seen.add(pdf)
                ctx = html[max(0, m.start() - 200) : m.end() + 50]
                text_m = re.search(r">([^<]{3,120})</a>", ctx)
                link_text = _strip_html(text_m.group(1)) if text_m else ""
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                titulo = link_text or name.replace("-", " ").replace("_", " ")
                blob = f"{page_title} {titulo} {pdf}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    if page_url != self.urbanismo_url:
                        continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": page_url,
                        "pdf_url": pdf,
                        "fecha": _fecha_from_blob(pdf + " " + titulo),
                        "origen": "wp_pdf",
                        "page_title": page_title,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tramites: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "urbanismo — trámites y normativa",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — licencias y expedientes",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Normas urbanísticas, guía tramitación, solicitudes obra",
                "origen": "wp_urbanismo",
            },
            {
                "id": _stable_id("lic", self.solicitudes_url),
                "fecha_concesion": None,
                "tipo": "solicitudes licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitudes e inscripciones — impresos licencias",
                "url": self.solicitudes_url,
                "source": "ayuntamiento",
                "nota": "Obra mayor/menor, primera ocupación, terrazas",
                "origen": "wp_tramite",
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
        ]
        for item in self._collect_seed_pdfs():
            blob = f"{item.get('titulo', '')} {item.get('pdf_url', '')}"
            if not RE_LICENCIA.search(blob):
                continue
            pdf_url = str(item.get("pdf_url") or "")
            tramites.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": item.get("fecha"),
                    "tipo": "impreso licencia / trámite",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "wp_pdf_tramite",
                    "pdf_url": pdf_url,
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

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if RE_EXCLUDE.search(titulo or ""):
            return None
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if not geom:
            return None
        name = str(meta.get("ambito_name") or "")
        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
            f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
        ) if name else ""
        return {
            "geom_geojson": geom,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                if cql
                else self.wfs_url
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": name or None,
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
        seen_names: set[str] = set()
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name or name in seen_names:
                continue
            seen_names.add(name)
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

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')} {row.get('page_title', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or row.get("pdf_url") or self.urbanismo_url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria")
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
            "nota": "Página informativa de trámite",
            "origen": row.get("origen"),
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
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "info": sum(1 for r in rows if str(r.get("origen", "")).startswith(("wp_", "sede_"))),
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

        for item in self._collect_seed_pdfs():
            add(self._pdf_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wp_pdf": sum(1 for r in rows if r.get("origen") == "wp_pdf"),
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
