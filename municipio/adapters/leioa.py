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

WEB_BASE = "https://www.leioa.net"
SEDE_BASE = "https://udaletxean.leioa.eus"
TRANSP_BASE = "https://leioazabalik.leioa.net"

TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES"
)
CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES"
IP_URBANISMO_URL = (
    f"{TRANSP_BASE}/expedientes-del-area-de-urbanismo-en-exposicion/informacion-publica"
)
PGOU_TRANSP_URL = (
    f"{TRANSP_BASE}/plan-general-de-ordenacion-urbana-pgou-.-modificaciones.-normas-urbanisticas.-informes"
)

ARCGIS_MAP = (
    "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/"
    "LurraldeAntolamendua_PlanificacionTerritorial/PX_Bilbao_Metropolitano_inf/MapServer"
)
PLANEAMIENTO_LAYER_IDS = (100, 119, 120, 121, 122, 134)

MUNICIPIO = "Leioa"
ID_PREFIX = "leioa"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|lizentzia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|modificaci[oó]n|reparcel|"
    r"expropi|sector|programa de actuaci|ordenanza|junta de concertaci|"
    r"normalizaci[oó]n de fincas|actuaci[oó]n integrada)",
)
RE_FECHA_DMY_DOT = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
RE_FECHA_DMY_SLASH = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_EXP_CODE = re.compile(r"\b20\d{2}/[0-9A-Z]+(?:/[0-9A-Z0-9]+)?\b")
RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{5,}")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha(text: str | None) -> str | None:
    if not text:
        return None
    m = RE_FECHA_DMY_DOT.search(text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_DMY_SLASH.search(text)
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
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


def _tipo_proyecto(titulo: str) -> str:
    b = (titulo or "").lower()
    if "convenio" in b:
        return "convenio urbanístico"
    if "plan parcial" in b or "modificaci" in b and "plan parcial" in b:
        return "plan parcial"
    if "pgou" in b or "plan general" in b:
        return "PGOU"
    if "plan especial" in b:
        return "plan especial"
    if "expropi" in b:
        return "expropiación"
    if "junta de concertaci" in b:
        return "gestión urbanística"
    if "ordenanza" in b:
        return "ordenanza urbanística"
    if "licitaci" in b or "contrat" in b:
        return "contratación urbanística"
    return "información pública / urbanismo"


class LeioaAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede STA (tablón PTS_TABLON + catálogo) + portal transparencia Liferay (IP urbanismo)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transp_base = str(self.config.get("transp_base") or TRANSP_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.ip_url = str(self.config.get("ip_urbanismo_url") or IP_URBANISMO_URL)
        self.arcgis_map = str(self.config.get("arcgis_map_url") or ARCGIS_MAP)
        self.planeamiento_layers = tuple(
            int(x) for x in (self.config.get("planeamiento_layer_ids") or PLANEAMIENTO_LAYER_IDS)
        )
        self.geometry_enrich = bool(self.config.get("geometry_enrich", True))
        self.geometry_max_rows = int(self.config.get("geometry_max_rows", 5))
        self._geometry_attempts = 0
        self._tablon_cache: list[dict[str, Any]] | None = None
        self._catalog_cache: list[dict[str, Any]] | None = None
        self._ip_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-leioa/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-leioa/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    @staticmethod
    def _extract_sta_dataset(html: str, names: tuple[str, ...] = ("PTS_TABLON", "PTS2_TABLON")) -> list[dict[str, Any]]:
        for dataset_name in names:
            needle = f"var dataset_{dataset_name} = ["
            start = html.find(needle)
            if start < 0:
                continue
            end = html.find("];", start)
            if end < 0:
                continue
            chunk = html[start + len(needle) - 1 : end + 1]
            try:
                data = json.loads(chunk)
                if isinstance(data, list) and data:
                    return data
            except json.JSONDecodeError:
                continue
        return []

    def _collect_tablon(self) -> list[dict[str, Any]]:
        if self._tablon_cache is not None:
            return self._tablon_cache
        html = self._fetch(self.tablon_url)
        self._tablon_cache = self._extract_sta_dataset(html)
        return self._tablon_cache

    def _collect_catalog(self) -> list[dict[str, Any]]:
        if self._catalog_cache is not None:
            return self._catalog_cache
        html = self._fetch(self.catalogo_url)
        needle = "var dataset_CATSERV = ["
        start = html.find(needle)
        if start < 0:
            self._catalog_cache = []
            return self._catalog_cache
        end = html.find("];", start)
        if end < 0:
            return []
        try:
            data = json.loads(html[start + len(needle) - 1 : end + 1])
            self._catalog_cache = data if isinstance(data, list) else []
            return self._catalog_cache
        except json.JSONDecodeError:
            self._catalog_cache = []
            return self._catalog_cache

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=ES"
        )

    def _tablon_row(self, row: dict[str, Any]) -> tuple[str, str, str, str]:
        title = str(row.get("descriptionProc") or row.get("externString") or "").strip()
        extern = str(row.get("externString") or "").strip()
        if extern and extern not in title:
            title = f"{extern} — {title}" if title else extern
        fecha = _xml_date(row.get("pubDateIni")) or ""
        dboid = str(row.get("dboid") or title)
        url = self._tablon_detail_url(dboid)
        return title, fecha, url, extern

    def _abs_transp_url(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return f"{self.transp_base}{href if href.startswith('/') else '/' + href}"

    def _parse_ip_table(self) -> list[dict[str, Any]]:
        if self._ip_cache is not None:
            return self._ip_cache
        try:
            html = self._fetch(self.ip_url)
        except urllib.error.URLError:
            self._ip_cache = []
            return self._ip_cache
        article = re.search(
            r"journal-content-article[^>]*>(.*?)<div class=\"entry-links",
            html,
            re.S,
        )
        content = article.group(1) if article else html
        records: list[dict[str, Any]] = []
        seen: set[str] = set()
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", content, re.S | re.I):
            cells_raw = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            cells = [_strip_html(c) for c in cells_raw]
            cells = [c for c in cells if c]
            if len(cells) < 2:
                continue
            titulo = cells[0]
            exp_match = RE_EXP_CODE.search(" ".join(cells[1:4]))
            if not exp_match and not RE_PROYECTO.search(titulo):
                continue
            expediente = exp_match.group(0) if exp_match else ""
            fecha = ""
            for cell in cells[2:6]:
                f = _parse_fecha(cell)
                if f:
                    fecha = f
                    break
            links = [
                self._abs_transp_url(h)
                for h in re.findall(r'href="([^"]+)"', tr)
                if "/documents/" in h or h.endswith(".pdf")
            ]
            key = expediente or titulo[:120]
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente,
                    "fecha": fecha,
                    "url": self.ip_url,
                    "pdf_url": links[0] if links else None,
                }
            )
        self._ip_cache = records
        return records

    def _geom_search_tokens(self, text: str) -> list[str]:
        stop = {
            "leioa",
            "ayuntamiento",
            "aprobacion",
            "inicial",
            "definitiva",
            "publica",
            "informacion",
            "expediente",
            "sector",
            "area",
            "plan",
            "urbanismo",
        }
        seen: set[str] = set()
        out: list[str] = []
        for m in RE_TOKEN.finditer(text or ""):
            w = m.group(0)
            key = w.lower()
            if key in stop or len(key) < 5:
                continue
            if key not in seen:
                seen.add(key)
                out.append(w)
        for m in re.finditer(r"(?i)(?:sector|área|area)\s+([0-9A-Z\-]+)", text or ""):
            tok = m.group(1)
            if tok.lower() not in seen:
                seen.add(tok.lower())
                out.append(tok)
        return out[:5]

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if self._geometry_attempts >= self.geometry_max_rows:
            return None
        self._geometry_attempts += 1
        for token in self._geom_search_tokens(titulo):
            esc = token.replace("'", "''")
            where = f"(ETIQUETA LIKE '%{esc}%' OR DESCRIPCION LIKE '%{esc}%')"
            for layer_id in self.planeamiento_layers[:2]:
                params = {
                    "where": where,
                    "outFields": "ETIQUETA,DESCRIPCION,CODAREAF",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "geojson",
                    "resultRecordCount": "1",
                }
                url = f"{self.arcgis_map}/{layer_id}/query?{urllib.parse.urlencode(params)}"
                try:
                    data = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                    continue
                feats = data.get("features") if isinstance(data, dict) else None
                if not feats:
                    continue
                geom = feats[0].get("geometry") if isinstance(feats[0], dict) else None
                if not isinstance(geom, dict) or not geom.get("type"):
                    continue
                return {
                    "geom_geojson": geom,
                    "geometry_source": "portal_visor_arcgis",
                    "geometry_source_url": url,
                    "coord_source": "portal_geometry_centroid",
                }
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if not self.geometry_enrich or record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""))
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec["lat"], rec["lon"] = cen

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def _catalog_licencia_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._collect_catalog():
            name = _strip_html(str(item.get("name") or ""))
            if not name or not RE_LICENCIA.search(name):
                continue
            dboid = str(item.get("dboid") or name)
            url = (
                f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
                f"APP_CODE=STA&PAGE_CODE=CATALOGO&DETALLE={dboid}&lang=ES"
            )
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": name[:200],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_catalogo",
                }
            )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._catalog_licencia_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tablon():
            title, fecha, url, _ = self._tablon_row(item)
            if not RE_LICENCIA.search(title):
                continue
            rec = {
                "id": _stable_id("lic", url),
                "fecha_concesion": fecha or None,
                "tipo": "licencia / tablón",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": title[:500],
                "url": url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "catalogo": len(self._catalog_licencia_pages())}

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

        for doc in self._parse_ip_table():
            titulo = doc["titulo"]
            exp = doc.get("expediente") or ""
            key = f"ip-{exp}-{titulo[:80]}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": doc.get("fecha") or None,
                "tipo": _tipo_proyecto(titulo),
                "url": doc.get("pdf_url") or doc["url"],
                "source": "ayuntamiento",
                "origen": "transparencia_ip",
            }
            if exp:
                rec["expediente"] = exp
            if doc.get("pdf_url"):
                rec["pdf_url"] = doc["pdf_url"]
            self._attach_geometry(rec)
            add(rec)

        for item in self._collect_tablon():
            title, fecha, url, extern = self._tablon_row(item)
            if RE_LICENCIA.search(title) and not RE_PROYECTO.search(title):
                continue
            if not RE_PROYECTO.search(title):
                continue
            rec = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": fecha or None,
                "tipo": _tipo_proyecto(title),
                "url": url,
                "source": "ayuntamiento",
                "origen": "sede_tablon",
            }
            if extern:
                rec["expediente"] = extern
            self._attach_geometry(rec)
            add(rec)

        add(
            {
                "id": _stable_id("proy", PGOU_TRANSP_URL),
                "municipio": MUNICIPIO,
                "titulo": "Plan General de Ordenación Urbana (PGOU) de Leioa — documentación en portal de transparencia",
                "fecha": "2001-06-04",
                "tipo": "PGOU",
                "url": PGOU_TRANSP_URL,
                "source": "ayuntamiento",
                "origen": "transparencia_pgou",
            }
        )

        ip_rows = self._parse_ip_table()
        tablon_urban = sum(
            1 for item in self._collect_tablon() if RE_PROYECTO.search(self._tablon_row(item)[0])
        )
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "ip_rows": len(ip_rows),
            "tablon_urban": tablon_urban,
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
