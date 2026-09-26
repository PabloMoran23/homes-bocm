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

BASE = "https://www.tapiadecasariego.es"
SEDE_BASE = "https://tapiadecasariego.sedelectronica.es"
RPGUR_BASE = "https://www54.asturias.es/rpgur/action/publico"
MUNICIPIO = "Tapia de Casariego"
ID_PREFIX = "tapia-de-casariego"

WFS_BASE = "http://visorrpgur.asturias.es:8090/geoserver/E79_ENTIDADES_URBANISTICAS/ows"
WFS_LAYER = "E79_ENTIDADES_URBANISTICAS:n01_AMBITO_INSTRUMENTO_CONSULTAS"

DEFAULT_SEED_PAGES: list[str] = [
    f"{BASE}/index.php?M1=2&M2=74",
    f"{BASE}/index.php?M1=1&M2=32&CT=13",
    f"{BASE}/index.php?M1=1&M2=32&CT=14",
    f"{BASE}/index.php?M1=1&M2=32&CT=13&SC=23",
    f"{BASE}/index.php?M1=1&M2=32&CT=13&SC=17",
    f"{BASE}/index.php?M1=1&M2=32&CT=13&SC=18",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra menor|obra mayor|edificaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgo\b|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle|de implantaci[oó]n)|normas? (?:provisionales|subsidiarias|urban)|"
    r"cat[aá]logo|actuaci[oó]n urban|ordenanza|impacto ambiental|parcel|enajenaci[oó]n)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(padr[oó]n|empleo|subvenci[oó]n|carnaval|pleno|hosteler|surf|deporte|"
    r"madrugador|concurso|bolsa|socorrista|informador tur)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_LINK = re.compile(
    r'href="((?:https?://(?:www\.)?tapiadecasariego\.es)?/images/documentos/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_CATALOG = re.compile(
    r'href="((?:https://tapiadecasariego\.sedelectronica\.es)?/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PREVIEW = re.compile(
    r'href="(https://tapiadecasariego\.sedelectronica\.es/preview-document/[^"]+)"',
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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _page_title(html: str, fallback: str = "") -> str:
    for pat in (r"<h1[^>]*>([^<]+)", r"<title>([^<]+)"):
        m = re.search(pat, html, re.I)
        if m:
            t = unescape(m.group(1).strip())
            t = re.sub(r"\s*[-|»].*Tapia.*$", "", t, flags=re.I).strip()
            if t and len(t) > 3:
                return t[:500]
    return fallback


def _tipo_proyecto(denominacion: str, clasificacion: str = "") -> str:
    blob = f"{denominacion} {clasificacion}".lower()
    if "plan general" in blob or "pgou" in blob or "pgo " in blob:
        return "PGOU"
    if "catálogo" in blob or "catalogo" in blob:
        return "catálogo urbanístico"
    if "plan especial" in blob or "pe " in blob:
        return "plan especial"
    if "plan parcial" in blob:
        return "plan parcial"
    if "estudio de detalle" in blob:
        return "estudio de detalle"
    if "estudio de implantaci" in blob:
        return "estudio de implantación"
    if "impacto ambiental" in blob:
        return "evaluación ambiental"
    if "convenio" in blob:
        return "convenio urbanístico"
    if "modificaci" in blob:
        return "modificación planeamiento"
    if "revisi" in blob:
        return "revisión planeamiento"
    if "enajenaci" in blob and "parcel" in blob:
        return "enajenación parcelas"
    if clasificacion.lower() == "gestión":
        return "gestión urbanística"
    if clasificacion.lower() == "general":
        return "planeamiento general"
    if clasificacion.lower() == "desarrollo":
        return "planeamiento desarrollo"
    return "instrumento urbanístico"


class TapiaDeCasariegoAyuntamientoAdapter(AyuntamientoAdapter):
    """eDise web + espublico sede + RPGUR Asturias; geometría parcial WFS visorrpgur."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.rpgur_base = str(self.config.get("rpgur_base") or RPGUR_BASE).rstrip("/")
        self.rpgur_concejo_id = str(self.config.get("rpgur_concejo_id") or "70")
        self.wfs_url = str(self.config.get("wfs_url") or WFS_BASE)
        self.wfs_layer = str(self.config.get("wfs_layer") or WFS_LAYER)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.max_board_pages = int(self.config.get("max_board_pages", 5))
        self._geom_index: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, data: bytes | None = None, encoding: str = "utf-8") -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-tapia-de-casariego/1.0"),
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

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

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
            "maxFeatures": "50",
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "CQL_FILTER": "Instrumento LIKE '%TAPIA%'",
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

    def _fetch_rpgur_list(self) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        page = 1
        while page <= 10:
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

    def _best_fecha(self, detail: dict[str, str], denominacion: str) -> str | None:
        for key in (
            "publicación BOPA aprobación definitiva",
            "acuerdo aprobación definitiva",
            "publicación BOPA aprobación inicial",
            "acuerdo aprobación inicial",
        ):
            val = detail.get(key, "")
            parsed = _parse_fecha_dmy(val)
            if parsed:
                return parsed
        return _iso_from_year(denominacion)

    def _collect_rpgur_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._fetch_rpgur_list():
            id_inst = item["id"]
            denominacion = item["denominacion"]
            expediente = item["expediente"]
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
                "fecha": self._best_fecha(detail, titulo),
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

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = re.search(
                r'href="(https://tapiadecasariego\.sedelectronica\.es/preview-document/[^"]+)"',
                tr,
                re.I,
            )
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0])
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            rows.append(
                {
                    "titulo": titulo[:500],
                    "doc_label": doc[:500],
                    "expediente": _strip_html(cells[1]),
                    "procedimiento": _strip_html(cells[2]),
                    "categoria": _strip_html(cells[3]),
                    "descripcion": _strip_html(cells[4]),
                    "fecha": _parse_fecha_dmy(_strip_html(cells[5])),
                    "url": link_m.group(1) if link_m else self.board_url,
                    "pdf_url": link_m.group(1) if link_m else None,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for page in range(1, self.max_board_pages + 1):
            url = self.board_url if page == 1 else f"{self.board_url}?page={page}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            items = self._parse_board_table(html, "tablon")
            if not items:
                break
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{self.sede_base}/dossier")
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            href, titulo = m.group(1), unescape(m.group(2).strip())
            url = href if href.startswith("http") else f"{self.sede_base}{href}"
            if url in seen:
                continue
            seen.add(url)
            if not RE_LICENCIA.search(titulo) and not RE_PROYECTO.search(titulo):
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "url": url,
                    "origen": "catalogo_tramites",
                }
            )
        return rows

    def _crawl_web_documents(self) -> list[dict[str, Any]]:
        visited: set[str] = set()
        queue = list(self.seed_pages)
        rows: list[dict[str, Any]] = []
        seen_docs: set[str] = set()

        while queue and len(visited) < 15:
            page_url = queue.pop(0)
            if page_url in visited:
                continue
            visited.add(page_url)
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            page_title = _page_title(html, "")
            if page_title and RE_PROYECTO.search(page_title):
                rec = {
                    "id": _stable_id("proy", page_url),
                    "municipio": MUNICIPIO,
                    "titulo": page_title,
                    "fecha": _iso_from_year(page_title),
                    "tipo": _tipo_proyecto(page_title),
                    "url": page_url,
                    "source": "ayuntamiento",
                    "origen": "web_page",
                }
                rows.append(rec)

            for m in RE_DOC_LINK.finditer(html):
                href = unescape(m.group(1))
                link = self._abs_url(href) if href.startswith("/") else href
                key = link.split("?")[0]
                if key in seen_docs:
                    continue
                seen_docs.add(key)
                title = Path(urllib.parse.unquote(key)).name
                title = re.sub(r"\.pdf$", "", title, flags=re.I).replace("_", " ").strip()
                blob = f"{title} {link} {page_title}"
                if not RE_PROYECTO.search(blob) and "documento" not in title.lower():
                    continue
                rec = {
                    "id": _stable_id("proy", link),
                    "municipio": MUNICIPIO,
                    "titulo": (title if len(title) > 4 else page_title or "documento urbanismo")[:500],
                    "fecha": _iso_from_year(title) or _iso_from_year(page_title),
                    "tipo": _tipo_proyecto(title),
                    "url": page_url,
                    "pdf_url": link,
                    "source": "ayuntamiento",
                    "origen": "web_pdf",
                }
                rows.append(rec)

            for m in re.finditer(
                r'href="((?:https?://(?:www\.)?tapiadecasariego\.es)?/index\.php\?[^"#]+)"',
                html,
                re.I,
            ):
                link = self._abs_url(m.group(1))
                if link not in visited and link not in queue:
                    if "CT=13" in link or "M2=74" in link:
                        queue.append(link)

        return rows

    def _board_to_licencias(self, board: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in board:
            blob = f"{item.get('titulo', '')} {item.get('descripcion', '')} {item.get('categoria', '')}"
            if RE_EXCLUDE.search(blob):
                continue
            if not RE_LICENCIA.search(blob):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", item["url"]),
                    "fecha_concesion": item.get("fecha"),
                    "tipo": "licencia / autorización",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": item.get("titulo") or item.get("descripcion"),
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "expediente": item.get("expediente"),
                    "origen": item.get("origen"),
                }
            )
        return rows

    def _board_to_proyectos(self, board: list[dict[str, Any]]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in board:
            blob = f"{item.get('titulo', '')} {item.get('descripcion', '')} {item.get('categoria', '')}"
            if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                continue
            if not RE_PROYECTO.search(blob):
                continue
            titulo = item.get("titulo") or item.get("descripcion") or "anuncio urbanismo"
            rows.append(
                {
                    "id": _stable_id("proy", item["url"]),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": item.get("fecha"),
                    "tipo": _tipo_proyecto(titulo),
                    "url": item["url"],
                    "pdf_url": item.get("pdf_url"),
                    "source": "ayuntamiento",
                    "expediente": item.get("expediente"),
                    "origen": item.get("origen"),
                }
            )
        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        info_url = f"{BASE}/index.php?M1=2&M2=74"
        info_id = _stable_id("lic", info_url)
        seen.add(info_id)
        rows.append(
            {
                "id": info_id,
                "fecha_concesion": None,
                "tipo": "trámite licencia",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — trámites y documentación",
                "url": info_url,
                "source": "ayuntamiento",
                "nota": "Sin listado público de licencias concedidas; sede espublico",
            }
        )

        board = self._collect_board()
        for rec in self._board_to_licencias(board):
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_tramites():
            if not RE_LICENCIA.search(rec.get("titulo", "")):
                continue
            rec_id = _stable_id("lic", rec["url"])
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
                    "titulo": rec["titulo"],
                    "url": rec["url"],
                    "source": "ayuntamiento",
                    "nota": "Catálogo de trámites sede electrónica",
                }
            )

        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_informativos"}

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

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_rpgur_proyectos():
            add(rec)
        board = self._collect_board()
        for rec in self._board_to_proyectos(board):
            add(rec)
        for rec in self._crawl_web_documents():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "rpgur": sum(1 for r in rows if r.get("origen") == "rpgur"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "web": sum(1 for r in rows if str(r.get("origen", "")).startswith("web")),
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
