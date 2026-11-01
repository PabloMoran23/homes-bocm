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

BASE = "https://www.basauri.eus"
SEDE_BASE = "https://sede.basauri.eus"
KARPETA_TABLON = (
    "https://karpeta.basauri.eus/sta/CarpetaPublic/doEvent?"
    "APP_CODE=STA&PAGE_CODE=BAS_TABLON&lang=es"
)
CATALOGO_URL = f"{SEDE_BASE}/sede/index.php?catalogo=1&idioma=es"
MUNICIPIO = "Basauri"
ID_PREFIX = "basauri"

ARCGIS_MAP = (
    "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/"
    "LurraldeAntolamendua_PlanificacionTerritorial/PX_Bilbao_Metropolitano_inf/MapServer"
)
PLANEAMIENTO_LAYER_IDS = (119, 120, 121, 122, 134)

DEFAULT_SEEDS: list[str] = [
    f"{BASE}/es/gestion-urbanistica",
    f"{BASE}/es/gestion-urbanistica/convenios-urbanisticos",
    f"{BASE}/es/pagina/planeamiento-de-desarrollo-urbanistico",
    f"{BASE}/es/pagina/modificaciones-urbanisticas",
    f"{BASE}/es/pagina/plan-general-de-ordenacion-urbana-de-basauri-pgou",
    f"{BASE}/es/pgou",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|de inicio)|obra(s)?\s+de\s+edificaci[oó]n|demolici[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial)|pgou|peou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|sector|"
    r"actuaci[oó]n|reparcel|urbanizaci[oó]n|normativa urban)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/sites/basauri/files/(\d{4})-(\d{2})/")
RE_CONVENIO_PATH = re.compile(r'href="(/es/convenio/[^"#?]+)"', re.I)
RE_LINK_PAIR = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>([^<]{4,300})</a>', re.I)
RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{4,}")


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _tipo_proyecto(blob: str) -> str:
    b = (blob or "").lower()
    if "convenio" in b:
        return "convenio urbanístico"
    if "peou" in b or "plan especial" in b:
        return "plan especial / PEOU"
    if "plan parcial" in b or "pp " in b:
        return "plan parcial"
    if "modificaci" in b:
        return "modificación urbanística"
    if "pgou" in b:
        return "PGOU"
    if "actuaci" in b:
        return "actuación urbanística"
    if "informaci" in b and "públic" in b:
        return "información pública"
    return "planeamiento / urbanismo"


class BasauriAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal 10 (gestión urbanística) + sede Joomla/STA (catálogo trámites; tablón karpeta)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEEDS)]
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.tablon_url = str(self.config.get("tablon_url") or KARPETA_TABLON)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.arcgis_map = str(self.config.get("arcgis_map_url") or ARCGIS_MAP)
        self.planeamiento_layers = tuple(
            int(x) for x in (self.config.get("planeamiento_layer_ids") or PLANEAMIENTO_LAYER_IDS)
        )
        self.geometry_enrich = bool(self.config.get("geometry_enrich", True))
        self.geometry_max_rows = int(self.config.get("geometry_max_rows", 8))
        self._geometry_attempts = 0
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("karpeta_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, use_karpeta_ssl: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-basauri/1.0")},
        )
        ctx = self._ssl_ctx if use_karpeta_ssl or "karpeta.basauri.eus" in url else None
        timeout = float(
            self.config.get("tablon_timeout_s", 15)
            if "karpeta.basauri.eus" in url
            else self.config.get("request_timeout_s", 60)
        )
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_portal(self, href: str) -> str:
        return urllib.parse.urljoin(BASE + "/", href)

    def _abs_sede(self, href: str) -> str:
        if href.startswith("http"):
            return href
        return urllib.parse.urljoin(self.sede_base + "/", href.lstrip("/"))

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I | re.S)
            if m:
                title = _strip_html(m.group(1))
                title = re.sub(r"\s*\|\s*Ayuntamiento de Basauri\s*$", "", title, flags=re.I)
                if title:
                    return title[:500]
        return fallback[:500]

    def _page_fecha(self, html: str, url: str = "") -> str | None:
        m = re.search(r'<time[^>]+datetime="([^"]+)"', html, re.I)
        if m:
            return m.group(1)[:10]
        fecha = _parse_fecha_dmy(html)
        if fecha:
            return fecha
        return _fecha_from_url(url)

    def _geom_search_tokens(self, text: str) -> list[str]:
        stop = {
            "basauri",
            "ayuntamiento",
            "convenio",
            "planeamiento",
            "urbanismo",
            "plan",
            "proyecto",
            "sector",
            "actuacion",
            "actuación",
        }
        seen: set[str] = set()
        out: list[str] = []
        for m in RE_TOKEN.finditer(text or ""):
            w = m.group(0)
            key = w.lower()
            if key in stop or len(key) < 4:
                continue
            if key not in seen:
                seen.add(key)
                out.append(w)
        return out[:5]

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if self._geometry_attempts >= self.geometry_max_rows:
            return None
        self._geometry_attempts += 1
        for token in self._geom_search_tokens(titulo):
            esc = token.replace("'", "''")
            where = f"(ETIQUETA LIKE '%{esc}%' OR DESCRIPCION LIKE '%{esc}%')"
            for layer_id in self.planeamiento_layers:
                params = {
                    "where": where,
                    "outFields": "ETIQUETA,DESCRIPCION",
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

    def _collect_convenios(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(f"{BASE}/es/gestion-urbanistica/convenios-urbanisticos")
        except urllib.error.URLError:
            return rows
        for m in RE_CONVENIO_PATH.finditer(html):
            path = unescape(m.group(1))
            if path in seen:
                continue
            seen.add(path)
            url = self._abs_portal(path)
            try:
                page = self._fetch(url)
            except urllib.error.URLError:
                page = ""
            title = self._page_title(page, path.rsplit("/", 1)[-1].replace("-", " "))
            fecha = self._page_fecha(page, url) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": title[:500],
                "fecha": fecha,
                "tipo": _tipo_proyecto(title),
                "url": url,
                "source": "ayuntamiento",
                "origen": "drupal_convenio",
            }
            self._attach_geometry(rec)
            rows.append(rec)
        return rows

    def _collect_seed_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        def add(url: str, titulo: str, origen: str) -> None:
            if not RE_PROYECTO.search(f"{titulo} {url}"):
                return
            if url in seen_urls:
                return
            seen_urls.add(url)
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": _fecha_from_url(url) or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "tipo": _tipo_proyecto(titulo),
                "url": url,
                "source": "ayuntamiento",
                "origen": origen,
            }
            self._attach_geometry(rec)
            rows.append(rec)

        for seed in self.seed_pages:
            try:
                html = self._fetch(seed)
            except urllib.error.URLError:
                continue
            for m in RE_LINK_PAIR.finditer(html):
                href = unescape(m.group(1))
                text = _strip_html(m.group(2))
                if not text or len(text) < 4:
                    continue
                if href.startswith("#") or "javascript:" in href.lower():
                    continue
                if any(x in href.lower() for x in ("/buscador", "/pagina/accesibilidad", "/basauri-le-atiende")):
                    continue
                low = f"{text} {href}".lower()
                if not (
                    RE_PROYECTO.search(low)
                    or href.endswith(".pdf")
                    or "/convenio/" in href
                    or "/sites/basauri/files/" in href
                ):
                    continue
                if href.startswith("http"):
                    url = href
                else:
                    url = self._abs_portal(href)
                if "/convenio/" in url:
                    continue
                if "basauri.eus" not in url and not url.endswith(".pdf"):
                    continue
                add(url, text, "drupal_semilla")
        return rows

    def _parse_tablon_rows(self, html_text: str) -> list[dict[str, Any]]:
        m = re.search(r"var metadata_TABLON[^=]*=\s*(\{.*?\}),\s*\n", html_text, re.S)
        if not m:
            return []
        blob = m.group(1)
        rows: list[dict[str, Any]] = []
        pat = re.compile(
            r'\{"data":\[\{"value":"([^"]+)"\},\{"value":"([^"]+)","linkHref":"([^"]+)"[^}]*\},\{"value":"([^"]+)"\}\]\}',
        )
        for match in pat.finditer(blob):
            fecha_raw, desc_raw, link, cat_raw = match.groups()
            desc = unescape(desc_raw)
            blob_cat = f"{desc} {unescape(cat_raw)}"
            if not RE_LICENCIA.search(blob_cat) and not RE_PROYECTO.search(blob_cat):
                continue
            kind = "lic" if RE_LICENCIA.search(blob_cat) else "proy"
            fecha = _parse_fecha_dmy(fecha_raw) or _fecha_from_url(link)
            rows.append(
                {
                    "kind": kind,
                    "fecha": fecha,
                    "titulo": desc[:500],
                    "categoria": unescape(cat_raw),
                    "url": link if link.startswith("http") else self._abs_sede(link),
                    "origen": "sta_tablon",
                }
            )
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, use_karpeta_ssl=True)
        except (urllib.error.URLError, TimeoutError):
            return []
        return self._parse_tablon_rows(html)

    def _collect_catalogo_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return rows
        seen: set[str] = set()
        for m in re.finditer(
            r'href="((?:https://sede\.basauri\.eus)?/es/tramite\?[^"]+)"[^>]*>([^<]{5,200})</a>',
            html,
            re.I,
        ):
            href, title_raw = m.group(1), unescape(m.group(2)).strip()
            if not RE_LICENCIA.search(title_raw):
                continue
            url = self._abs_sede(href.replace("&amp;", "&"))
            if url in seen:
                continue
            seen.add(url)
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": title_raw[:200],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title_raw[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "sede_catalogo",
                    "nota": "Trámite informativo; no concesión publicada en listado",
                }
            )
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        self._geometry_attempts = 0
        by_id: dict[str, dict[str, Any]] = {}

        def put(rec: dict[str, Any]) -> None:
            by_id[rec["id"]] = rec

        for rec in self._collect_convenios():
            put(rec)
        for rec in self._collect_seed_documents():
            put(rec)

        for item in self._collect_tablon():
            if item["kind"] != "proy":
                continue
            rec: dict[str, Any] = {
                "id": _stable_id("proy", item["url"]),
                "municipio": MUNICIPIO,
                "titulo": item["titulo"],
                "fecha": item.get("fecha") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "tipo": _tipo_proyecto(item["titulo"]),
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": item["origen"],
                "categoria_tablon": item.get("categoria"),
            }
            self._attach_geometry(rec)
            put(rec)

        return list(by_id.values())

    def _collect_licencias(self) -> list[dict[str, Any]]:
        by_id: dict[str, dict[str, Any]] = {}
        for rec in self._collect_catalogo_licencias():
            by_id[rec["id"]] = rec
        for item in self._collect_tablon():
            if item["kind"] != "lic":
                continue
            rec = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": item.get("fecha"),
                "tipo": item.get("categoria") or "licencia / edicto",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": item["titulo"],
                "url": item["url"],
                "source": "ayuntamiento",
                "origen": item["origen"],
            }
            by_id[rec["id"]] = rec
        return list(by_id.values())

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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "catalogo": sum(1 for r in rows if r.get("origen") == "sede_catalogo"),
            "tablon": sum(1 for r in rows if r.get("origen") == "sta_tablon"),
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
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "convenios": sum(1 for r in rows if r.get("origen") == "drupal_convenio"),
            "semillas": sum(1 for r in rows if r.get("origen") == "drupal_semilla"),
            "tablon": sum(1 for r in rows if r.get("origen") == "sta_tablon"),
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
