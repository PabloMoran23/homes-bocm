from __future__ import annotations

import hashlib
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
from municipio.gis.sitcm import WFS_BASE, _merge_geometries, resolve_ambito_geometry

WP_BASE = "https://www.valdepielagos.es"
SEDE_BASE = "https://valdepielagos.sedelectronica.es"
MUNICIPIO = "Valdepiélagos"
ID_PREFIX = "valdepielagos"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "VALDEPIÉLAGOS"

PLANEAMIENTO_URL = f"{WP_BASE}/planeamiento/"
TECNICO_URL = f"{WP_BASE}/tecnico-municipal/"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|ocupaci[oó]n.*v[ií]a p[uú]blica|acto comunicado)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|aprobaci[oó]n|"
    r"reparcel|sector|sau[\s\-]*\d|subsanaci[oó]n|clasificaci[oó]n del suelo|"
    r"planos?\s+ordenaci[oó]n|memoria|cat[aá]logo|acuerdo|anexo|impacto ambiental)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|presupuest|empleo|jurado|fiestas|calendario fiscal|"
    r"jabal[ií]|selecci[oó]n de personal|vacaciones|protocolo)",
)
RE_SAU = re.compile(r"(?i)\bSAU[\s\-]*(\d+)\b")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_ICONLIST_LINK = re.compile(
    r'av_iconlist_title[^>]*>\s*<a href=["\']([^"\']+)["\'][^>]*title=["\']([^"\']*)["\']',
    re.I,
)
RE_TOGGLE_SECTION = re.compile(
    r"<h5[^>]*>([^<]+)<span class=\"toggle_icon\">.*?<a href=\"([^\"]+\.pdf[^\"]*)\"",
    re.I | re.S,
)
RE_BOARD_CELL = re.compile(
    r'data-label="([^"]+)"[^>]*>\s*(?:<span>)?(.*?)(?:</span>)?\s*</td>',
    re.I | re.S,
)
RE_BOARD_ROW = re.compile(r"<tr>\s*(.*?)\s*</tr>", re.I | re.S)
RE_H4 = re.compile(r"<h4[^>]*>([^<]+)</h4>", re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


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
    m = re.search(r"/(\d{4})/(\d{2})/", url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return _parse_fecha_dmy(Path(url).name)


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if re.search(r"\bsau[\s\-]*\d", n):
        return "subsanación SAU"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    if "clasificaci" in n and "suelo" in n:
        return "clasificación del suelo"
    if "planos" in n and "ordenaci" in n:
        return "planos de ordenación"
    if "memoria" in n:
        return "memoria planeamiento"
    if "impacto ambiental" in n:
        return "evaluación ambiental"
    if "acuerdo" in n:
        return "acuerdo planeamiento"
    return "planeamiento"


def _licencia_tipo(title: str) -> str:
    n = title.lower()
    if "ocupaci" in n and "v[ií]a" in n:
        return "ocupación vía pública"
    if "acto comunicado" in n:
        return "acto comunicado"
    if "declaraci" in n and "actividad" in n:
        return "declaración responsable de actividad"
    if "declaraci" in n:
        return "declaración responsable urbanística"
    if "licencia" in n:
        return "solicitud licencia urbanística"
    return "trámite urbanístico"


class ValdepielagosAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Enfold + sede espublico gestiona + ámbitos SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.planeamiento_url = str(self.config.get("planeamiento_url") or PLANEAMIENTO_URL)
        self.tecnico_url = str(self.config.get("tecnico_url") or TECNICO_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_feats: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-valdepielagos/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60, context=self._ssl_ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _parse_planeamiento(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        sections = [(m.start(), unescape(m.group(1).strip())) for m in RE_H4.finditer(html)]
        section_for = lambda pos: next(
            (title for start, title in reversed(sections) if start <= pos),
            "Planeamiento",
        )

        for m in RE_ICONLIST_LINK.finditer(html):
            href, label = m.group(1), unescape(m.group(2).strip())
            pdf_url = self._abs_wp(href)
            section = section_for(m.start())
            titulo = f"{section} — {label}" if label and label.lower() not in section.lower() else section
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_url(pdf_url) or _parse_fecha_dmy(section),
                    "url": self.planeamiento_url,
                    "pdf_url": pdf_url,
                    "origen": "wp_planeamiento",
                    "seccion": section,
                }
            )
        return rows

    def _parse_tecnico_impresos(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TOGGLE_SECTION.finditer(html):
            titulo = _strip_html(m.group(1))
            pdf_url = self._abs_wp(m.group(2))
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_url(pdf_url),
                    "url": self.tecnico_url,
                    "pdf_url": pdf_url,
                    "origen": "wp_impresos",
                }
            )
        return rows

    def _parse_board(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.I | re.S)
        if not tbody_m:
            return rows
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
                    "origen": "sede_board",
                }
            )
        return rows

    def _load_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_feats is not None:
            return self._wfs_feats
        muni = self.wfs_municipio.replace("'", "''")
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "50",
                "CQL_FILTER": f"DS_MUNICIPIO='{muni}'",
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_feats = []
            return self._wfs_feats
        self._wfs_feats = [f for f in (data.get("features") or []) if isinstance(f, dict)]
        return self._wfs_feats

    def _match_sau_ambit(self, title: str) -> str | None:
        m = RE_SAU.search(title or "")
        if not m:
            return None
        sau_num = m.group(1)
        for feat in self._load_wfs_ambitos():
            name = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "")
            if re.search(rf"\bSAU[\s\-]*{sau_num}\b", name, re.I):
                return name
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        title = str(rec.get("titulo") or "")
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, title)
        if not geom:
            ambit = self._match_sau_ambit(title)
            if ambit:
                chosen = [
                    f
                    for f in self._load_wfs_ambitos()
                    if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "") == ambit
                ]
                geom = _merge_geometries(chosen)
                meta = {"ambito_name": ambit}
        if not geom:
            return
        esc = str(meta.get("ambito_name") or "").replace("'", "''")
        cql = f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}'"
        if esc:
            cql += f" AND DS_NOMB_AMB='{esc}'"
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = (
            f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
        )
        rec["coord_source"] = "portal_geometry_centroid"
        if meta.get("ambito_name"):
            rec["ambito_sit"] = meta["ambito_name"]
        cen = geometry_centroid(geom)
        if cen:
            rec.setdefault("lat", cen[0])
            rec.setdefault("lon", cen[1])

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feat in self._load_wfs_ambitos():
            props = feat.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([feat])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": self.planeamiento_url,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                esc = name.replace("'", "''")
                cql = (
                    f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39)*2)}' "
                    f"AND DS_NOMB_AMB='{esc}'"
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

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
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
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo sede",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "Licencias y declaraciones responsables vía sede",
                "origen": "sede_tramite",
            },
        ]
        try:
            html = self._fetch(self.tecnico_url)
        except urllib.error.URLError:
            return rows
        for item in self._parse_tecnico_impresos(html):
            rows.append(
                {
                    "id": _stable_id("lic", item["pdf_url"]),
                    "fecha_concesion": item.get("fecha"),
                    "tipo": _licencia_tipo(item["titulo"]),
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "pdf_url": item["pdf_url"],
                    "source": "ayuntamiento",
                    "nota": "Formulario/trámite informativo; no concesión publicada",
                    "origen": item.get("origen"),
                }
            )
        return rows

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "seccion"))
        if RE_EXCLUDE.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("expediente") or row["url"] + "|" + row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria"))
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row.get("pdf_url") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or _licencia_tipo(row["titulo"]),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
            **({"expte": row["expediente"]} if row.get("expediente") else {}),
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
        for rec in self._collect_licencia_info():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        try:
            board = self._parse_board(self._fetch(self.board_url))
        except urllib.error.URLError:
            board = []
        for item in board:
            rec = self._to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        try:
            html = self._fetch(self.planeamiento_url)
            for item in self._parse_planeamiento(html):
                add(self._to_proyecto(item))
        except urllib.error.URLError:
            pass
        try:
            board = self._parse_board(self._fetch(self.board_url))
            for item in board:
                add(self._to_proyecto(item))
        except urllib.error.URLError:
            pass
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
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
