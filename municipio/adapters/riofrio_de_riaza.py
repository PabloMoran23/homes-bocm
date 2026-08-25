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
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.riofrioderiaza.es"
SEDE_BASE = "https://riofrioderiaza.sedelectronica.es"
PLAI_BASE = "https://servicios.jcyl.es/PlanPublica"
MUNICIPIO = "Riofrío de Riaza"
ID_PREFIX = "riofrio-de-riaza"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/wfs"
PLAI_MUNICIPIO = 172
PLAI_PROVINCIA = 40

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/actualdiad-municipal",
    f"{WEB_BASE}/publicaciones-oficiales",
    f"{WEB_BASE}/normativa-municipal",
    f"{WEB_BASE}/vivienda",
    f"{WEB_BASE}/area-de-descargas",
]

RE_LIFERAY_DOC = re.compile(
    r'<a href="(/documents/[^"]+)" title="([^"]+)" class="document file-pdf"',
    re.I,
)
RE_LIFERAY_NEWS = re.compile(
    r'href="(https://www\.riofrioderiaza\.es/actualdiad-municipal/-/asset_publisher/[^"]+)"'
    r'[^>]*title="([^"]+)"',
    re.I,
)
RE_PREVIEW = re.compile(
    r'href="(https://riofrioderiaza\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://riofrioderiaza\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra (?:mayor|menor)|"
    r"primera ocupaci[oó]n|primera utilizaci[oó]n|licencia urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva|provisional)|reparcel|sector|"
    r"edicto|actuaci[oó]n urban|reurbaniz|urbanizaci[oó]n|suelo urban|suelo urbanizable|"
    r"ficha urban|alineaci[oó]n|zonificaci[oó]n|memoria|plano|ampliaci[oó]n urban|"
    r"alumbrado|bocyl|instrumento|ua-|peri|sin planeamiento)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(decreto|real decreto|ley \d|patrimonio hist[oó]rico|ministerio de educaci[oó]n|"
    r"glosario|caratula$|indice normativa$|esquema$|capitulo \d|"
    r"proceso selectivo|empleo|fiestas|carnaval|turismo|gastronom|cineg[eé]tico|"
    r"listas electorales|juez de paz)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR_CODE = re.compile(
    r"(?i)\b("
    r"UA[-\s]?\d+[A-Z]?|"
    r"SECTOR\s+\d+(?:_[A-Za-z ]+)?|"
    r"SU[- ]?NC\.?\s*(?:N[ºo°]\.?\s*)?\d+"
    r")\b",
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


def _parse_fecha_iso(text: str) -> str | None:
    m = RE_FECHA_ISO.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    iso = _parse_fecha_iso(text)
    if iso:
        return iso
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "sin planeamiento" in n:
        return "sin planeamiento general"
    if "nnss" in n or "normas urban" in n:
        return "normas urbanísticas"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n and "p" in n:
        return "información pública"
    if "memoria" in n:
        return "memoria planeamiento"
    if "plano" in n or "zonificaci" in n or "alineaci" in n:
        return "planos planeamiento"
    if "ficha" in n:
        return "ficha actuación"
    if "sector" in n or re.search(r"ua-\d", n):
        return "sector"
    if "vivienda" in n:
        return "vivienda"
    return "urbanismo"


class RiofrioDeRiazaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay Segovia8 + sede espublico + PLAI JCYL + IDECyL WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.plai_municipio = int(self.config.get("plai_municipio") or PLAI_MUNICIPIO)
        self.plai_provincia = int(self.config.get("plai_provincia") or PLAI_PROVINCIA)
        self.plai_max_pages = int(self.config.get("plai_max_pages", 4))
        self.plai_page_size = int(self.config.get("plai_page_size", 15))
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or MUNICIPIO)
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

    def _fetch(self, url: str, *, sede: bool = False, timeout: int | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-riofrio-de-riaza/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=timeout or (90 if sede else 60)) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_web(self, path: str) -> str:
        if path.startswith("http"):
            return path
        return f"{self.web_base}{path if path.startswith('/') else '/' + path}"

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "120",
                "CQL_FILTER": f"n_mun = '{self.wfs_municipio.replace(chr(39), chr(39) + chr(39))}'",
            }
        )
        return f"{self.wfs_base}?{params}"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        rows: list[dict[str, Any]] = []
        for layer, default_tipo in WFS_LAYERS:
            url = self._wfs_query_url(layer)
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                titulo = _strip_html(str(props.get("n_titulo") or ""))
                if not titulo:
                    sector = str(props.get("n_sector") or "").strip()
                    num = str(props.get("n_num_sect") or "").strip()
                    titulo = f"{sector} ({num})" if sector else num
                if not titulo:
                    titulo = str(props.get("c_id_sect") or props.get("c_plan") or layer)
                instrum = str(props.get("n_instrum") or props.get("c_instrum") or "")
                blob = f"{titulo} {instrum}"
                fecha = _parse_fecha_iso(str(props.get("f_bocyl") or "")) or _parse_fecha_iso(
                    str(props.get("f_aprob") or "")
                )
                doc_url = str(props.get("url_doc_info") or "").strip() or url
                key = str(props.get("c_id_sect") or props.get("c_plan") or props.get("fid") or titulo)
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", f"wfs:{layer}:{key}"),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(blob) if blob.strip() else default_tipo,
                    "url": doc_url,
                    "source": "ayuntamiento",
                    "origen": "idecyl_wfs",
                    "wfs_layer": layer,
                    "sector_id": props.get("c_id_sect"),
                    "instrumento": instrum or None,
                }
                if isinstance(geom, dict) and geom.get("type"):
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
        self._wfs_cache = rows
        return rows

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "").lower()
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            if titulo and wfs_title and (titulo in wfs_title or wfs_title in titulo):
                self._copy_geometry(rec, wfs_rec)
                return
        for code in RE_SECTOR_CODE.findall(titulo):
            for wfs_rec in self._collect_wfs_proyectos():
                wfs_blob = f"{wfs_rec.get('titulo', '')} {wfs_rec.get('sector_id', '')}".lower()
                if code.lower() in wfs_blob:
                    self._copy_geometry(rec, wfs_rec)
                    return

    @staticmethod
    def _copy_geometry(target: dict[str, Any], source: dict[str, Any]) -> None:
        for key in (
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
        ):
            if source.get(key) is not None:
                target[key] = source[key]

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            link_m = RE_PREVIEW.search(tr)
            if not link_m:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            titulo = unescape(title_m.group(1).strip()) if title_m else link_m.group(1)
            fecha = _parse_fecha_dmy(_strip_html(cells[5])) if len(cells) > 5 else None
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": link_m.group(1),
                    "pdf_url": link_m.group(1),
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (self.info_url, "info_tablon")):
            try:
                html = self._fetch(url, sede=True, timeout=45)
            except urllib.error.URLError:
                continue
            for rec in self._parse_board_table(html, origen):
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url, sede=True, timeout=45)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
            if not url.startswith("http"):
                url = f"{self.sede_base}{url}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append({"titulo": titulo[:500], "url": url, "origen": "catalogo_tramites"})
        return rows

    def _plai_page_url(self, offset: int, *, info_publica: bool = False) -> str:
        action = "searchVPubDocMuniPlai.do" if info_publica else "searchVPubDocMuniPlau.do"
        params = {
            "pager.size": str(self.plai_page_size),
            "pager.reload": "no",
            "municipio": f"{self.plai_municipio:03d}",
            "provincia": str(self.plai_provincia),
            "urlResults": action,
            "pager.offset": str(offset),
        }
        if info_publica:
            params["bInfoPublica"] = "S"
        else:
            params["bInfoPublica"] = "N"
        return f"{PLAI_BASE}/{action}?{urllib.parse.urlencode(params)}"

    @staticmethod
    def _parse_plai_rows(html: str) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c]
            if len(cells) < 5 or cells[0] in {"Libro", "Tipo"}:
                continue
            titulo = cells[4] if len(cells) > 4 else cells[-1]
            if not titulo or re.fullmatch(r"\d{1,2}/\d{1,2}/\d{4}", titulo):
                continue
            fecha_pub = cells[2]
            doc_m = re.search(r"doOpen\('(\d+)'", tr) or re.search(r"doOpenDocumento\((\d+)\)", tr)
            doc_id = doc_m.group(1) if doc_m else None
            if doc_id:
                url = f"{PLAI_BASE}/openDocumento.do?cDocId={doc_id}"
            else:
                url = (
                    f"{PLAI_BASE}/searchVPubDocMuniPlau.do?"
                    f"provincia={PLAI_PROVINCIA}&municipio={PLAI_MUNICIPIO:03d}"
                )
            rows.append(
                {
                    "title": titulo,
                    "url": url,
                    "fecha": fecha_pub,
                    "instrumento": cells[1] if len(cells) > 1 else "",
                }
            )
        return rows

    def _collect_plai(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for info_publica in (False, True):
            for page in range(self.plai_max_pages):
                offset = page * self.plai_page_size
                try:
                    html = self._fetch(self._plai_page_url(offset, info_publica=info_publica))
                except urllib.error.URLError:
                    break
                parsed = self._parse_plai_rows(html)
                if not parsed:
                    break
                for item in parsed:
                    key = item["url"] + item["title"]
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "titulo": item["title"][:500],
                            "fecha": _parse_fecha_dmy(item.get("fecha") or ""),
                            "url": item["url"],
                            "instrumento": item.get("instrumento") or "",
                            "origen": "plai_jcyl",
                        }
                    )
                if len(parsed) < self.plai_page_size:
                    break
        return rows

    def _collect_liferay_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            folder = ""
            for m in re.finditer(
                r"<i class='fas fa-folder'></i>\s*([^<]+)</a>|"
                r'<a href="(/documents/[^"]+)" title="([^"]+)" class="document file-pdf"',
                html,
                re.I,
            ):
                if m.lastindex == 1 and m.group(1) and not m.group(1).startswith("/"):
                    folder = _strip_html(m.group(1))
                    continue
                if m.lastindex >= 2 and m.group(1) and m.group(1).startswith("/"):
                    path = m.group(1)
                    title = unescape(m.group(2)).strip()
                    if path in seen:
                        continue
                    seen.add(path)
                    pdf_url = self._abs_web(path)
                    rows.append(
                        {
                            "titulo": title[:500],
                            "url": page_url,
                            "pdf_url": pdf_url,
                            "fecha": _fecha_from_blob(f"{title} {folder}"),
                            "origen": "liferay_pdf",
                            "folder": folder,
                        }
                    )
        return rows

    def _collect_liferay_news(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            if "actualdiad" not in page_url:
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_LIFERAY_NEWS.finditer(html):
                url = unescape(m.group(1).replace("&amp;", "&"))
                title = _strip_html(m.group(2))
                if url in seen:
                    continue
                seen.add(url)
                rows.append(
                    {
                        "titulo": title[:500],
                        "url": url,
                        "fecha": None,
                        "origen": "liferay_news",
                    }
                )
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('folder', '')} {row.get('instrumento', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or row.get("pdf_url") or self.web_base,
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, tipo in (
            (f"{self.web_base}/vivienda", "vivienda — información y trámites"),
            (f"{self.sede_base}/dossier", "sede electrónica — catálogo de trámites"),
            (f"{self.sede_base}/board", "tablón de anuncios — sede electrónica"),
        ):
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": tipo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite o publicación",
                    "origen": "liferay_tramite",
                }
            )
        for item in self._collect_tramites():
            if not RE_LICENCIA.search(item["titulo"]):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", item["url"]),
                    "fecha_concesion": None,
                    "tipo": "trámite sede",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item["titulo"],
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "nota": "Trámite informativo en catálogo sede",
                    "origen": "catalogo_tramites",
                }
            )
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_LIFERAY_DOC.finditer(html):
                title = unescape(m.group(2)).strip()
                if not RE_LICENCIA.search(title):
                    continue
                pdf_url = self._abs_web(m.group(1))
                rows.append(
                    {
                        "id": _stable_id("lic", pdf_url),
                        "fecha_concesion": None,
                        "tipo": "formulario licencia",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": pdf_url,
                        "source": "ayuntamiento",
                        "nota": "Formulario PDF; no concesión publicada",
                        "origen": "liferay_pdf",
                        "pdf_url": pdf_url,
                    }
                )
        return rows

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
        for rec in self._collect_licencia_tramites():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tramites": sum(1 for r in rows if r.get("origen") == "liferay_tramite"),
            "catalogo": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_tramites():
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
        for wfs_rec in self._collect_wfs_proyectos():
            if wfs_rec["id"] not in seen:
                seen.add(wfs_rec["id"])
                rows.append(wfs_rec)
        for item in self._collect_board():
            rec = self._row_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_plai():
            rec = self._row_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_liferay_documents():
            rec = self._row_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_liferay_news():
            rec = self._row_to_proyecto(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "plai": sum(1 for r in rows if r.get("origen") == "plai_jcyl"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for wfs_rec in self._collect_wfs_proyectos():
            existing[wfs_rec["id"]] = wfs_rec
        for item in self._collect_board():
            rec = self._row_to_proyecto(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_plai():
            rec = self._row_to_proyecto(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_liferay_documents():
            rec = self._row_to_proyecto(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_liferay_news():
            rec = self._row_to_proyecto(item)
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
