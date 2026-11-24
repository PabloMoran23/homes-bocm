from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records

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

WEB_BASE = "https://redondela.gal"
SEDE_BASE = "https://redondela.sedelectronica.gal"
MUNICIPIO = "Redondela"
ID_PREFIX = "redondela"
INE = "36045"
WAYBACK_PREFIX = "https://web.archive.org/web/2024/"

SIOTUGA_INVENTARIO = (
    f"https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello={INE}&lang=es_ES"
)
SIOTUGA_QUERY_DOC = "https://siotuga.xunta.gal/siotuga/assets/inventario/query_document.php"
SIOTUGA_WMS = f"https://siotuga.xunta.gal/siotuga/ws?codine={INE}"
ARCGIS_FS = (
    "https://services-eu1.arcgis.com/KmoBn3Qii9gbOa4C/arcgis/rest/services"
)
PXOM_ARCGIS_APP = (
    "https://redondela.maps.arcgis.com/apps/instant/sidebar/index.html"
    "?appid=f29c9e98a39342aab3369148a80b1f63"
)
PXOM_EXPERIENCE = "https://experience.arcgis.com/experience/81494d91a3ae4e8ba912219a05a10ca9"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/gl/pxom/",
    f"{WEB_BASE}/es/pxom/",
    f"{WEB_BASE}/sede-electronica/",
    f"{WEB_BASE}/gl/sede-electronica/",
]

DEFAULT_LICENCIA_SEEDS: list[tuple[str, str]] = [
    ("Sede electrónica — Concello de Redondela", SEDE_BASE),
    ("Sede electrónica (información)", f"{WEB_BASE}/sede-electronica/"),
    (
        "Visor «O PXOM nun clic» — trámites e consulta planeamento",
        PXOM_EXPERIENCE,
    ),
]

RE_HREF = re.compile(r'href="([^"]+)"', re.I)
RE_PDF = re.compile(r"\.pdf(?:\?|#|$)", re.I)
RE_FECHA_ISO = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{5,}")
RE_URBAN = re.compile(
    r"(?i)(urban|licen|planeam|pxom|pxou|obra|territ|convenio|sector|reparcel|"
    r"exposici[oó]n|informaci[oó]n p[uú]blica|modificaci[oó]n|ordenanza|instrumento)",
)
RE_PROYECTO = re.compile(
    r"(?i)(plan|planeam|pxom|pxou|sector|convenio|urban|exposici[oó]n|"
    r"informaci[oó]n p[uú]blica|modificaci[oó]n|reparcel|instrumento|peri|sunp)",
)

GEOM_LAYERS: list[tuple[str, int, str]] = [
    ("T36045_PXOM_AI_Malla_SUC_2000_(VP)", 0, "Nombre"),
    ("T36045_PXOM_AI_Malla_5000_(VP)", 0, "NOMBRE"),
]


def _wayback_url(url: str) -> str:
    return f"{WAYBACK_PREFIX}{url}"


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(base_page: str, href: str) -> str:
    href = unescape(href.strip())
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return WEB_BASE.rstrip("/") + href
    return urllib.parse.urljoin(base_page, href)


def _parse_fecha(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _proyecto_tipo(titulo: str, figura: str | None = None) -> str:
    blob = f"{titulo} {figura or ''}".lower()
    if "pxom" in blob or "plan xeral" in blob or "plan general" in blob:
        return "plan general (PXOM)"
    if "normas subsidiarias" in blob:
        return "normas subsidiarias"
    if "peri" in blob or "reforma interior" in blob:
        return "PERI / plan especial"
    if "sunp" in blob or "sectoriz" in blob or "polígono" in blob or "poligono" in blob:
        return "planeamiento de desarrollo"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "exposici" in blob or "información pública" in blob:
        return "información pública"
    return figura or "planeamiento"


class RedondelaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress redondela.gal (403 en cloud) + SIOTUGA 36045 + ArcGIS Hub PXOM."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_siotuga_des = int(self.config.get("max_siotuga_desarrollo", 80))
        self.wayback_fallback = bool(self.config.get("wayback_fallback", True))
        self._direct_blocked = bool(self.config.get("prefer_wayback", False))
        self._direct_timeout_s = float(self.config.get("direct_timeout_s", 12))
        geom_cfg = self.config.get("geometry") or {}
        self.geometry_enrich = bool(self.config.get("geometry_enrich", True))
        self.geometry_max_rows = int(self.config.get("geometry_max_rows", 25))
        self._geometry_attempts = 0
        self._arcgis_fs = str(self.config.get("arcgis_feature_server") or ARCGIS_FS).rstrip("/")
        self._geom_layers: list[tuple[str, int, str]] = [
            tuple(x)  # type: ignore[misc]
            for x in (self.config.get("arcgis_layers") or GEOM_LAYERS)
        ]
        self._jar = http.cookiejar.CookieJar()
        self._opener = self._build_opener()
        self._siotuga_token: str | None = None

    def _build_opener(self) -> urllib.request.OpenerDirector:
        handlers: list[Any] = [urllib.request.HTTPCookieProcessor(self._jar)]
        if self.config.get("insecure_ssl", True):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            handlers.append(urllib.request.HTTPSHandler(context=ctx))
        return urllib.request.build_opener(*handlers)

    def _fetch(
        self,
        url: str,
        *,
        data: bytes | None = None,
        charset: str | None = None,
        use_wayback: bool = False,
    ) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-redondela/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        candidates: list[str] = []
        if use_wayback and self.wayback_fallback:
            candidates.append(_wayback_url(url))
        elif not self._direct_blocked:
            candidates.append(url)
        if self.wayback_fallback and url not in candidates:
            candidates.append(_wayback_url(url))
        last_err: urllib.error.URLError | None = None
        for attempt_url in candidates:
            timeout = self._direct_timeout_s if attempt_url == url else 75.0
            req = urllib.request.Request(attempt_url, data=data, headers=headers)
            try:
                with self._opener.open(req, timeout=timeout) as resp:
                    enc = charset or resp.headers.get_content_charset() or "utf-8"
                    body = resp.read().decode(enc, errors="replace")
                    if attempt_url == url and "403 | Forbidden" in body[:800]:
                        self._direct_blocked = True
                        continue
                    return body
            except urllib.error.URLError as exc:
                last_err = exc
                if attempt_url == url:
                    self._direct_blocked = True
                continue
        raise last_err or urllib.error.URLError("fetch failed")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-redondela/1.0")},
        )
        with self._opener.open(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _get_siotuga_token(self) -> str:
        if self._siotuga_token:
            return self._siotuga_token
        html = self._fetch(SIOTUGA_INVENTARIO, charset="utf-8")
        m = re.search(r"name=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            m = re.search(r"id=['\"]token['\"][^>]*value=['\"]([^'\"]+)['\"]", html, re.I)
        if not m:
            raise RuntimeError("SIOTUGA: no se encontró token de sesión")
        self._siotuga_token = m.group(1)
        return self._siotuga_token

    def _siotuga_query(self, idclase: int) -> list[dict[str, Any]]:
        token = self._get_siotuga_token()
        data = f"id={INE}&token={token}&idclase={idclase}".encode()
        raw = self._fetch(SIOTUGA_QUERY_DOC, data=data, charset="utf-8")
        if raw.strip().startswith("tokenIncorrecto"):
            return []
        try:
            docs = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return docs if isinstance(docs, list) else []

    def _collect_siotuga(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for doc in self._siotuga_query(14):
            rows.append(
                {
                    "titulo": doc.get("docnome") or "Plan xeral",
                    "fecha": doc.get("fechaaddef"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(str(doc.get("docnome") or ""), str(doc.get("figura") or "")),
                    "origen": "siotuga_pg",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        for doc in self._siotuga_query(13)[: self.max_siotuga_des]:
            rows.append(
                {
                    "titulo": doc.get("docnome") or "Planeamento desenvolvemento",
                    "fecha": doc.get("fechaaddef"),
                    "url": SIOTUGA_INVENTARIO,
                    "tipo": _proyecto_tipo(str(doc.get("docnome") or ""), str(doc.get("figura") or "")),
                    "origen": "siotuga_des",
                    "siotuga_id": doc.get("id"),
                    "figura": doc.get("figura"),
                }
            )
        return rows

    def _fixed_proyecto_seeds(self) -> list[dict[str, Any]]:
        return [
            {
                "titulo": "PXOM — portal municipal (WordPress)",
                "fecha": None,
                "url": f"{self.web_base}/gl/pxom/",
                "tipo": "plan general",
                "origen": "web_pxom",
            },
            {
                "titulo": "Inventario planeamento — SIOTUGA (INE 36045)",
                "fecha": None,
                "url": SIOTUGA_INVENTARIO,
                "tipo": "inventario planeamiento",
                "origen": "siotuga_inventario",
            },
            {
                "titulo": "Visor ArcGIS «O PXOM nun clic»",
                "fecha": None,
                "url": PXOM_ARCGIS_APP,
                "tipo": "visor cartografía PXOM",
                "origen": "arcgis_app",
            },
            {
                "titulo": "Experience Builder — PXOM Redondela 3.0",
                "fecha": None,
                "url": PXOM_EXPERIENCE,
                "tipo": "visor planeamiento",
                "origen": "arcgis_experience",
            },
            {
                "titulo": f"WMS planeamento SIOTUGA (codine {INE})",
                "fecha": None,
                "url": SIOTUGA_WMS,
                "tipo": "cartografía WMS",
                "origen": "siotuga_wms",
            },
        ]

    def _collect_wp_assets(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(titulo: str, url: str, origen: str, fecha: str | None = None) -> None:
            if url in seen:
                return
            if not RE_URBAN.search(f"{titulo} {url}"):
                return
            seen.add(url)
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": url,
                    "tipo": _proyecto_tipo(titulo),
                    "origen": origen,
                }
            )

        for page in self.seed_pages:
            try:
                html = self._fetch(page, use_wayback=True)
            except urllib.error.URLError:
                continue
            for href in RE_HREF.findall(html):
                url = _abs_url(page, href)
                if "redondela.gal" not in url:
                    continue
                if RE_PDF.search(url):
                    name = urllib.parse.unquote(url.rsplit("/", 1)[-1]).replace(".pdf", "").replace("-", " ")
                    add(name or "Documento PDF", url, "wp_pdf", _parse_fecha(url))
                    continue
                if "/pxom" in url.lower() and RE_PROYECTO.search(url):
                    if url.rstrip("/") == page.rstrip("/"):
                        continue
                    slug_part = url.rstrip("/").rsplit("/", 1)[-1].replace("-", " ")
                    add(slug_part or "PXOM", url, "wp_link")

        return rows

    def _geom_search_tokens(self, text: str) -> list[str]:
        stop = {
            "redondela",
            "pxom",
            "plan",
            "planeamento",
            "planeamiento",
            "modificacion",
            "modificación",
            "municipal",
            "ordenacion",
            "ordenación",
            "instrumento",
            "ambito",
            "ámbito",
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
        return out[:6]

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        if self._geometry_attempts >= self.geometry_max_rows:
            return None
        self._geometry_attempts += 1
        for token in self._geom_search_tokens(titulo):
            esc = token.replace("'", "''")
            for svc, layer_id, field in self._geom_layers:
                where = f"({field} LIKE '%{esc}%')"
                params = {
                    "where": where,
                    "outFields": field,
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "geojson",
                    "resultRecordCount": "1",
                }
                layer_url = f"{self._arcgis_fs}/{svc}/FeatureServer/{layer_id}"
                url = f"{layer_url}/query?{urllib.parse.urlencode(params)}"
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

    def _licencia_seeds(self) -> list[dict[str, Any]]:
        return [
            {"titulo": title, "url": url, "origen": "tramite_info", "tipo": "información trámite"}
            for title, url in DEFAULT_LICENCIA_SEEDS
        ]

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.web_base
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}|{row.get('siotuga_id', '')}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(titulo, row.get("figura")),
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("siotuga_id"):
            rec["siotuga_doc_id"] = row["siotuga_id"]
        self._attach_geometry(rec)
        return rec

    def _to_licencia(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        url = row.get("url") or self.sede_base
        return {
            "id": _stable_id("lic", url + titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite / información licencias",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for item in self._licencia_seeds():
            rec = self._to_licencia(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_info"}

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

        def add(item: dict[str, Any]) -> None:
            rec = self._to_proyecto(item)
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._fixed_proyecto_seeds():
            add(item)
        for item in self._collect_siotuga():
            add(item)
        for item in self._collect_wp_assets():
            add(item)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "siotuga": sum(1 for r in rows if str(r.get("origen", "")).startswith("siotuga")),
            "wp": sum(1 for r in rows if str(r.get("origen", "")).startswith("wp_")),
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
