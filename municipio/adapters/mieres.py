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

BASE = "https://www.mieres.es"
SEDE_BASE = "https://sedeelectronica.ayto-mieres.es"
TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON"
)
RPGUR_BASE = "https://www54.asturias.es/rpgur/action/publico"
MUNICIPIO = "Mieres"
ID_PREFIX = "mieres"

WFS_BASE = "http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows"
WFS_LAYER = "E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS"
WFS_MUNICIPIO_ID = "33037"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/areas-municipales/urbanismo/",
    f"{BASE}/areas-municipales/urbanismo/plan-general-de-ordenacion-urbana-de-mieres/",
    f"{BASE}/ayuntamiento/servicios-municipales/obras-urbanismo-y-arquitectura/",
    f"{BASE}/ayuntamiento/instancias-enlaces-a-tramites-online/",
]

DEFAULT_LICENCIA_PAGES: list[str] = [
    f"{BASE}/ayuntamiento/instancias-enlaces-a-tramites-online/",
    f"{BASE}/areas-municipales/urbanismo/",
    TABLON_URL,
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|ordenanza|normativa urban|edificaci[oó]n|obra (?:mayor|menor)|"
    r"disciplina urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general|territorial)|pgou|pgo|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de implantaci[oó]n)|normas? (?:provisionales|subsidiarias)|"
    r"cat[aá]logo|actuaci[oó]n urban|ordenanza|disciplina urban|evaluaci[oó]n ambiental)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_EXPEDIENTE = re.compile(r"\b(C-\d{4}/\d{2,4}|\d{4,6}[A-Z]?/\d{4})\b")
RE_DOC_LINK = re.compile(
    r'href="((?:https?://(?:www\.)?mieres\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_RPGUR_ROW = re.compile(
    r'idInstrumento=(\d+).*?<td>\s*([^<]*?)\s*</td>\s*<td>\s*([^<]*?)\s*</td>\s*'
    r'<td>\s*([^<]*?)\s*</td>\s*<td>\s*([^<]*?)\s*</td>\s*<td>\s*([^<]*?)\s*</td>\s*'
    r'<td>\s*([^<]*?)\s*</td>',
    re.S,
)
RE_DETAIL_FIELD = re.compile(
    r'label_consulta2">\s*([^<:]+?)\s*:?\s*</label>.*?'
    r'(?:label_form_consulta_enlace">\s*<a[^>]*>([^<]+)</a>|'
    r'label_form_consulta">\s*([^<]+?)\s*</label>)',
    re.S,
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


def _iso_from_year(text: str) -> str | None:
    years = [
        int(m.group(1))
        for m in RE_YEAR.finditer(text or "")
        if 1980 <= int(m.group(1)) <= 2030
    ]
    if not years:
        return None
    return f"{max(years)}-01-01"


def _fecha_from_pub_date(pub: Any) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub.get("year", 0)),
            int(pub.get("month", 1)),
            int(pub.get("day", 1)),
        ).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (r"<h1[^>]*>([^<]+)", r"<title>([^<]+)"):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|].*Mieres.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3 and "sede electr" not in t.lower():
                return t[:500]
    return fallback


def _tipo_proyecto(denominacion: str, clasificacion: str = "") -> str:
    blob = f"{denominacion} {clasificacion}".lower()
    if "plan territorial especial" in blob or "pte " in blob:
        return "plan territorial especial"
    if "normas" in blob and "provisional" in blob:
        return "normas provisionales"
    if "plan general" in blob or "pgou" in blob or "pgo " in blob:
        return "PGOU"
    if "plan especial" in blob or "pe " in blob:
        return "plan especial"
    if "plan parcial" in blob:
        return "plan parcial"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "estudio de implantaci" in blob:
        return "estudio de implantación"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "catálogo" in blob or "catalogo" in blob:
        return "catálogo urbanístico"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "revisi" in blob:
        return "revisión planeamiento"
    if "disciplina urban" in blob:
        return "disciplina urbanística"
    if clasificacion.lower() == "gestión":
        return "gestión urbanística"
    if clasificacion.lower() == "general":
        return "planeamiento general"
    if clasificacion.lower() == "desarrollo":
        return "planeamiento desarrollo"
    return "instrumento urbanístico"


class MieresAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress mieres.es + sede STA (tablón) + RPGUR Asturias; geometría parcial WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.rpgur_base = str(self.config.get("rpgur_base") or RPGUR_BASE).rstrip("/")
        self.rpgur_concejo_id = str(self.config.get("rpgur_concejo_id") or "37")
        self.wfs_url = str(self.config.get("wfs_url") or WFS_BASE)
        self.wfs_layer = str(self.config.get("wfs_layer") or WFS_LAYER)
        self.wfs_municipio_id = str(self.config.get("wfs_municipio_id") or WFS_MUNICIPIO_ID)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.licencia_pages = [str(u) for u in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)]
        self.max_crawl_pages = int(self.config.get("max_crawl_pages", 20))
        self.max_rpgur_pages = int(self.config.get("max_rpgur_pages", 10))
        self.fetch_rpgur_details = bool(self.config.get("fetch_rpgur_details", False))
        self._geom_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, encoding: str = "utf-8") -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-mieres/1.0"),
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
        if encoding == "iso-8859-1":
            return raw.decode("iso-8859-1", errors="replace")
        return raw.decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, page_url: str = BASE) -> str:
        return urllib.parse.urljoin(page_url, href)

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON"
        )

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
                line = line.strip()
                if line:
                    try:
                        obj = json.loads(line)
                        if isinstance(obj, dict):
                            rows.append(obj)
                    except json.JSONDecodeError:
                        pass
        return rows

    def _load_geom_index(self) -> dict[str, dict[str, Any]]:
        if self._geom_index is not None:
            return self._geom_index
        params = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": self.wfs_layer,
            "maxFeatures": "500",
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "CQL_FILTER": f"id_municipio={self.wfs_municipio_id}",
        }
        url = f"{self.wfs_url}?{urllib.parse.urlencode(params)}"
        index: dict[str, dict[str, Any]] = {}
        try:
            data = self._fetch_json(url)
            for feat in data.get("features") or []:
                if not isinstance(feat, dict):
                    continue
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                inv_id = props.get("Id._Inventario_Registro_Urbanístico")
                if inv_id is None or not isinstance(geom, dict):
                    continue
                key = str(inv_id)
                index[key] = {
                    "geom_geojson": geom,
                    "geometry_source": "portal_wfs",
                    "geometry_source_url": url,
                    "coord_source": "portal_geometry_centroid",
                }
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
            pass
        self._geom_index = index
        return index

    def _attach_geometry(self, rec: dict[str, Any], id_instrumento: str | int | None = None) -> None:
        if record_geometry(rec):
            return
        if id_instrumento is None:
            return
        geom = self._load_geom_index().get(str(id_instrumento))
        if geom:
            rec.update(geom)
            centroid = geometry_centroid(geom["geom_geojson"])
            if centroid:
                rec["lat"], rec["lon"] = centroid

    @staticmethod
    def _extract_tablon_dataset(html: str) -> list[dict[str, Any]]:
        needle = "var dataset_PTS2_TABLON = "
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

    def _fetch_rpgur_list(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        page = 1
        while page <= self.max_rpgur_pages:
            params = {
                "method": "listPublico",
                "idConcejo": self.rpgur_concejo_id,
                "estado": "V",
                "primeraVez": "false",
                "page": str(page),
            }
            url = f"{self.rpgur_base}/busquedaConsulta?{urllib.parse.urlencode(params)}"
            try:
                html = self._fetch(url, encoding="iso-8859-1")
            except urllib.error.URLError:
                break
            page_rows = 0
            for m in RE_RPGUR_ROW.finditer(html):
                page_rows += 1
                rows.append(
                    {
                        "id": m.group(1),
                        "ambito": _strip_html(m.group(2)),
                        "concejo": _strip_html(m.group(3)),
                        "clasificacion": _strip_html(m.group(4)),
                        "denominacion": _strip_html(m.group(5)),
                        "expediente": _strip_html(m.group(6)),
                        "estado": _strip_html(m.group(7)),
                    }
                )
            if page_rows == 0 or f"page={page + 1}" not in html:
                break
            page += 1
        return rows

    def _fetch_rpgur_detail(self, id_instrumento: str) -> dict[str, str]:
        url = (
            f"{self.rpgur_base}/gestionConsulta"
            f"?method=retrieve&idInstrumento={urllib.parse.quote(id_instrumento)}"
        )
        fields: dict[str, str] = {}
        try:
            html = self._fetch(url, encoding="iso-8859-1")
        except urllib.error.URLError:
            return fields
        for m in RE_DETAIL_FIELD.finditer(html):
            label = _strip_html(m.group(1)).rstrip(":").strip()
            value = _strip_html(m.group(2) or m.group(3) or "").strip()
            if label and value:
                fields[label] = value
        return fields

    def _best_fecha(self, detail: dict[str, str], denominacion: str, expediente: str = "") -> str | None:
        for key in (
            "publicación BOPA aprobación definitiva",
            "acuerdo aprobación definitiva",
            "publicación BOPA aprobación inicial",
            "acuerdo aprobación inicial",
        ):
            parsed = _parse_fecha_dmy(detail.get(key, ""))
            if parsed:
                return parsed
        m = RE_EXPEDIENTE.search(expediente)
        if m:
            year = m.group(0).split("/")[-1]
            if year.isdigit() and len(year) == 4:
                return f"{year}-01-01"
        return _iso_from_year(denominacion)

    def _collect_rpgur_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._fetch_rpgur_list():
            id_inst = item["id"]
            denominacion = item["denominacion"]
            expediente = item["expediente"]
            detail: dict[str, str] = {}
            if self.fetch_rpgur_details:
                detail = self._fetch_rpgur_detail(id_inst)
            url = (
                f"{self.rpgur_base}/gestionConsulta"
                f"?method=retrieve&idInstrumento={id_inst}"
            )
            titulo = detail.get("Denominación", denominacion) or denominacion
            rec = {
                "id": _stable_id("proy", f"rpgur:{id_inst}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": self._best_fecha(detail, titulo, expediente),
                "tipo": _tipo_proyecto(titulo, item.get("clasificacion", "")),
                "url": url,
                "source": "ayuntamiento",
                "origen": "rpgur",
                "expediente": expediente or detail.get("Expediente"),
                "estado": item.get("estado") or detail.get("Estado"),
                "clasificacion": item.get("clasificacion"),
                "id_instrumento": id_inst,
            }
            self._attach_geometry(rec, id_inst)
            rows.append(rec)
        return rows

    def _collect_tablon_items(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(TABLON_URL)
        except urllib.error.URLError:
            return rows
        for item in self._extract_tablon_dataset(html):
            dboid = str(item.get("dboid") or "")
            titulo = _strip_html(
                str(item.get("descriptionProc") or item.get("externString") or "")
            )
            if not titulo or not dboid:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "dboid": dboid,
                    "extern": str(item.get("externString") or ""),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _crawl_portal_documents(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        seen_docs: set[str] = set()

        while queue and len(visited) < self.max_crawl_pages:
            page_url = queue.pop(0).rstrip("/")
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = _page_title(html, "")
            if page_title and RE_PROYECTO.search(page_title):
                rows.append(
                    {
                        "id": _stable_id("proy", page_url),
                        "municipio": MUNICIPIO,
                        "titulo": page_title,
                        "fecha": _iso_from_year(page_title),
                        "tipo": _tipo_proyecto(page_title),
                        "url": page_url,
                        "source": "ayuntamiento",
                        "origen": "portal_page",
                    }
                )

            for m in RE_DOC_LINK.finditer(html):
                href = unescape(m.group(1))
                link = self._abs_url(href, page_url) if href.startswith(("/", ".")) else href
                key = link.split("?")[0]
                if key in seen_docs:
                    continue
                seen_docs.add(key)
                title = Path(urllib.parse.unquote(key)).name
                title = re.sub(r"\.pdf$", "", title, flags=re.I).replace("-", " ").strip()
                blob = f"{title} {link} {page_title}"
                if not RE_PROYECTO.search(blob):
                    continue
                rows.append(
                    {
                        "id": _stable_id("proy", link),
                        "municipio": MUNICIPIO,
                        "titulo": (title if len(title) > 4 else page_title or "documento urbanismo")[:500],
                        "fecha": _iso_from_year(title) or _iso_from_year(page_title),
                        "tipo": _tipo_proyecto(title),
                        "url": page_url,
                        "pdf_url": link,
                        "source": "ayuntamiento",
                        "origen": "portal_document",
                    }
                )

            for m in re.finditer(r'href="(https://www\.mieres\.es/[^"#?]+)"', html, re.I):
                link = m.group(1).rstrip("/")
                if link not in visited and link not in queue and RE_PROYECTO.search(link):
                    queue.append(link)

        return rows

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
            return None
        if RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
            return None
        return {
            "id": _stable_id("proy", row.get("url") or titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _tipo_proyecto(titulo),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row.get("titulo") or ""
        if not RE_LICENCIA.search(titulo):
            return None
        return {
            "id": _stable_id("lic", row.get("url") or titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": "anuncio tablón",
            "distrito": row.get("extern") or None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in self._collect_tablon_items():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        info_pages = [
            (TABLON_URL, "Tablón de anuncios — sede electrónica"),
            (
                f"{BASE}/ayuntamiento/instancias-enlaces-a-tramites-online/",
                "Trámites urbanismo (licencias, DR, certificación)",
            ),
            (
                f"{BASE}/areas-municipales/urbanismo/",
                "Urbanismo, Obras y Vivienda",
            ),
        ]
        for page_url, titulo in info_pages:
            rec_id = _stable_id("lic", page_url)
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
                    "titulo": titulo,
                    "url": page_url,
                    "source": "ayuntamiento",
                    "nota": "Sin listado público de concesiones; página informativa o tablón",
                }
            )

        for page_url in self.licencia_pages:
            if page_url == TABLON_URL:
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = _page_title(html, "")
            if page_title and RE_LICENCIA.search(page_title):
                rec_id = _stable_id("lic", page_url)
                if rec_id not in seen:
                    seen.add(rec_id)
                    rows.append(
                        {
                            "id": rec_id,
                            "fecha_concesion": None,
                            "tipo": "trámite licencia",
                            "distrito": None,
                            "lat": None,
                            "lon": None,
                            "titulo": page_title[:500],
                            "url": page_url,
                            "source": "ayuntamiento",
                            "nota": "Página informativa de trámites",
                        }
                    )

            for m in RE_DOC_LINK.finditer(html):
                href = unescape(m.group(1))
                link = self._abs_url(href, page_url) if href.startswith(("/", ".")) else href
                title = Path(urllib.parse.unquote(link.split("?")[0])).name
                title = re.sub(r"\.pdf$", "", title, flags=re.I).replace("-", " ").strip()
                if not RE_LICENCIA.search(f"{title} {link}"):
                    continue
                key = link.split("?")[0]
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "id": _stable_id("lic", link),
                        "fecha_concesion": _iso_from_year(title),
                        "tipo": "normativa licencias",
                        "distrito": None,
                        "lat": None,
                        "lon": None,
                        "titulo": title[:500],
                        "url": page_url,
                        "pdf_url": link,
                        "source": "ayuntamiento",
                        "nota": "Documento normativo; no concesión publicada",
                    }
                )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_tablon"}

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
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": added,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_rpgur_proyectos():
            add(rec)
        for item in self._collect_tablon_items():
            add(self._tablon_to_proyecto(item))
        for rec in self._crawl_portal_documents():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "rpgur": sum(1 for r in rows if r.get("origen") == "rpgur"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sta"),
            "portal": sum(1 for r in rows if str(r.get("origen", "")).startswith("portal")),
            "with_geometry": with_geom,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_proyectos(out_jsonl)
        after = result["rows"]
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
