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

WEB_BASE = "https://www.villardelolmo.es"
SEDE_BASE = "https://villardelolmo.sedelectronica.es"
MUNICIPIO = "Villar del Olmo"
ID_PREFIX = "villar-del-olmo"

PGOU_URL = f"{WEB_BASE}/Pagina/plan-general-de-urbanismo"
URBANISMO_URL = f"{WEB_BASE}/servicios-al-ciudadano/territorio-y-medio-ambiente"
TRAMITES_URL = f"{SEDE_BASE}/dossier"

DEFAULT_SEED_PAGES: list[str] = [
    PGOU_URL,
    URBANISMO_URL,
    f"{WEB_BASE}/convenio-agua-eurovillas-/anuncio-bocm-adenda-convenio-del-agua",
    f"{WEB_BASE}/convenio-agua-eurovillas-/propuesta-texto-definitivo-del-convenio-",
    f"{WEB_BASE}/convenio-agua-eurovillas-/borrador-convenio-agua-eurovillas-",
]

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VILLAR DEL OLMO"

DEFAULT_LICENCIA_PDFS: list[dict[str, str]] = [
    {
        "path": "/Ficheros/Documentos/Declaracionresponsabledeobrarellenable.pdf",
        "tipo": "declaración responsable de obra",
        "titulo": "Declaración responsable de obra rellenable",
    },
    {
        "path": "/Ficheros/Documentos/CertificadodeIdoneidadEDI.pdf",
        "tipo": "certificado idoneidad EDI",
        "titulo": "Certificado de idoneidad EDI",
    },
    {
        "path": "/Ficheros/Documentos/ITEFavorable.pdf",
        "tipo": "informe ITE favorable",
        "titulo": "Modelo ITE favorable",
    },
    {
        "path": "/Ficheros/Documentos/ITEDesfavorable.pdf",
        "tipo": "informe ITE desfavorable",
        "titulo": "Modelo ITE desfavorable",
    },
]

RE_PREVIEW = re.compile(
    r'href="(https://villardelolmo\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|obra|actividad)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa|autorizaci[oó]n (?:previa|urban)|obra menor|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n (?:inicial|definitiva|provisional)|"
    r"documento avance|estudio (?:ac[uú]stico|ambiental|de detalle)|modificaci[oó]n|convenio|"
    r"sector|unidad de ejecuci[oó]n|eurovillas|ordenaci[oó]n|calificaci[oó]n|"
    r"encuadre territorial|estructura catastral|gesti[oó]n [aá]mbitos|bocm|"
    r"plano|memoria|anexo|catalogo|die\b|nue\d|tme\d|po0\d|inf0\d|"
    r"\b(?:UE|SAU|NUE|PAU)-[\w\d-]+\b)",
)
RE_SKIP = re.compile(
    r"(?i)(presupuesto|calendario fiscal|cobranza iae|censo electoral|"
    r"acta de pleno|borrador de acta|colonias felinas|punto limpio|"
    r"contenedor amarillo|programa de gesti[oó]n de colonias)",
)
RE_PDF_LINK = re.compile(
    r'<a\s+href="([^"]+\.pdf[^"]*)"[^>]*?(?:tittle|title)="([^"]*)"[^>]*>([^<]*)</a>'
    r'|<a\s+href="([^"]+\.pdf[^"]*)"[^>]*>([^<]*)</a>',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_BOCM_DATE = re.compile(r"BOCM[-_]?(\d{4})(\d{2})(\d{2})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_BOCM_DATE.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _abs_url(href: str, base: str = WEB_BASE) -> str:
    return urllib.parse.urljoin(f"{base}/", unescape(href).replace("&amp;", "&"))


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "documento avance" in n or "pgou" in n or "plan general" in n:
        return "PGOU"
    if "nnss" in n or "normas subsidiarias" in n:
        return "normas subsidiarias"
    if "convenio" in n:
        return "convenio urbanístico"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "memoria" in n:
        return "memoria urbanística"
    if "plano" in n or "ordenaci" in n or "calificaci" in n:
        return "planeamiento"
    if "anexo" in n:
        return "anexo normativa"
    if "eurovillas" in n:
        return "plan especial Eurovillas"
    if re.search(r"\bnue\d", n):
        return "núcleo de población"
    return "urbanismo"


class VillarDelOlmoAyuntamientoAdapter(AyuntamientoAdapter):
    """Neosoft web (PGOU documento avance + normativa) + sede espublico tablón + WFS SITCM."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
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
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-villar-del-olmo/1.0")},
        )
        if "sedelectronica" in url:
            resp_ctx = self._opener.open(req, timeout=60)
        else:
            resp_ctx = urllib.request.urlopen(req, timeout=60)
        with resp_ctx as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _parse_pdf_links(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_PDF_LINK.finditer(html):
            href = m.group(1) or m.group(4) or ""
            tittle = _clean_title(m.group(2) or "")
            anchor = _clean_title(m.group(3) or m.group(5) or "")
            pdf_url = _abs_url(href)
            if pdf_url in seen:
                continue
            seen.add(pdf_url)
            title = tittle or anchor or Path(pdf_url).stem.replace("-", " ").replace("_", " ")
            rows.append(
                {
                    "titulo": title[:500],
                    "pdf_url": pdf_url,
                    "url": page_url,
                    "fecha": _parse_fecha_dmy(f"{title} {pdf_url}"),
                    "blob": f"{title} {pdf_url}",
                }
            )
        return rows

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbody_m.group(1), re.S | re.I):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 4:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _clean_title(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            expediente = _clean_title(cells[1]) if len(cells) > 1 else ""
            procedimiento = _clean_title(cells[2]) if len(cells) > 2 else ""
            categoria = _clean_title(cells[3]) if len(cells) > 3 else ""
            descripcion = _clean_title(cells[4]) if len(cells) > 4 else titulo
            fecha_cell = _clean_title(cells[5]) if len(cells) > 5 else ""
            url = link_m.group(1) if link_m else self.board_url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": expediente,
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion,
                    "fecha": _parse_fecha_dmy(fecha_cell) or _parse_fecha_dmy(titulo),
                    "url": url,
                    "pdf_url": url,
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
                    "fecha": _parse_fecha_dmy(titulo),
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

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            rows.extend(self._parse_pdf_links(html, page_url))
        return rows

    def _collect_pgou_page(self) -> dict[str, Any]:
        return {
            "id": _stable_id("proy", self.pgou_url),
            "municipio": MUNICIPIO,
            "titulo": "Documento Avance PGOU Villar del Olmo — exposición pública",
            "fecha": "2025-11-28",
            "tipo": "PGOU",
            "url": self.pgou_url,
            "source": "ayuntamiento",
            "origen": "pgou_web",
            "nota": "Exposición pública 45 días desde BOCM 28/11/2025",
        }

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("licencia_pdfs") or DEFAULT_LICENCIA_PDFS:
            pdf_url = _abs_url(str(item["path"]))
            rows.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": None,
                    "tipo": item["tipo"],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": self.urbanismo_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "nota": "Formulario/trámite informativo; no concesión publicada",
                    "origen": "tramites_formularios",
                }
            )
        rows.extend(
            [
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
                    "nota": "Anuncios y exposiciones públicas en sede espublico gestiona",
                    "origen": "sede_tablon",
                },
                {
                    "id": _stable_id("lic", self.tramites_url),
                    "fecha_concesion": None,
                    "tipo": "trámites urbanismo sede",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Catálogo de trámites — urbanismo y licencias",
                    "url": self.tramites_url,
                    "source": "ayuntamiento",
                    "nota": "Licencias de obra, actividad y declaración responsable vía sede",
                    "origen": "sede_tramite",
                },
                {
                    "id": _stable_id("lic", f"{self.sede_base}/transparency"),
                    "fecha_concesion": None,
                    "tipo": "portal transparencia urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Portal de transparencia — urbanismo y medio ambiente",
                    "url": f"{self.sede_base}/transparency",
                    "source": "ayuntamiento",
                    "nota": "Documentación urbanística en portal de transparencia",
                    "origen": "sede_transparencia",
                },
            ]
        )
        return rows

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
        if RE_SKIP.search(titulo or ""):
            return None
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if not geom:
            return None
        name = str(meta.get("ambito_name") or "")
        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
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
            merged = _merge_geometries(
                [x for x in feats if str((x.get("properties") or {}).get("DS_NOMB_AMB")) == name]
            )
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": self.pgou_url,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39) * 2)}'"
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

    def _pdf_to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any] | None:
        blob = rec.get("blob") or rec.get("titulo") or ""
        if RE_SKIP.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        title = rec["titulo"]
        row: dict[str, Any] = {
            "id": _stable_id("proy", rec["pdf_url"]),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": rec.get("fecha"),
            "tipo": _proyecto_tipo(title),
            "url": rec.get("url") or self.pgou_url,
            "pdf_url": rec["pdf_url"],
            "source": "ayuntamiento",
            "origen": "urbanismo_pdf",
        }
        self._attach_geometry(row)
        return row

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_SKIP.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia / obra",
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
        if RE_SKIP.search(blob):
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
            "fecha": row.get("fecha") or _parse_fecha_dmy(row["titulo"]),
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
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "formularios": sum(1 for r in rows if r.get("origen") == "tramites_formularios"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            lic = self._board_to_licencia(item)
            if lic:
                existing[lic["id"]] = lic
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

        pgou = self._collect_pgou_page()
        add(pgou)

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
            "pgou_web": sum(1 for r in rows if r.get("origen") == "pgou_web"),
            "urbanismo_pdf": sum(1 for r in rows if r.get("origen") == "urbanismo_pdf"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
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
