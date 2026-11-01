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
from urllib.parse import urljoin

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.sanpedrodelpinatar.es"
SEDE_BASE = "https://sede.sanpedrodelpinatar.es"
MUNICIPIO = "San Pedro del Pinatar"
ID_PREFIX = "san-pedro-del-pinatar"
COD_INE = "30075"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
URBANISMO_KEYWORD = "PTS_PC_012"

WFS_URL = (
    "https://mapas-gis-inter.carm.es/geoserver/SIT_USU_PLA_URB_CARM/wfs"
    "?service=WFS&version=2.0.0&request=GetFeature"
    "&typeNames=SIT_USU_PLA_URB_CARM:plu_ze_37_mun_uso_suelo"
    "&CQL_FILTER=Municipio%3D%27San%20Pedro%20del%20Pinatar%27"
    "&count=1000&outputFormat=application/json&srsName=EPSG:4326"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/concejalias/urbanismo/",
    f"{WEB_BASE}/concejalias/urbanismo-2/plan-general-de-ordenacion-urbana/",
    f"{WEB_BASE}/category/urbanismo/",
    "https://ayto.sanpedrodelpinatar.es/avance-pgmo/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|segunda y sucesiva ocupaci[oó]n|ocupaci[oó]n de v[ií]a|"
    r"paneles solares|invernaderos|anexo t[eé]cnico)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|loturm|"
    r"informaci[oó]n p[uú]blica|expediente|expte|proyecto|modificaci[oó]n|"
    r"estudio de detalle|reparcel|sector|unp-|up-|u\.p\.|borm|aprobaci[oó]n|"
    r"villa alegr[ií]a|los lorcas|adaptaci[oó]n del pp|fachada mar[ií]tima|"
    r"artero guirao|romer[ií]a|campoamor|snu|suss|ordenaci[oó]n urbana)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(oferta de empleo|proceso selectivo|subvenci[oó]n|padr[oó]n|iae\b|"
    r"cobranza|presupuesto general|bolsa de trabajo|fiestas|concurso de dibujo|"
    r"barracas populares|cesta solidaria|vertidos alcantarillado)",
)
RE_LINK = re.compile(r'href=["\']([^"\']+)["\']', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_AMBITO_TOKEN = re.compile(
    r"(?i)\b("
    r"UNP[-\s]?[0-9]+R[0-9A-Z]*|"
    r"UP[-\s]?[0-9]+[A-Z0-9]*|"
    r"U\.P\.[\s]*[0-9]+R[-_\s]?[A-Z0-9-]*|"
    r"SGEL\.?\s*Adscrito\s+UP[-\s_]?[0-9]+[A-Z0-9]*|"
    r"SGC\.?\s*Adscrito\s+UP[-\s_]?[0-9]+[A-Z0-9]*"
    r")\b",
)
RE_NAMED_SECTOR = re.compile(
    r"(?i)(villa alegr[ií]a|los lorcas|las beatas|los cuarteros|el moj[oó]n|"
    r"puerto pinatar|las charcas|los saez)",
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


def _xml_date(obj: dict[str, Any] | None) -> str | None:
    if not obj or not isinstance(obj, dict):
        return None
    try:
        return datetime(
            int(obj["year"]),
            int(obj["month"]),
            int(obj["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _normalize_ambito(raw: str) -> str:
    code = unescape(raw or "").strip().upper()
    code = re.sub(r"U\.P\.\s*(\d+)R\s*-\s*([A-Z0-9]+)", r"UP-\1R\2", code, flags=re.I)
    code = code.replace("_", "-").replace("U.P.", "UP-").replace(" ", "")
    code = re.sub(r"UP-(\d+)R([A-Z])", r"UP-\1R\2", code)
    code = re.sub(r"UNP-(\d+)R(\d+)", r"UNP-\1R\2", code)
    return code.rstrip(".")


def _base_ambito_key(raw: str) -> str | None:
    norm = _normalize_ambito(raw)
    m = re.match(r"^(UNP-\d+R\d*|UP-\d+[A-Z0-9]*)", norm)
    if m:
        return m.group(1)
    m2 = re.search(r"(UNP-\d+R\d*|UP-\d+[A-Z0-9]*)", norm)
    return m2.group(1) if m2 else None


def _named_sector_to_ambito(name: str) -> str | None:
    n = name.lower()
    if "villa alegr" in n:
        return "UNP-3R1"
    if "los lorcas" in n:
        return "UNP-3R2"
    if "las beatas" in n:
        return "UP-1I"
    if "el moj" in n:
        return "UNP-7R"
    if "puerto pinatar" in n:
        return "UP-5R"
    if "las charcas" in n:
        return "UP-1R"
    if "los saez" in n:
        return "SU Los Saez"
    return None


def _ambito_codes_from_text(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in RE_AMBITO_TOKEN.finditer(text or ""):
        code = _normalize_ambito(m.group(1))
        if code and code not in seen:
            seen.add(code)
            out.append(code)
    m_up = re.search(r"(?i)U\.P\.[\s]*(\d+)R[-_\s]?([A-Z0-9]+)", text or "")
    if m_up:
        code = f"UP-{m_up.group(1)}R{m_up.group(2).upper()}"
        if code not in seen:
            seen.add(code)
            out.append(code)
    for m in RE_NAMED_SECTOR.finditer(text or ""):
        mapped = _named_sector_to_ambito(m.group(1))
        if mapped and mapped not in seen:
            seen.add(mapped)
            out.append(mapped)
    return out


def _proyecto_tipo(blob: str) -> str:
    b = blob.lower()
    if "estudio de detalle" in b or "3/16p" in b:
        return "estudio de detalle"
    if "plan parcial" in b or "u.p." in b or "up-2r" in b:
        return "plan parcial"
    if "pgom" in b or "pgou" in b or "plan general" in b:
        return "planeamiento general"
    if "modificaci" in b:
        return "modificación planeamiento"
    if "informaci" in b and "p" in b and "blica" in b:
        return "información pública"
    if "licencia" in b:
        return "licencia publicada"
    return "urbanismo"


class SanPedroDelPinatarAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + sede STA (T-Systems tablón/catálogo) + WFS SITMURCIA (geometría parcial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wfs_url = str(self.config.get("wfs_url") or WFS_URL)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._wfs_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-san-pedro-del-pinatar/1.0")},
        )
        ctx = self._ssl_ctx if sede or "sede.sanpedrodelpinatar.es" in url else None
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = ["
        start = html.find(needle)
        if start < 0:
            return []
        end = html.find("];", start)
        if end < 0:
            return []
        chunk = html[start + len(needle) - 1 : end + 1]
        try:
            data = json.loads(chunk)
            return data if isinstance(data, list) else []
        except json.JSONDecodeError:
            return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, sede=True)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "PTS2_TABLON")

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url, sede=True)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            keywords = item.get("keywordList") or []
            if not any(str(k.get("code") or "") == URBANISMO_KEYWORD for k in keywords):
                continue
            name = str(item.get("name") or "").strip()
            code = str(item.get("code") or item.get("dboid") or name)
            if not name:
                continue
            rows.append({"name": name, "code": code, "url": f"{self.catalogo_url}#tramite={code}"})
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            page_title = _strip_html(title_m.group(1)) if title_m else seed
            for href in RE_LINK.findall(html):
                url = urljoin(seed, unescape(href))
                if url in seen:
                    continue
                if not any(
                    x in url.lower()
                    for x in (".pdf", "borm", "estudio", "urban", "pgou", "pgom", "plan", "planeam")
                ):
                    continue
                blob = f"{page_title} {url}"
                if not RE_PROYECTO.search(blob) and not RE_LICENCIA.search(blob):
                    continue
                seen.add(url)
                name = Path(urllib.parse.urlparse(url).path).name.replace("-", " ")
                rows.append(
                    {
                        "titulo": (name or page_title)[:500],
                        "fecha": _fecha_from_blob(blob, url),
                        "url": url,
                        "origen": "web_wp",
                        "blob": blob,
                    }
                )
        return rows

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        rem = row.get("remitent") or {}
        remitente = str(rem.get("description") or "")
        fecha = _xml_date(row.get("pubDateIni")) or ""
        expte = str(row.get("externString") or "")
        dboid = str(row.get("dboid") or title)
        url = f"{self.tablon_url}#dboid={dboid}"
        return title, remitente, fecha, expte, url

    def _build_wfs_index(self) -> dict[str, dict[str, Any]]:
        if self._wfs_index is not None:
            return self._wfs_index
        index: dict[str, dict[str, Any]] = {}
        try:
            data = json.loads(self._fetch(self.wfs_url))
        except (urllib.error.URLError, json.JSONDecodeError):
            self._wfs_index = index
            return index
        for feat in data.get("features") or []:
            props = feat.get("properties") or {}
            raw_amb = str(props.get("Ambito") or "")
            geom = feat.get("geometry")
            if not raw_amb or not isinstance(geom, dict):
                continue
            keys = {_normalize_ambito(raw_amb), raw_amb.strip().upper()}
            base = _base_ambito_key(raw_amb)
            if base:
                keys.add(base)
            rec = {
                "geom_geojson": geom,
                "geometry_source": "portal_wfs",
                "geometry_source_url": self.wfs_url,
                "coord_source": "portal_geometry_centroid",
                "ambito": raw_amb,
                "clasificacion": props.get("Clasificacion"),
            }
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
            for key in keys:
                if key and key not in index:
                    index[key] = rec
        self._wfs_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "expte", "blob", "url"))
        index = self._build_wfs_index()
        for code in _ambito_codes_from_text(blob):
            hit = index.get(code) or index.get(code.rstrip("."))
            if not hit:
                base = _base_ambito_key(code)
                if base:
                    hit = index.get(base)
            if not hit:
                continue
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
            return

    def _tramite_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if not RE_LICENCIA.search(name):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", item["code"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "titulo": name[:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": "catalogo",
        }
        self._attach_geometry(rec)
        return rec

    def _web_to_licencia(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        if RE_EXCLUDE.search(blob):
            return None
        url = str(raw.get("url") or self.web_base)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", url),
            "fecha_concesion": raw.get("fecha") or _fecha_from_blob(blob, url),
            "tipo": "formulario / trámite",
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "titulo": str(raw.get("titulo") or "")[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", expte or url),
            "fecha_concesion": fecha or None,
            "tipo": "licencia",
            "distrito": MUNICIPIO,
            "lat": None,
            "lon": None,
            "titulo": title[:500],
            "expte": expte or None,
            "url": url,
            "source": "ayuntamiento",
            "origen": "tablon",
        }
        self._attach_geometry(rec)
        return rec

    def _to_proyecto(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        blob = raw.get("blob") or raw.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        url = str(raw.get("url") or self.web_base)
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": str(raw.get("titulo") or "")[:500],
            "fecha": raw.get("fecha") or _fecha_from_blob(blob, url),
            "tipo": _proyecto_tipo(blob),
            "url": url,
            "source": "ayuntamiento",
            "origen": raw.get("origen"),
        }
        if raw.get("expte"):
            rec["expte"] = raw["expte"]
        self._attach_geometry(rec)
        return rec

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        title, remitente, fecha, expte, url = self._tablon_row(row)
        blob = f"{title} {remitente}"
        is_urb = "URBANISMO" in remitente.upper()
        if RE_EXCLUDE.search(blob):
            return None
        if not is_urb and not RE_PROYECTO.search(blob):
            return None
        return self._to_proyecto(
            {
                "titulo": title,
                "fecha": fecha or None,
                "url": url,
                "blob": blob,
                "expte": expte or None,
                "origen": "tablon",
            }
        )

    def _tramite_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        name = item["name"]
        if RE_LICENCIA.search(name) and not RE_PROYECTO.search(name):
            return None
        if not RE_PROYECTO.search(name):
            return None
        return self._to_proyecto(
            {
                "titulo": name,
                "url": item["url"],
                "blob": name,
                "origen": "catalogo",
            }
        )

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

    def _collect_licencia_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon():
            add(self._tablon_to_licencia(item))
        for item in self._collect_catalog_tramites():
            add(self._tramite_to_licencia(item))
        for item in self._collect_web_docs():
            add(self._web_to_licencia(item))
        return rows

    def _collect_proyecto_rows(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_web_docs():
            add(self._to_proyecto(item))
        for item in self._collect_tablon():
            add(self._tablon_to_proyecto(item))
        for item in self._collect_catalog_tramites():
            add(self._tramite_to_proyecto(item))
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo"),
            "web": sum(1 for r in rows if r.get("origen") == "web_wp"),
        }

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
        rows = self._collect_proyecto_rows()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "web": sum(1 for r in rows if r.get("origen") == "web_wp"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
