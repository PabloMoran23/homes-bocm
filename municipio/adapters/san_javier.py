from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.sanjavier.es"
SEDE_BASE = "https://sanjavier.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
PLANTEAMIENTO_URL = f"{WEB_BASE}/es/ayuntamiento-planteamiento-urbanistico"
URBANISMO_URL = f"{WEB_BASE}/es/seccion-49-urbanismo-administrativo"
MUNICIPIO = "San Javier"
ID_PREFIX = "san-javier"
COD_INE = "30070"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27San%20Javier%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

DEFAULT_SEED_PAGES: tuple[str, ...] = (
    PLANTEAMIENTO_URL,
    URBANISMO_URL,
    f"{WEB_BASE}/es/pagina-1902-documentalencanizadas",
    f"{WEB_BASE}/es/pagina-1907-plan-edil",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban|ejecuci[oó]n de obras)|inicio de obra|"
    r"obra (?:mayor|menor)|concesi[oó]n demanial|ocupaci[oó]n de v[ií]a p[uú]blica)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgmo|normas subsidiarias|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|borm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|pol[ií]gono|"
    r"cambio de uso|ordenanza|normativa urban|evaluaci[oó]n ambiental|"
    r"delimitaci[oó]n|urbanizaci[oó]n|rotunda|la manga|santiago de la ribera|"
    r"encanizadas|plan edil|actuaciones urban)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"oferta empleo p[uú]blico|junta de gobierno local|proceso selectivo|"
    r"acta n[ºo°]|lista provisional|arquitecto t[eé]cnico|administrativo|"
    r"herencia|inventario notarial|demarcaci[oó]n de costas(?!.*urban))",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://sanjavier\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_LINK = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AMBITO = re.compile(
    r"(?i)\b(UA-?\s*\d+|SECTOR\s+[\w-]+|Pol[ií]gono\s+[A-Z0-9][\w.\s-]{2,40}|"
    r"La Manga|Santiago de la Ribera|Encanizadas|Roda)\b",
)
RE_PLANT_ITEM = re.compile(
    r'<li class="lieado col-md-12 Parte_Superior_CListado".*?</li>\s*'
    r'<li class="col-md-12 lieado-fino Parte_Inferior_CListado".*?</li>',
    re.I | re.S,
)
RE_DESCARGAR = re.compile(r'href="(https://www\.sanjavier\.es/es/descargar-fichero-[^"]+)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", t).upper().strip()


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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_ambito(raw: str) -> str:
    code = unescape(raw or "").strip()
    code = re.sub(r"\s+", " ", code)
    return code


def _ambito_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_AMBITO.finditer(text or ""):
        code = _normalize_ambito(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "plan parcial" in b or "rotunda" in b:
        return "plan parcial"
    if "modificaci" in b and ("nn.ss" in b or "normas" in b or "pgmo" in b):
        return "modificación planeamiento"
    if "pgmo" in b or "plan general" in b:
        return "PGMO"
    if "normas subsidiarias" in b or "nn.ss" in b:
        return "normas subsidiarias"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "concesi" in b and "demanial" in b:
        return "concesión demanial"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class SanJavierAyuntamientoAdapter(AyuntamientoAdapter):
    """Web Yii + sede espublico gestiona (tablón) + WFS SITMURCIA (geometría parcial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self._wfs_index: dict[str, dict[str, Any]] | None = None
        self._wfs_norm_index: list[tuple[str, dict[str, Any]]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-san-javier/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_url(self, href: str, page_url: str = WEB_BASE) -> str:
        return urljoin(page_url, href)

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

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        norm_rows: list[tuple[str, dict[str, Any]]] = []
        try:
            data = json.loads(self._fetch(self.wfs_url))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = index
            self._wfs_norm_index = norm_rows
            return index
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            ambito = _normalize_ambito(str(props.get("Ambito") or ""))
            geom = feat.get("geometry")
            if not ambito or not isinstance(geom, dict):
                continue
            rec = {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": ambito,
                "clasificacion": props.get("Clasificacion"),
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            index[ambito] = rec
            norm_rows.append((_norm_text(ambito), rec))
        norm_rows.sort(key=lambda x: len(x[0]), reverse=True)
        self._wfs_index = index
        self._wfs_norm_index = norm_rows
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "blob", "expte"))
        index = self._build_wfs_index()
        for code in _ambito_codes_from_text(blob):
            hit = index.get(code)
            if not hit:
                for key, row in index.items():
                    if _norm_text(code) in _norm_text(key) or _norm_text(key) in _norm_text(code):
                        hit = row
                        break
            if hit:
                self._merge_geom(rec, hit)
                return
        title_norm = _norm_text(blob)
        for ambito_norm, hit in self._wfs_norm_index or []:
            if len(ambito_norm) < 8:
                continue
            if ambito_norm in title_norm:
                self._merge_geom(rec, hit)
                return

    def _merge_geom(self, rec: dict[str, Any], hit: dict[str, Any]) -> None:
        for key in (
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
            "ambito",
            "clasificacion",
        ):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            if not documento or documento in ("Documento",):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                }
            )
        return rows

    def _collect_planteamiento(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(PLANTEAMIENTO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for block in RE_PLANT_ITEM.finditer(html):
            chunk = block.group(0)
            titulo_m = re.search(r"Titulo:\s*</strong>\s*</span>\s*([^<]+)", chunk, re.I | re.S)
            titulo = _strip_html(titulo_m.group(1)) if titulo_m else ""
            if not titulo:
                continue
            fecha_ini = None
            fi_m = re.search(
                r"Fecha Inicio\s*:\s*</strong>\s*</span>\s*([^<]+)",
                chunk,
                re.I | re.S,
            )
            if fi_m:
                fecha_ini = _parse_fecha_dmy(_strip_html(fi_m.group(1)))
            pdf_m = RE_DESCARGAR.search(chunk)
            url = pdf_m.group(1) if pdf_m else PLANTEAMIENTO_URL
            blob = f"{titulo} {_strip_html(chunk)}"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha_ini,
                    "url": url,
                    "blob": blob,
                    "origen": "web_planteamiento",
                }
            )
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            page_title = _strip_html(re.search(r"<title>([^<]+)", html, re.I).group(1)) if re.search(r"<title>", html) else seed
            for m in RE_DESCARGAR.finditer(html):
                url = m.group(1)
                if url in seen:
                    continue
                seen.add(url)
                ctx_start = max(0, m.start() - 400)
                ctx = _strip_html(html[ctx_start : m.start() + 200])
                titulo = ctx[-180:] if ctx else page_title
                blob = f"{titulo} {ctx}"
                if not RE_PROYECTO.search(blob) and "planeam" not in blob.lower():
                    continue
                rows.append(
                    {
                        "titulo": (titulo or page_title)[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": url,
                        "blob": blob,
                        "origen": "web_pdf",
                    }
                )
            for href, title in RE_LINK.findall(html):
                if "urbmurcia" not in href.lower() and "borm.es" not in href.lower():
                    continue
                titulo = _strip_html(title) or href
                url = self._abs_url(href, seed)
                if url in seen:
                    continue
                blob = f"{titulo} {url}"
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _fecha_from_blob(blob),
                        "url": url,
                        "blob": blob,
                        "origen": "web_enlace",
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
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
                "nota": "Edictos urbanísticos en espublico gestiona (/board)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", URBANISMO_URL),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo administrativo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo administrativo — modelos licencia y comunicación previa",
                "url": URBANISMO_URL,
                "source": "ayuntamiento",
                "nota": "Declaraciones responsables y comunicaciones previas (PDF/web)",
                "origen": "web_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        cat = (row.get("categoria") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        if "urban" in cat:
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "actividad" in proc:
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra|demanial", blob):
            tipo = "licencia / autorización obra"
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon",
            "blob": blob,
        }
        self._attach_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "urban" not in proc:
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
            "origen": "tablon",
            "blob": blob,
        }
        self._attach_geometry(rec)
        return rec

    def _raw_to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", raw["url"]),
            "municipio": MUNICIPIO,
            "titulo": raw["titulo"],
            "fecha": raw.get("fecha") or _fecha_from_blob(blob),
            "tipo": _proyecto_tipo(blob),
            "url": raw["url"],
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
            "blob": blob,
        }
        self._attach_geometry(rec)
        return rec

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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "web_tramite")),
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
        for source in (
            self._collect_board(),
            self._collect_planteamiento(),
            self._collect_seed_pdfs(),
        ):
            for item in source:
                rec = self._board_to_proyecto(item) if "documento" in item else self._raw_to_proyecto(item)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok" if rows else "partial",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for source in (
            self._collect_board(),
            self._collect_planteamiento(),
            self._collect_seed_pdfs(),
        ):
            for item in source:
                rec = self._board_to_proyecto(item) if "documento" in item else self._raw_to_proyecto(item)
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
