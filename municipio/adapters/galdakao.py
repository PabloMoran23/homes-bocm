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
from municipio.http import fetch_text

PORTAL_BASE = "https://www.galdakao.eus"
SEDE_BASE = "https://galdakao.egoitzaelektronikoa.eus"
MUNICIPIO = "Galdakao"
ID_PREFIX = "galdakao"

BIZKAIA_PUR_URL = (
    "https://www.bizkaia.eus/es/planeamiento-urbanistico-buscador"
    "?p_p_id=IYBIWPUC_INSTANCE_CadYBlTy6tfn&p_p_lifecycle=0"
    "&p_p_state=normal&p_p_mode=view"
)
BIZKAIA_MUNICIPIO_ID = "36"

URBANISMO_URL = f"{PORTAL_BASE}/urbanismo-obras"
PLANEAMIENTO_URL = f"{PORTAL_BASE}/planeamiento"

ARCGIS_MAP = (
    "https://geo.bizkaia.eus/arcgisserverinspire/rest/services/"
    "LurraldeAntolamendua_PlanificacionTerritorial/PX_Bilbao_Metropolitano_inf/MapServer"
)
PLANEAMIENTO_LAYER_IDS = (100, 119, 120, 121, 122, 134)

DEFAULT_LICENCIA_SEEDS: list[tuple[str, str]] = [
    (f"{SEDE_BASE}/board", "Tablón electrónico de anuncios (sede)"),
    (f"{SEDE_BASE}/dossier", "Catálogo de trámites — sede electrónica"),
    (URBANISMO_URL, "Urbanismo y obras — portal municipal"),
]

DEFAULT_DOCUMENTED_PROYECTOS: list[dict[str, Any]] = [
    {
        "titulo": "Aprobación inicial del Estudio de Detalle parcela 29-31 de Merkadillo",
        "url": URBANISMO_URL,
        "fecha": "",
        "tipo": "estudio de detalle",
        "geom_tokens": ["Merkadillo", "29-31"],
    },
    {
        "titulo": "Modificación UE-BE-3",
        "url": URBANISMO_URL,
        "fecha": "",
        "tipo": "unidad de ejecución",
        "geom_tokens": ["UE-BE-3", "BE-3"],
    },
    {
        "titulo": "Aprobación Definitiva de la unidad UEZU3",
        "url": URBANISMO_URL,
        "fecha": "",
        "tipo": "unidad de ejecución",
        "geom_tokens": ["UEZU3"],
    },
    {
        "titulo": "Aprobación Inicial del Proyecto de Reparcelación de la unidad UECR9",
        "url": URBANISMO_URL,
        "fecha": "",
        "tipo": "reparcelación",
        "geom_tokens": ["UECR9"],
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|lizentzia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:menor|mayor|txiki)|jardueren erantzukizun|"
    r"exposici[oó]n p[uú]blica.*licen|informaci[oó]n p[uú]blica.*licen|jendeaurrekoa)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio de detalle|urbanizaci[oó]n|unidad de ejecuci[oó]n|\bue[- ]?[a-z0-9]+|"
    r"instrumento|sector|peri|nnss|aprobaci[oó]n (?:inicial|definitiva)|hirigintza|"
    r"ordenanza.*vivienda|jendeaurrekoa)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BIZKAIA_CARD = re.compile(
    r'role="heading"[^>]*>(\d{4})</p>\s*<p>([^<]+)</p>.*?'
    r'href="([^"]+_IYBIWPUC_INSTANCE_CadYBlTy6tfn_idInstrumento=\d+[^"]*)"',
    re.S | re.I,
)
RE_BIZKAIA_CODE = re.compile(
    r'<span class="mw-100 text-right">\(([^)]+)\)</span>',
    re.I,
)
RE_PREVIEW = re.compile(
    rf'href="({re.escape(SEDE_BASE)}/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    rf'href="({re.escape(SEDE_BASE)}/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]{4,}")


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


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2035
    ]
    if not years:
        return None
    return f"{max(years)}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _tipo_proyecto(titulo: str) -> str:
    blob = titulo.lower()
    if "plan general" in blob or "pgou" in blob:
        return "PGOU"
    if "plan parcial" in blob or "plan especial" in blob:
        return "plan especial / parcial"
    if "reparcel" in blob:
        return "reparcelación"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if re.search(r"\bue[- ]?[a-z0-9]+", blob):
        return "unidad de ejecución"
    if "modificaci" in blob:
        return "modificación"
    if "informaci" in blob and "pública" in blob:
        return "información pública"
    if "ordenanza" in blob:
        return "ordenanza urbanística"
    return "planeamiento"


class GaldakaoAyuntamientoAdapter(AyuntamientoAdapter):
    """Sede espublico (tablón + catálogo) + Registro PUR Bizkaia (municipio 36); geometría parcial ArcGIS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or PORTAL_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.portal_timeout_s = float(self.config.get("portal_timeout_s", 20))
        self.bizkaia_municipio_id = str(
            self.config.get("bizkaia_municipio_id") or BIZKAIA_MUNICIPIO_ID
        )
        raw_seeds = self.config.get("licencia_seeds")
        if raw_seeds:
            self.licencia_seeds = [(str(s["url"]), str(s["titulo"])) for s in raw_seeds]
        else:
            self.licencia_seeds = list(DEFAULT_LICENCIA_SEEDS)
        raw_doc = self.config.get("documented_proyectos")
        self.documented_proyectos = list(raw_doc) if raw_doc else list(DEFAULT_DOCUMENTED_PROYECTOS)
        self.arcgis_map = str(self.config.get("arcgis_map_url") or ARCGIS_MAP)
        self.planeamiento_layers = tuple(
            int(x) for x in (self.config.get("planeamiento_layer_ids") or PLANEAMIENTO_LAYER_IDS)
        )
        self.geometry_enrich = bool(self.config.get("geometry_enrich", True))
        self.geometry_max_rows = int(self.config.get("geometry_max_rows", 8))
        self.geometry_max_tokens = int(self.config.get("geometry_max_tokens", 3))
        self.geometry_max_layers = int(self.config.get("geometry_max_layers", 4))
        self.centroid_lat = float(self.config.get("centroid_lat", 43.2308))
        self.centroid_lng = float(self.config.get("centroid_lng", -2.8444))
        self._geometry_attempts = 0
        self._ssl_ctx = ssl.create_default_context()
        self._jar = http.cookiejar.CookieJar()
        self._sede_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch_sede(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-galdakao/1.0")},
        )
        with self._sede_opener.open(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch(self, url: str, data: bytes | None = None, *, portal: bool = False) -> str:
        time.sleep(self.delay_s)
        headers = {"User-Agent": self.config.get("user_agent", "poc-bocm-galdakao/1.0")}
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        if portal:
            with urllib.request.urlopen(req, timeout=self.portal_timeout_s) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        return fetch_text(req)

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _bizkaia_form_date(self) -> str:
        try:
            html = self._fetch(BIZKAIA_PUR_URL)
        except (urllib.error.URLError, TimeoutError):
            return str(int(time.time() * 1000))
        m = re.search(
            r'name="_IYBIWPUC_INSTANCE_CadYBlTy6tfn_formDate"[^>]*value="(\d+)"',
            html,
            re.I,
        )
        return m.group(1) if m else str(int(time.time() * 1000))

    def _collect_bizkaia_planeamiento(self) -> list[dict[str, Any]]:
        form_date = self._bizkaia_form_date()
        payload = urllib.parse.urlencode(
            {
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_formDate": form_date,
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_select-municipios": self.bizkaia_municipio_id,
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_select-figuras": "",
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_filtro-texto": "",
                "_IYBIWPUC_INSTANCE_CadYBlTy6tfn_submit": "Buscar",
            }
        ).encode("utf-8")
        try:
            html = self._fetch(BIZKAIA_PUR_URL, data=payload)
        except (urllib.error.URLError, TimeoutError):
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_BIZKAIA_CARD.finditer(html):
            year, titulo, url = m.group(1), unescape(m.group(2).strip()), m.group(3)
            titulo = re.sub(r"\s+", " ", titulo)
            block = m.group(0)
            code_m = RE_BIZKAIA_CODE.search(block)
            codigo = code_m.group(1).strip() if code_m else None
            inst_m = re.search(r"idInstrumento=(\d+)", url)
            inst_id = inst_m.group(1) if inst_m else url
            detail_url = url if url.startswith("http") else f"https://www.bizkaia.eus{url}"
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"bizkaia-pur-{inst_id}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": f"{year}",
                "tipo": _tipo_proyecto(titulo),
                "url": detail_url,
                "source": "ayuntamiento",
                "origen": "bizkaia_pur",
                "instrumento_id": inst_id,
            }
            if codigo:
                rec["codigo_instrumento"] = codigo
            rows.append(rec)
        return rows

    def _parse_board_table(self, html: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            descripcion = _strip_html(cells[4])
            titulo = (title_m.group(1).strip() if title_m else "") or descripcion or doc
            pdf_url = link_m.group(1) if link_m else self.board_url
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": descripcion[:500],
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
                    "url": pdf_url,
                    "pdf_url": pdf_url,
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url in (self.board_url, f"{self.sede_base}/info"):
            try:
                html = self._fetch_sede(url)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for rec in self._parse_board_table(html):
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_catalog_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch_sede(self.dossier_url)
        except (urllib.error.URLError, TimeoutError, OSError):
            return []
        rows: list[dict[str, Any]] = []
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if not re.search(r"(?i)hirigintza|urban|licen|obra", titulo):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia / urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "catalogo_sede",
                }
            )
        return rows

    def _collect_portal_urbanismo_links(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in (URBANISMO_URL, PLANEAMIENTO_URL):
            try:
                html = self._fetch(url, portal=True)
            except (urllib.error.URLError, TimeoutError, OSError):
                continue
            for m in re.finditer(r"(?i)(aprobaci[oó]n[^.<]{10,120}|modificaci[oó]n[^.<]{5,80}|estudio de detalle[^.<]{5,80})", html):
                titulo = _strip_html(m.group(1))
                if not RE_PROYECTO.search(titulo):
                    continue
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "url": url,
                        "fecha": _iso_from_year(titulo),
                        "origen": "portal_web",
                    }
                )
        return rows

    def _geom_tokens(self, text: str, extra: list[str] | None = None) -> list[str]:
        stop = {
            "galdakao",
            "bizkaia",
            "plan",
            "general",
            "modificacion",
            "modificación",
            "aprobacion",
            "aprobación",
            "inicial",
            "definitiva",
            "proyecto",
            "sector",
            "urbano",
            "instrumento",
        }
        seen: set[str] = set()
        out: list[str] = []
        for tok in extra or []:
            key = tok.lower()
            if key not in seen and len(key) >= 3:
                seen.add(key)
                out.append(tok)
        for m in RE_TOKEN.finditer(text or ""):
            w = m.group(0)
            key = w.lower()
            if key in stop or len(key) < 4:
                continue
            if key not in seen:
                seen.add(key)
                out.append(w)
        return out[: self.geometry_max_tokens]

    def _geometry_plausible(self, geom: dict[str, Any]) -> bool:
        centroid = geometry_centroid(geom)
        if not centroid:
            return False
        lat, lon = centroid
        return (
            abs(lat - self.centroid_lat) <= 0.15
            and abs(lon - self.centroid_lng) <= 0.15
        )

    def _fetch_geometry(self, titulo: str, extra_tokens: list[str] | None = None) -> dict[str, Any] | None:
        if not self.geometry_enrich or self._geometry_attempts >= self.geometry_max_rows:
            return None
        self._geometry_attempts += 1
        layer_ids = self.planeamiento_layers[: self.geometry_max_layers]
        for token in self._geom_tokens(titulo, extra_tokens):
            esc = token.replace("'", "''")
            where = f"(DESCRIPCION LIKE '%{esc}%' OR ETIQUETA LIKE '%{esc}%')"
            for layer_id in layer_ids:
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
                except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
                    continue
                feats = data.get("features") if isinstance(data, dict) else None
                if not feats:
                    continue
                geom = feats[0].get("geometry") if isinstance(feats[0], dict) else None
                if not isinstance(geom, dict) or not geom.get("type"):
                    continue
                if not self._geometry_plausible(geom):
                    continue
                return {
                    "geom_geojson": geom,
                    "geometry_source": "portal_visor_arcgis",
                    "geometry_source_url": url,
                    "coord_source": "portal_geometry_centroid",
                }
        return None

    def _attach_geometry(self, rec: dict[str, Any], extra_tokens: list[str] | None = None) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(str(rec.get("titulo") or ""), extra_tokens)
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _board_blob(self, item: dict[str, Any]) -> str:
        return " ".join(
            str(item.get(k) or "")
            for k in ("titulo", "descripcion", "procedimiento", "categoria", "expediente")
        )

    def _to_proyecto(
        self,
        titulo: str,
        url: str,
        fecha: str | None,
        *,
        origen: str,
        geom_tokens: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        if not RE_PROYECTO.search(titulo):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{url}|{titulo}"),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _tipo_proyecto(titulo),
            "url": url,
            "source": "ayuntamiento",
            "origen": origen,
        }
        if extra:
            rec.update(extra)
        self._attach_geometry(rec, geom_tokens)
        return rec

    def _to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        blob = self._board_blob(item)
        if not RE_LICENCIA.search(blob) and not re.search(
            r"(?i)hirigintza", item.get("categoria") or ""
        ):
            return None
        titulo = str(item.get("titulo") or item.get("descripcion") or "")
        url = str(item.get("url") or self.board_url)
        return {
            "id": _stable_id("lic", url),
            "fecha_concesion": item.get("fecha"),
            "tipo": "licencia / urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": url,
            "source": "ayuntamiento",
            "origen": item.get("origen", "tablon_sede"),
            "expte": item.get("expediente") or None,
        }

    def _informative_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo in self.licencia_seeds:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite informativo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "tramites_info",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._informative_licencias() + self._collect_catalog_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_sede"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_licencias(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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

        for rec in self._collect_bizkaia_planeamiento():
            self._attach_geometry(rec, [str(rec.get("codigo_instrumento") or "")])
            add(rec)

        for item in self._collect_board():
            blob = self._board_blob(item)
            add(
                self._to_proyecto(
                    str(item.get("titulo") or ""),
                    str(item.get("url") or self.board_url),
                    item.get("fecha"),
                    origen="tablon_sede",
                    extra={"expediente": item.get("expediente"), "pdf_url": item.get("pdf_url")},
                )
            )

        for item in self._collect_portal_urbanismo_links():
            add(
                self._to_proyecto(
                    item["titulo"],
                    item["url"],
                    item.get("fecha"),
                    origen=item.get("origen", "portal_web"),
                )
            )

        for doc in self.documented_proyectos:
            titulo = str(doc.get("titulo") or "")
            url = str(doc.get("url") or URBANISMO_URL)
            fecha = str(doc.get("fecha") or "") or _iso_from_year(titulo)
            tokens = [str(t) for t in (doc.get("geom_tokens") or [])]
            add(
                self._to_proyecto(
                    titulo,
                    url,
                    fecha or None,
                    origen="documented",
                    geom_tokens=tokens,
                )
            )

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "bizkaia_pur": sum(1 for r in rows if r.get("origen") == "bizkaia_pur"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.parent.mkdir(parents=True, exist_ok=True)
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
