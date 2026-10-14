from __future__ import annotations

import hashlib
import json
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.perales_de_tajuna import PeralesDeTajunaAyuntamientoAdapter
from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry
from municipio.gis.sitcm import WFS_BASE, _merge_geometries

ID_PREFIX = "perales-de-tajuna-y-tielmes"

PERALES_WEB = "https://www.ayto-peralestajuna.org"
PERALES_SEDE = "https://ayto-peralestajuna.sedelectronica.es"

TIELMES_WEB = "https://www.tielmes.es"
TIELMES_SEDE = "https://tielmes.sedelectronica.es"
TIELMES_LICENCIAS_URL = f"{TIELMES_WEB}/licencias-y-urbanismo"
TIELMES_CANTARRANAS_URL = (
    f"{TIELMES_WEB}/informacion-publica-y-consulta-de-calificacion-urbanistica-en-la-finca-molino-de-cantarranas"
)
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
SITCM_VISOR_URL = "https://www.comunidad.madrid/servicios/urbanismo-medio-ambiente/planeamiento-urbanistico-municipios"

DEFAULT_CANTARRANAS_PDFS: list[dict[str, str]] = [
    {
        "path": "/Ficheros/Documentos/01-PROYECTODESCRIPTIVO.pdf",
        "titulo": "IP Molino de Cantarranas — proyecto descriptivo",
        "tipo": "información pública",
    },
    {
        "path": "/Ficheros/Documentos/02-MEMORIAACCESOALAFINCA.pdf",
        "titulo": "IP Molino de Cantarranas — memoria acceso a la finca",
        "tipo": "información pública",
    },
    {
        "path": "/Ficheros/Documentos/03-ESTUDIOIMPACTOAMBIENTAL.pdf",
        "titulo": "IP Molino de Cantarranas — estudio impacto ambiental",
        "tipo": "evaluación ambiental",
    },
    {
        "path": "/Ficheros/Documentos/04-PLANOS-CU-U-01.pdf",
        "titulo": "IP Molino de Cantarranas — planos calificación urbanística U-01",
        "tipo": "información pública",
    },
    {
        "path": "/Ficheros/Documentos/05-PLANOS-CU-A-01.pdf",
        "titulo": "IP Molino de Cantarranas — planos calificación urbanística A-01",
        "tipo": "información pública",
    },
    {
        "path": "/Ficheros/Documentos/05-PLANOS-CU-A-02-A05.pdf",
        "titulo": "IP Molino de Cantarranas — planos A-02 a A-05",
        "tipo": "información pública",
    },
    {
        "path": "/Ficheros/Documentos/05-PLANOS-CU-A-06-A09.pdf",
        "titulo": "IP Molino de Cantarranas — planos A-06 a A-09",
        "tipo": "información pública",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|declaraci[oó]n responsable|"
    r"comunicaci[oó]n previa|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|calificaci[oó]n urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|informaci[oó]n p[uú]blica|"
    r"expediente|reparcel|aprobaci[oó]n|sector|edicto|bocm|molino|cantarranas|"
    r"impacto ambiental|calificaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|funcionario|empleo|oposici[oó]n|convocatoria.*pleno|"
    r"plusval[ií]a|iae\b|calendario fiscal|navidad|carnaval)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(title: str) -> str:
    n = (title or "").lower()
    if "informaci" in n and ("pública" in n or "publica" in n):
        return "información pública"
    if "impacto ambiental" in n:
        return "evaluación ambiental"
    if "calificaci" in n:
        return "calificación urbanística"
    if "planeam" in n or "pgou" in n:
        return "planeamiento"
    return "urbanismo"


def _reid_row(kind: str, rec: dict[str, Any]) -> dict[str, Any]:
    key = "|".join(
        str(rec.get(k) or "")
        for k in ("municipio", "pdf_url", "url", "titulo", "expte", "origen")
    )
    out = dict(rec)
    out["id"] = _stable_id(kind, key)
    return out


class PeralesDeTajunaYTielmesAyuntamientoAdapter(AyuntamientoAdapter):
    """
    Slug compuesto BOCM: portales de Perales de Tajuña (ya en `perales-de-tajuna`) y Tielmes.
    """

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PERALES_WEB)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.user_agent = str(
            self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")
        )
        perales_cfg = dict(self.config.get("perales") or {})
        perales_cfg.setdefault("request_delay_s", self.delay_s)
        perales_cfg.setdefault("user_agent", self.user_agent)
        perales_cfg.setdefault("insecure_ssl", True)
        self._perales = PeralesDeTajunaAyuntamientoAdapter(
            "perales-de-tajuna", perales_cfg, PERALES_WEB
        )
        self._sitcm_cache: dict[str, dict[str, dict[str, Any]]] = {}

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=60) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _abs_tielmes(self, href: str) -> str:
        return urllib.parse.urljoin(f"{TIELMES_WEB}/", unescape(href).replace("&amp;", "&"))

    def _parse_tielmes_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tr in re.findall(r"<tr>\s*(.*?)\s*</tr>", html, re.I | re.S):
            cells: dict[str, str] = {}
            for label, val in re.findall(
                r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
                tr,
                re.I | re.S,
            ):
                cells[label] = _strip_html(val)
            if not cells.get("Documento"):
                continue
            expte = cells.get("Expediente", "")
            key = expte or cells["Documento"]
            if key in seen:
                continue
            seen.add(key)
            preview = re.search(r"preview-document/([a-f0-9-]+)", tr, re.I)
            url = (
                f"{TIELMES_SEDE}/preview-document/{preview.group(1)}"
                if preview
                else f"{TIELMES_SEDE}/board"
            )
            rows.append(
                {
                    "titulo": cells["Documento"][:500],
                    "expediente": expte,
                    "procedimiento": cells.get("Procedimiento", ""),
                    "categoria": cells.get("Categoría", ""),
                    "descripcion": cells.get("Descripción", ""),
                    "fecha": _parse_fecha_dmy(cells.get("Fecha de Publicación", "")),
                    "url": url,
                    "pdf_url": url if preview else None,
                    "origen": "tielmes_tablon",
                    "municipio": "Tielmes",
                }
            )
        return rows

    def _collect_tielmes_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{TIELMES_SEDE}/board")
        except urllib.error.URLError:
            return []
        return self._parse_tielmes_board(html)

    def _collect_tielmes_cantarranas(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.config.get("cantarranas_pdfs") or DEFAULT_CANTARRANAS_PDFS:
            pdf_url = self._abs_tielmes(str(item["path"]))
            rows.append(
                {
                    "titulo": item["titulo"],
                    "fecha": None,
                    "tipo": item.get("tipo") or _proyecto_tipo(item["titulo"]),
                    "url": TIELMES_CANTARRANAS_URL,
                    "pdf_url": pdf_url,
                    "origen": "tielmes_transparencia",
                    "municipio": "Tielmes",
                }
            )
        try:
            html = self._fetch(TIELMES_CANTARRANAS_URL)
            for href in dict.fromkeys(RE_PDF_HREF.findall(html)):
                pdf_url = self._abs_tielmes(href)
                if any(r.get("pdf_url") == pdf_url for r in rows):
                    continue
                rows.append(
                    {
                        "titulo": Path(href).stem.replace("-", " ")[:500],
                        "fecha": None,
                        "tipo": "información pública",
                        "url": TIELMES_CANTARRANAS_URL,
                        "pdf_url": pdf_url,
                        "origen": "tielmes_transparencia",
                        "municipio": "Tielmes",
                    }
                )
        except urllib.error.URLError:
            pass
        return rows

    def _collect_tielmes_licencia_info(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", TIELMES_LICENCIAS_URL),
                "fecha_concesion": None,
                "tipo": "trámites licencias y urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Licencias y urbanismo — requisitos y formularios (web municipal)",
                "url": TIELMES_LICENCIAS_URL,
                "source": "ayuntamiento",
                "municipio": "Tielmes",
                "origen": "tielmes_web",
            },
            {
                "id": _stable_id("lic", f"{TIELMES_SEDE}/board"),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Tielmes",
                "url": f"{TIELMES_SEDE}/board",
                "source": "ayuntamiento",
                "municipio": "Tielmes",
                "origen": "tielmes_sede",
            },
            {
                "id": _stable_id("lic", TIELMES_SEDE),
                "fecha_concesion": None,
                "tipo": "sede electrónica (espublico gestiona)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica Tielmes — presentación de trámites",
                "url": f"{TIELMES_SEDE}/",
                "source": "ayuntamiento",
                "municipio": "Tielmes",
                "origen": "tielmes_sede",
            },
        ]

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and row.get("categoria", "").lower() != "urbanismo":
            return None
        key = row.get("expediente") or row["titulo"]
        return {
            "id": _stable_id("proy", f"Tielmes|{key}"),
            "municipio": "Tielmes",
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion")
        )
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["titulo"]
        return {
            "id": _stable_id("lic", f"Tielmes|{key}"),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "municipio": "Tielmes",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        pdf = row.get("pdf_url")
        return {
            "id": _stable_id("proy", pdf or row["titulo"]),
            "municipio": row.get("municipio") or "Tielmes",
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(row["titulo"]),
            "url": row.get("url") or TIELMES_CANTARRANAS_URL,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": pdf} if pdf else {}),
        }

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _load_sitcm_ambitos(self, wfs_municipio: str) -> dict[str, dict[str, Any]]:
        if wfs_municipio in self._sitcm_cache:
            return self._sitcm_cache[wfs_municipio]
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "120",
                "CQL_FILTER": f"DS_MUNICIPIO='{wfs_municipio}'",
            }
        )
        url = f"{WFS_BASE}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._sitcm_cache[wfs_municipio] = {}
            return self._sitcm_cache[wfs_municipio]
        cache: dict[str, dict[str, Any]] = {}
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if name:
                cache[name.upper()] = feat
        self._sitcm_cache[wfs_municipio] = cache
        return cache

    def _collect_sitcm_proyectos(self, municipio: str, wfs_municipio: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for ambit_name, feat in self._load_sitcm_ambitos(wfs_municipio).items():
            merged = _merge_geometries([feat])
            if not merged:
                continue
            titulo = f"Ámbito planeamiento SITCM — {ambit_name}"
            esc = ambit_name.replace("'", "''")
            cql = f"DS_MUNICIPIO='{wfs_municipio}' AND DS_NOMB_AMB='{esc}'"
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": WFS_TYPE,
                    "outputFormat": "application/json",
                    "srsName": "EPSG:4326",
                    "count": "5",
                    "CQL_FILTER": cql,
                }
            )
            row: dict[str, Any] = {
                "id": _stable_id("proy", f"sitcm-{wfs_municipio}-{ambit_name}"),
                "municipio": municipio,
                "titulo": titulo,
                "fecha": None,
                "tipo": "ámbito planeamiento",
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sitcm_ambito",
                "geom_geojson": merged,
                "geometry_source": "portal_wfs",
                "geometry_source_url": f"{WFS_BASE}?{params}",
                "coord_source": "portal_geometry_centroid",
                "ambito_sit": ambit_name,
            }
            cen = geometry_centroid(merged)
            if cen:
                row["lat"], row["lon"] = cen
            rows.append(row)
        return rows

    def _rows_from_perales(self, kind: str) -> list[dict[str, Any]]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"{kind}.jsonl"
            if kind == "lic":
                self._perales.backfill_licencias(path)
            else:
                self._perales.backfill_proyectos(path)
            rows: list[dict[str, Any]] = []
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rows.append(_reid_row(kind, json.loads(line)))
            return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._rows_from_perales("lic"):
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for rec in self._collect_tielmes_licencia_info():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tielmes_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "perales": sum(1 for r in rows if r.get("municipio") == "Perales de Tajuña"),
            "tielmes": sum(1 for r in rows if r.get("municipio") == "Tielmes"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
        after = result["rows"]
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_sitcm_proyectos("Perales de Tajuña", "PERALES DE TAJUÑA"):
            add(rec)
        for rec in self._rows_from_perales("proy"):
            add(rec)
        for row in self._collect_tielmes_cantarranas():
            add(self._row_to_proyecto(row))
        for item in self._collect_tielmes_board():
            add(self._board_to_proyecto(item))

        for rec in rows:
            if record_geometry(rec):
                continue
            if rec.get("municipio") == "Perales de Tajuña":
                self._perales._enrich_geometry(rec)
            elif rec.get("geom_geojson"):
                cen = geometry_centroid(rec["geom_geojson"])
                if cen:
                    rec.setdefault("lat", cen[0])
                    rec.setdefault("lon", cen[1])

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "perales": sum(1 for r in rows if r.get("municipio") == "Perales de Tajuña"),
            "tielmes": sum(1 for r in rows if r.get("municipio") == "Tielmes"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
