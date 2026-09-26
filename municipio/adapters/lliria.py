from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, unquote

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.lliria.es"
SEDE_BASE = "https://sede.lliria.es"
MUNICIPIO = "Llíria"
ID_PREFIX = "lliria"
WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "InventarioSuSuz"
INE_MUN = "46146"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON&lang=ES"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/es/areas-municipales/urbanismo",
    f"{WEB_BASE}/es/urbanismo",
    f"{WEB_BASE}/es/transparencia",
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "licencia urbanística",
    "licencia de obra",
    "declaración responsable",
    "comunicación previa",
    "certificado urbanístico",
    "compatibilidad urbanística",
    "informe de compatibilidad urbanística",
    "primera ocupación",
    "licencia obras urbanización",
    "licencia urbanística de",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|compatibilidad urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|pai|pop|convenio urban|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|edicto|"
    r"reparcel|estudio de detalle|modificaci[oó]n|sector|urbaniz|expropi|"
    r"integraci[oó]n paisag|participaci[oó]n p[uú]blica|sometimiento|"
    r"homologaci[oó]n|sre-|st-|sunp|sup-|ue-|ppos)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"presupuest|convocatoria del pleno|subvenci[oó]n|huertos urbanos|"
    r"cobranza|iae|bolsa de trabajo|vigilante.*urban|concurso de reels|"
    r"contrataci[oó]n del estado|licitaci[oó]n del expt|relaci[oó]n de puestos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_EXPTE = re.compile(r"(?i)(?:exp(?:te)?\.?|expediente)\s*[:\.]?\s*(\d{1,4}/\d{4}[^/\s]*)")
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SRE|ST|SUNP|SUP|PAI|PPOS|SD|SECTOR)[\s\-]?(?:IND\s*)?[\dA-ZÁÉÍÓÚ'._\-]+(?:[\s,\-yY/]+[\dA-ZÁÉÍÓÚ'._\-]+)*)\b",
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


def _fecha_from_pub_date(pub: dict[str, Any] | None) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


def _clean_title(text: str) -> str:
    t = unescape(text or "")
    return re.sub(r"\s+", " ", t).strip()[:500]


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _clean_title(m.group(1))
        if len(tok) >= 3:
            tokens.append(tok)
    return tokens


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "expropi" in n:
        return "expropiación"
    if "plan especial" in n or "pai" in n:
        return "plan especial / PAI"
    if "plan parcial" in n or "ppos" in n:
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "informaci" in n or "exposici" in n or "sometimiento" in n:
        return "información pública"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "urbaniz" in n:
        return "urbanización"
    if "pge" in n or "pgou" in n or "planeam" in n:
        return "planeamiento"
    if re.search(r"\b(sre|st|sunp|sup|ue)\b", n):
        return "sector planeamiento"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.strip().split()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lon = nums[i], nums[i + 1]
        ring.append([lon, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


class LliriaAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal web (opcional) + sede STA TAO (tablón/catálogo) + ICV InventarioSuSuz WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-lliria/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-lliria/1.0")},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.read()

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_TABLON&lang=ES"
        )

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_CATSERV&lang=ES"
        )

    def _tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rem = item.get("remitent") or {}
            remitente = str(rem.get("description") or "")
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "remitente": remitente,
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(CATALOGO_URL)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_title(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, timeout=25)
            except urllib.error.URLError:
                continue
            for href in RE_PDF.findall(html):
                pdf = urljoin(page_url, href)
                if pdf in seen:
                    continue
                if not any(k in pdf.lower() for k in ("urban", "plane", "licen", "llicen", "pgou", "sector")):
                    continue
                seen.add(pdf)
                name = _clean_title(unquote(Path(pdf).name))
                rows.append(
                    {
                        "titulo": name,
                        "fecha": _parse_fecha_dmy(name) or _parse_fecha_iso(name),
                        "url": page_url,
                        "pdf_url": pdf,
                        "origen": "web_pdf",
                    }
                )
        return rows

    def _parse_wfs_feature(self, feat_el: ET.Element) -> dict[str, Any] | None:
        props: dict[str, Any] = {}
        geom: dict[str, Any] | None = None
        for child in feat_el:
            tag = child.tag.split("}", 1)[-1]
            if tag == "msGeometry":
                for gchild in child.iter():
                    gtag = gchild.tag.split("}", 1)[-1]
                    if gtag == "posList" and gchild.text:
                        geom = _gml_poslist_to_polygon(gchild.text)
            elif child.text and tag not in {"boundedBy", "msGeometry"}:
                props[tag] = child.text.strip()
        if props.get("cod_ine_mun") != self.ine_mun:
            return None
        pp = _clean_title(str(props.get("pp") or ""))
        ue = _clean_title(str(props.get("ue") or ""))
        titulo = pp
        if ue and ue.lower() not in titulo.lower():
            titulo = f"{pp} ({ue})" if pp else ue
        if not titulo:
            titulo = _clean_title(str(props.get("clasificacion") or ""))
        if not titulo:
            return None
        fecha = _parse_fecha_iso(str(props.get("f_aprob") or "")) or _parse_fecha_iso(
            str(props.get("f_public") or "")
        )
        key = str(props.get("id") or titulo)
        wfs_url = (
            f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
            f"&count=1&STARTINDEX=0"
        )
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"wfs:{key}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _proyecto_tipo(f"{titulo} {props.get('clasificacion', '')}"),
            "url": f"{self.sede_base}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON&lang=ES",
            "source": "ayuntamiento",
            "origen": "icv_wfs",
            "clasificacion": props.get("clasificacion"),
            "pp": pp or None,
            "ue": ue or None,
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = wfs_url
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        start = 0
        step = 200
        while start < 12000:
            url = (
                f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
                f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
                f"&count={step}&STARTINDEX={start}"
            )
            try:
                raw = self._fetch_bytes(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = [el for el in root if el.tag.endswith("member")]
            if not members:
                break
            for member in members:
                rec = self._parse_wfs_feature(member[0])
                if rec:
                    rows.append(rec)
            start += step
            if len(members) < step:
                break
        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._wfs_by_key[tok.lower()] = rec
        return rows

    def _match_wfs(self, text: str) -> dict[str, Any] | None:
        if self._wfs_by_key is None:
            self._collect_wfs_proyectos()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._wfs_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        for tok in _sector_tokens(text):
            hit = (self._wfs_by_key or {}).get(tok.lower())
            if hit:
                return hit
        return None

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        wfs_rec = self._match_wfs(str(rec.get("titulo") or ""))
        if not wfs_rec:
            return
        for key in (
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if wfs_rec.get(key) is not None:
                rec[key] = wfs_rec[key]

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row['titulo']} {row.get('extern', '')} {row.get('remitente', '')}"
        if not RE_LICENCIA.search(blob):
            return None
        if RE_NOISE.search(blob) and not re.search(r"(?i)licencia|licència|llic|compatibilidad", blob):
            return None
        key = row.get("dboid") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"expte": m.group(1)} if (m := RE_EXPTE.search(row["titulo"])) else {}),
        }

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        lower = titulo.lower()
        if not any(p in lower for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Trámite del catálogo sede; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('remitente', '')} {row.get('extern', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        if RE_NOISE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("dboid") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        if row.get("extern"):
            rec["expte"] = row["extern"]
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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for row in self._tablon_rows():
            rec = self._tablon_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._catalog_rows():
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._tablon_rows():
            add(self._row_to_proyecto(row))
        for row in self._collect_web_docs():
            add(self._row_to_proyecto(row))
        for rec in self._collect_wfs_proyectos():
            add(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tablon_catalogo"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "source": "tablon_icv_wfs",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
