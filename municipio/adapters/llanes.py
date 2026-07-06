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
from urllib.parse import unquote, urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

BASE = "https://www.ayuntamientodellanes.com"
SEDE_BASE = "https://llanes.sede.e-ayuntamiento.es"
RPGUR_BASE = "https://www54.asturias.es/rpgur"
WFS_AMBITO = (
    "http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows"
)
MUNICIPIO = "Llanes"
ID_PREFIX = "llanes"
LLANES_RPGUR_CONCEJO_ID = "36"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/es/urbanismo",
    f"{BASE}/es/urbanismo-y-patrimonio",
    f"{BASE}/es/aprobacion-pgou-y-catalogo",
    f"{BASE}/es/plan-especial-de-uso-turistico",
    f"{BASE}/es/documentos-en-informaci%C3%B3n-p%C3%BAblica1",
    f"{BASE}/es/documentos-sometidos-a-informacion-publica",
    f"{BASE}/es/normativa-urbanistica",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{BASE}/es/urbanismo",
    f"{SEDE_BASE}/action/tramites?method=enter",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|instrucci[oó]n.*licencia|tr[aá]mite.*obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|proyecto|"
    r"modificaci[oó]n|reparcel|cat[aá]logo|normas (?:subsidiarias|urban)|peredi|"
    r"memoria|planos|estudio (?:ac[uú]stico|ambiental)|aprobaci[oó]n)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_DOC_HREF = re.compile(r'href="(/documents/[^"]+\.pdf[^"]*)"', re.I)
RE_DROPBOX = re.compile(r'href="(https://www\.dropbox\.com[^"]+)"', re.I)
RE_RPGUR_ROW = re.compile(
    r'<tr class="(?:odd|even)">(.*?)</tr>',
    re.S | re.I,
)
RE_RPGUR_ID = re.compile(r"idInstrumento=(\d+)")
RE_RPGUR_DATE_LABEL = re.compile(
    r"(?:Aprobaci[oó]n [Ii]nicial|publicaci[oó]n BOPA|acuerdo)[^:]*:\s*(\d{1,2}/\d{1,2}/\d{4})",
    re.I,
)


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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _clean_title(raw: str) -> str:
    t = unescape(re.sub(r"\s+", " ", raw or "")).strip()
    t = re.sub(r"\.pdf$", "", t, flags=re.I)
    t = re.sub(r"\+", " ", t)
    return t[:500] if t else raw[:500]


def _title_from_doc_url(url: str) -> str:
    path = unquote(url.split("?")[0])
    parts = [p for p in path.split("/") if p]
    for part in reversed(parts):
        if part.lower().endswith(".pdf"):
            return _clean_title(part[:-4])
    return _clean_title(Path(path).name) or url


def _abs_portal(href: str) -> str:
    if href.startswith("http"):
        return unescape(href.split("&amp;")[0])
    return urljoin(f"{BASE}/", unescape(href))


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "catálogo" in n or "catalogo" in n:
        return "catálogo urbanístico"
    if "plan especial" in n or "peut" in n or "uso turístico" in n:
        return "plan especial"
    if "peredi" in n:
        return "plan especial implantación"
    if "normas subsidiarias" in n or "nspm" in n:
        return "normas subsidiarias"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "revisi" in n:
        return "revisión planeamiento"
    return "planeamiento"


class LlanesAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay municipal web + RPGUR (registro urbanístico Asturias) + WFS ámbitos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.user_agent = str(self.config.get("user_agent", "poc-bocm-llanes/1.0"))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self._geometry_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, headers: dict[str, str] | None = None) -> str:
        time.sleep(self.delay_s)
        hdrs = {"User-Agent": self.user_agent}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data, headers=hdrs)
        with urllib.request.urlopen(req, timeout=90) as resp:
            raw = resp.read()
        for enc in ("utf-8", "latin-1"):
            try:
                return raw.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _load_geometry_by_rpgur_id(self) -> dict[str, dict[str, Any]]:
        if self._geometry_cache is not None:
            return self._geometry_cache
        out: dict[str, dict[str, Any]] = {}
        cql = urllib.parse.quote("Instrumento LIKE '%LLANES%'")
        url = (
            f"{WFS_AMBITO}?service=WFS&version=1.0.0&request=GetFeature"
            f"&typeName=E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS"
            f"&CQL_FILTER={cql}&outputFormat=application/json&srsName=EPSG:4326"
        )
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._geometry_cache = out
            return out
        for feat in data.get("features") or []:
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties") or {}
            inv_id = props.get("Id._Inventario_Registro_Urbanístico")
            geom = feat.get("geometry")
            if inv_id is None or not isinstance(geom, dict):
                continue
            key = str(int(inv_id)) if str(inv_id).isdigit() else str(inv_id)
            out[key] = {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": url,
                "coord_source": "portal_geometry_centroid",
                "instrumento": props.get("Denominación_Instrumento") or props.get("Instrumento"),
            }
        self._geometry_cache = out
        return out

    def _attach_geometry(self, rec: dict[str, Any], rpgur_id: str | None = None) -> None:
        if record_geometry(rec):
            return
        if not rpgur_id:
            return
        geom_row = self._load_geometry_by_rpgur_id().get(str(rpgur_id))
        if not geom_row:
            return
        rec.update(geom_row)
        cen = geometry_centroid(geom_row["geom_geojson"])
        if cen:
            rec["lat"], rec["lon"] = cen

    def _collect_rpgur_instruments(self) -> list[dict[str, Any]]:
        post_data = urllib.parse.urlencode(
            {
                "primeraVez": "true",
                "accesoConcejo": "",
                "nombreConcejo": "",
                "ambito": "MUN",
                "idConcejo": LLANES_RPGUR_CONCEJO_ID,
                "tipoInstrumento": "",
                "estadoInstrumento": "",
                "denominacion": "",
            }
        ).encode("utf-8")
        url = f"{RPGUR_BASE}/action/publico/busquedaConsulta?method=listPublico"
        try:
            html = self._fetch(
                url,
                data=post_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for block in RE_RPGUR_ROW.findall(html):
            iid_m = RE_RPGUR_ID.search(block)
            if not iid_m:
                continue
            iid = iid_m.group(1)
            cells = [
                re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip()
                for c in re.findall(r"<td[^>]*>(.*?)</td>", block, re.S | re.I)
            ]
            cells = [c for c in cells if c and c.lower() != "acceder"]
            if len(cells) < 4:
                continue
            titulo = _clean_title(cells[3] if len(cells) > 3 else cells[-1])
            estado = cells[-1] if len(cells) > 4 else ""
            codigo = ""
            for cell in cells:
                if re.fullmatch(r"C-\d+/\d+", cell.strip()):
                    codigo = cell.strip()
                    break
            detail_url = f"{RPGUR_BASE}/action/publico/gestionConsulta?method=retrieve&idInstrumento={iid}"
            fecha = None
            try:
                detail_html = self._fetch(detail_url)
                fecha = _parse_fecha_dmy(detail_html) or _parse_fecha_iso(detail_html)
                if not fecha:
                    dm = RE_RPGUR_DATE_LABEL.search(detail_html)
                    if dm:
                        fecha = _parse_fecha_dmy(dm.group(0))
            except urllib.error.URLError:
                pass
            blob = f"{titulo} {codigo} {estado}"
            rec = {
                "id": _stable_id("proy", f"rpgur:{iid}"),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": fecha,
                "tipo": _proyecto_tipo(blob),
                "url": detail_url,
                "source": "ayuntamiento",
                "estado": estado,
                "codigo_expediente": codigo or None,
                "rpgur_id": iid,
            }
            self._attach_geometry(rec, iid)
            rows.append(rec)
        return rows

    def _collect_portal_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(titulo: str, url: str, fecha: str | None = None, tipo: str | None = None) -> None:
            titulo = _clean_title(titulo)
            key = url.split("?")[0]
            if not titulo or key in seen:
                return
            if not RE_PROYECTO.search(titulo) and not RE_PROYECTO.search(url):
                return
            seen.add(key)
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": fecha,
                    "tipo": tipo or _proyecto_tipo(titulo),
                    "url": url,
                    "source": "ayuntamiento",
                }
            )

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            tm = re.search(r"<title>([^<]+)", html, re.I)
            if tm:
                page_title = _clean_title(tm.group(1).split("-")[0])

            for href in RE_DOC_HREF.findall(html):
                doc_url = _abs_portal(href)
                title = _title_from_doc_url(doc_url)
                fecha = _parse_fecha_dmy(doc_url) or _parse_fecha_iso(doc_url)
                add(title or page_title, doc_url, fecha)

            for href in RE_DROPBOX.findall(html):
                box_url = unescape(href.split("&amp;")[0])
                label = "Documentación Dropbox"
                low = box_url.lower()
                if "bej85" in low or "peredi" in page_url.lower():
                    label = "Plan Especial PEREDI LAB (Dropbox)"
                elif "7xizxkvc" in low or "gmw7yvaw" in low:
                    label = "Expediente PGOU y Catálogo (Dropbox)"
                elif "7n4ikspj" in low:
                    label = "Documentación urbanística (Dropbox)"
                add(label, box_url)

            if page_title and RE_PROYECTO.search(page_title):
                add(page_title, page_url)

        return rows

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.licencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for href, text in re.findall(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{3,120})</a>', html, re.I):
                blob = f"{text} {href}"
                if not RE_LICENCIA.search(blob):
                    continue
                url = _abs_portal(href) if not href.startswith("http") else href.split("&amp;")[0]
                rec_id = _stable_id("lic", url)
                if rec_id in seen:
                    continue
                seen.add(rec_id)
                rows.append(
                    {
                        "id": rec_id,
                        "fecha_concesion": None,
                        "tipo": "trámite licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": _clean_title(text),
                        "url": url,
                        "source": "ayuntamiento",
                        "nota": "Ficha procedimental; sede con fallo TLS — sin listado de concesiones",
                    }
                )
        if not rows:
            url = f"{SEDE_BASE}/action/tramites?method=enter"
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": "Trámites de licencias urbanísticas (sede electrónica)",
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Sede llanes.sede.e-ayuntamiento.es con error TLS; sin dataset público de concesiones",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return {"rows": len(rows), "path": str(path)}

    def _merge_proyectos(self, *sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        for source in sources:
            for row in source:
                key = (row.get("titulo") or "").lower()[:80]
                url_key = (row.get("url") or "").split("?")[0]
                dedupe = f"{key}|{url_key}"
                if dedupe in seen:
                    continue
                seen.add(dedupe)
                merged.append(row)
        return merged

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_tramites()
        return self._write_jsonl(out_jsonl, rows)

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_licencias(out_jsonl)

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._merge_proyectos(
            self._collect_rpgur_instruments(),
            self._collect_portal_pages(),
        )
        return self._write_jsonl(out_jsonl, rows)

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        return self.backfill_proyectos(out_jsonl)
