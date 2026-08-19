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
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

SEDE_BASE = "https://castello.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
MUNICIPIO = "Castellón de la Plana"
ID_PREFIX = "castellon-de-la-plana"
INE_CODE = "12040"

GVA_PG_INDEX = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/"
    "3%20CASTELL%D3N/12040%20CASTELL%D3%20DE%20LA%20PLANA/1%20P.%20GENERAL/"
)
GVA_PD_INDEX = (
    "https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/"
    "3%20CASTELL%D3N/12040%20CASTELL%D3%20DE%20LA%20PLANA/2%20P.%20DIFERIDO/"
)
ICV_WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad| de apertura)?|"
    r"notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor)|horari.*recreativ)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|ordenaci[oó]n)|pgou|pgmod|popmod|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|viabilitat)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"cambio de uso|expropiaci[oó]n|glorieta|pep |pe-|pri-|uet-|pp s\.|ed c_|ed manzana)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|padrones|hereus|hereu|borsa de treball|contractaci[oó]n)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://castello\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_GVA_FOLDER = re.compile(r'href="([^"]+)"[^>]*>([^<]+)</a>', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PLAN_CODE = re.compile(r"(12040-\d{4})")
RE_EXPEDIENTE = re.compile(r"\b(20\d{6})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(title: str, procedimiento: str = "") -> str:
    blob = f"{title} {procedimiento}".lower()
    if "pgmod" in blob or "modificaci" in blob:
        return "modificación PGOU"
    if "popmod" in blob:
        return "modificación POP"
    if "plan especial" in blob or re.search(r"\bpe[\s-]", blob):
        return "plan especial"
    if "plan parcial" in blob or re.search(r"\bpp[\s-]", blob):
        return "plan parcial"
    if "plan general" in blob or "pgou" in blob:
        return "PGOU"
    if "ordenaci" in blob and "pormenor" in blob:
        return "plan ordenación pormenorizada"
    if "estudio de detalle" in blob or "estudio detalle" in blob:
        return "estudio de detalle"
    if "informaci" in blob and "p" in blob and "blica" in blob:
        return "información pública"
    if "expropiaci" in blob:
        return "expropiación"
    if "estudio de viabilitat" in blob or "viabilitat" in blob:
        return "estudio de viabilidad"
    if "licencia" in blob:
        return "licencia publicada"
    return "planeamiento"


def _gml_poslist_to_ring(poslist: str) -> list[list[float]]:
    nums = [float(x) for x in re.split(r"\s+", poslist.strip()) if x]
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lng = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    rings: list[list[list[float]]] = []
    for pos in feat.findall(".//{http://www.opengis.net/gml/3.2}posList"):
        if pos.text:
            ring = _gml_poslist_to_ring(pos.text)
            if len(ring) >= 4:
                rings.append(ring)
    if not rings:
        return None
    if len(rings) == 1:
        return {"type": "Polygon", "coordinates": rings}
    return {"type": "MultiPolygon", "coordinates": [[ring] for ring in rings]}


class CastellonDeLaPlanaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico gestiona + registro planeamiento GVA + ICV WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.gva_indexes: list[str] = [
            str(u)
            for u in (
                self.config.get("gva_indexes")
                or [GVA_PG_INDEX, GVA_PD_INDEX]
            )
        ]
        self.icv_wfs_base = str(self.config.get("icv_wfs_base") or ICV_WFS_BASE).rstrip("/")
        self.ine_code = str(self.config.get("ine_code") or INE_CODE)
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

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-castellon-de-la-plana/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-castellon-de-la-plana/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

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
                cls = cm.group(1)
                cells[cls] = _strip_html(cm.group(2))

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

    def _collect_gva_planeamiento(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for index_url in self.gva_indexes:
            try:
                html = self._fetch(index_url)
            except urllib.error.URLError:
                continue
            base = index_url if index_url.endswith("/") else f"{index_url}/"
            for href, title in RE_GVA_FOLDER.findall(html):
                title = _strip_html(title)
                if not title or title.lower() == "name":
                    continue
                if not href.endswith("/"):
                    continue
                if "12040-" not in href and "12040-" not in title:
                    continue
                folder_url = urllib.parse.urljoin(base, href)
                if folder_url in seen:
                    continue
                seen.add(folder_url)
                code_m = RE_PLAN_CODE.search(title) or RE_PLAN_CODE.search(href)
                exp_m = RE_EXPEDIENTE.search(title)
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _fecha_from_blob(title),
                        "url": folder_url,
                        "plan_code": code_m.group(1) if code_m else None,
                        "expediente": exp_m.group(1) if exp_m else None,
                        "procedimiento": "registro planeamiento GVA",
                        "blob": title,
                        "origen": "gva_planeamiento",
                    }
                )
        return rows

    def _icv_wfs_page_url(self, start_index: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "Planeamiento.Zonificacion",
                "outputFormat": "application/gml+xml; version=3.2",
                "count": "100",
                "startIndex": str(start_index),
                "srsName": "EPSG:4326",
            }
        )
        return f"{self.icv_wfs_base}?{params}"

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for start in range(0, 5000, 100):
            url = self._icv_wfs_page_url(start)
            try:
                raw = self._fetch_bytes(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break

            members = root.findall(".//{http://www.opengis.net/wfs/2.0}member")
            if not members:
                break

            for mem in members:
                feat = mem[0]
                props: dict[str, str] = {}
                for child in feat:
                    tag = child.tag.split("}")[-1]
                    if tag == "msGeometry":
                        continue
                    txt = "".join(child.itertext()).strip()
                    if txt:
                        props[tag] = txt
                if props.get("cod_ine_mun") != self.ine_code:
                    continue

                key = "|".join(
                    [
                        props.get("expediente", ""),
                        props.get("denominaci", ""),
                        props.get("zon_suelo", ""),
                        props.get("clas_suelo", ""),
                    ]
                )
                if key in seen:
                    continue
                seen.add(key)

                geom = _gml_feature_to_geojson(feat)
                titulo = props.get("denominaci") or props.get("denominaci_val") or "Zonificación"
                zona = props.get("zon_suelo") or ""
                if zona:
                    titulo = f"{titulo} — {zona}"
                doc_url = props.get("url_abs") or url
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"icv:{key}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(props.get("expediente", "")),
                    "tipo": _proyecto_tipo(titulo),
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "origen": "icv_wfs",
                    "expediente": props.get("expediente") or None,
                    "zon_suelo": zona or None,
                    "clas_suelo": props.get("clas_suelo") or None,
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)

            if len(members) < 100:
                break

        self._wfs_cache = rows
        return rows

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(
            str(rec.get(k) or "")
            for k in ("titulo", "expediente", "plan_code", "tipo", "procedimiento")
        ).lower()
        for wfs_rec in self._collect_icv_wfs():
            wfs_blob = " ".join(
                str(wfs_rec.get(k) or "")
                for k in ("titulo", "expediente", "zon_suelo", "clas_suelo")
            ).lower()
            exp = str(rec.get("expediente") or "")
            wfs_exp = str(wfs_rec.get("expediente") or "")
            if exp and wfs_exp and exp in wfs_exp:
                self._copy_geometry(rec, wfs_rec)
                return
            if "plan general" in blob and "plan general" in wfs_blob:
                self._copy_geometry(rec, wfs_rec)
                return
            title = str(rec.get("titulo") or "").lower()
            for token in re.split(r"[\s,/()-]+", title):
                if len(token) >= 6 and token in wfs_blob:
                    self._copy_geometry(rec, wfs_rec)
                    return

    def _copy_geometry(self, rec: dict[str, Any], src: dict[str, Any]) -> None:
        for key in (
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if src.get(key) is not None:
                rec[key] = src[key]

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias y actividad",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón d'anuncis — licencias d'obra i activitat",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Edictes i anuncis publicats a la seu electrònica espublico",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catàleg de tràmits — seu electrònica",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias y comunicaciones previas vía sede (sin listado histórico público)",
                "origen": "sede_tramite",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/expedientes"),
                "fecha_concesion": None,
                "tipo": "consulta expedientes (autenticación)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Consulta d'expedients urbanístics (sede)",
                "url": f"{self.sede_base}/expedientes",
                "source": "ayuntamiento",
                "nota": "Requiere identificación; no hay listado público de expedientes",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "genéric", "generic")):
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
        if "actividad" in proc or "recreativ" in blob.lower():
            tipo = "licencia de actividad"
        elif re.search(r"(?i)obra", blob):
            tipo = "licencia de obra"
        key = row.get("expediente") or row["url"]
        return {
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
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "genéric" not in proc and "generic" not in proc:
            return None
        key = row.get("expediente") or row["url"]
        rec = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "tablon",
        }
        self._enrich_geometry(rec)
        return rec

    def _gva_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        title = row["titulo"]
        key = row.get("url") or title
        rec = {
            "id": _stable_id("proy", f"gva:{key}"),
            "municipio": MUNICIPIO,
            "titulo": title,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(title, row.get("procedimiento") or ""),
            "url": row["url"],
            "source": "ayuntamiento",
            "expediente": row.get("expediente"),
            "plan_code": row.get("plan_code"),
            "origen": row.get("origen") or "gva_planeamiento",
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
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
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

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_gva_planeamiento():
            add(self._gva_to_proyecto(item))
        for item in self._collect_icv_wfs():
            add(item)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "gva": sum(1 for r in rows if r.get("origen") == "gva_planeamiento"),
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
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
