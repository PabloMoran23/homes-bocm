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

WP_BASE = "https://aytonavaluenga.es"
SEDE_BASE = "https://navaluenga.sedelectronica.es"
PLAU_BASE = "https://servicios.jcyl.es/PlanPublica"
WFS_BASE = "https://idecyl.jcyl.es/geoserver/urbanismo/ows"
MUNICIPIO = "Navaluenga"
ID_PREFIX = "navaluenga"
PLAU_PROVINCIA = 5
PLAU_MUNICIPIO = 163

WFS_LAYERS: tuple[tuple[str, str], ...] = (
    ("urbanismo:plau_cyl_instrumentos_ambito", "instrumento"),
    ("urbanismo:plau_cyl_planes_parciales", "plan parcial"),
    ("urbanismo:plau_cyl_sectores", "sector"),
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/bandos-y-pregones/",
    f"{WP_BASE}/ordenanzas-y-reglamentos/",
    f"{SEDE_BASE}/board",
    f"{PLAU_BASE}/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=163",
]

RE_PREVIEW = re.compile(
    r'href="(https://navaluenga\.sedelectronica\.es/preview-document/[^"]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|limpieza de solar)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio urban|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva|provisional)|reparcel|sector|"
    r"edicto|bando|actuaci[oó]n urban|normas urban|instrumento|num\b|bocyl|bopa|"
    r"ordenanza.*estacionamiento|valdebruna)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(pleno|convocatoria|empleo|subvenci[oó]n deportiv|cert\.|ordenanza fiscal|"
    r"perfil contratante|iae|cobranza|regantes|comunidad de regantes)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_DOC_HREF = re.compile(
    r'href=["\']((?:https?://[^"\']+|/[^"\']+))["\']',
    re.I,
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


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "plan parcial" in n:
        return "plan parcial"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "normas urban" in n or " num" in n or n.strip() == "num":
        return "normas urbanísticas"
    if "informaci" in n:
        return "información pública"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "sector" in n:
        return "sector"
    if "ordenanza" in n:
        return "ordenanza municipal"
    return "planeamiento"


class NavaluengaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress Astra + sede espublico + PlanPublica JCyL + IDECyL WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.plau_provincia = int(self.config.get("plau_provincia") or PLAU_PROVINCIA)
        self.plau_municipio = int(self.config.get("plau_municipio") or PLAU_MUNICIPIO)
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

    def _fetch(self, url: str, *, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-navaluenga/1.0")},
        )
        opener = self._opener if sede else urllib.request.build_opener()
        with opener.open(req, timeout=90 if sede else 60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-navaluenga/1.0")},
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_wp(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.wp_base}/", href)

    def _wfs_query_url(self, layer: str) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": layer,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "200",
                "CQL_FILTER": f"n_mun = '{self.wfs_municipio}'",
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
                return
        for token in re.split(r"[\s,/()-]+", titulo):
            if len(token) < 5:
                continue
            for wfs_rec in self._collect_wfs_proyectos():
                wfs_title = str(wfs_rec.get("titulo") or "").lower()
                if token in wfs_title:
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
                    return

    def _plau_print_url(self) -> str:
        params = urllib.parse.urlencode(
            {
                "provincia": f"{self.plau_provincia:02d}",
                "municipio": f"{self.plau_municipio:03d}",
                "bInfoPublica": "N",
            }
        )
        return f"{PLAU_BASE}/searchVPubDocMuniPlauPrint.do?{params}"

    def _parse_plau_rows(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S | re.I):
            doc_m = re.search(r"doOpen\('(\d+)',\s*'([^']+)'\)", tr)
            if not doc_m:
                doc_m = re.search(r"doOpen\('(\d+)'\)", tr)
                if not doc_m:
                    continue
                doc_id, codigo = doc_m.group(1), doc_m.group(1)
            else:
                doc_id, codigo = doc_m.group(1), doc_m.group(2)
            cells = [
                _strip_html(c)
                for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S | re.I)
            ]
            cells = [c for c in cells if c]
            titulo = cells[4] if len(cells) > 4 else (cells[-1] if cells else "")
            if not titulo:
                continue
            fecha = _parse_fecha_dmy(cells[2] if len(cells) > 2 else "")
            instrumento = cells[1] if len(cells) > 1 else ""
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "instrumento": instrumento,
                    "codigo": codigo,
                    "url": f"{PLAU_BASE}/openDocumento.do?cDocId={doc_id}",
                    "origen": "plau_jcyl",
                }
            )
        return rows

    def _collect_plau(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self._plau_print_url())
        except urllib.error.URLError:
            return []
        return self._parse_plau_rows(html)

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r"<tbody[^>]*>(.*?)</tbody>", html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 2:
                continue
            link_m = RE_PREVIEW.search(tr)
            title_m = re.search(r'title="([^"]*)"', tr, re.I)
            doc = _strip_html(cells[0]) if cells else ""
            titulo = (title_m.group(1).strip() if title_m else "") or doc
            url = link_m.group(1) if link_m else self.board_url
            fecha = None
            if len(cells) >= 6:
                fecha = _parse_fecha_dmy(_strip_html(cells[5]))
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": _strip_html(cells[1]) if len(cells) > 1 else "",
                    "procedimiento": _strip_html(cells[2]) if len(cells) > 2 else "",
                    "categoria": _strip_html(cells[3]) if len(cells) > 3 else "",
                    "descripcion": _strip_html(cells[4]) if len(cells) > 4 else "",
                    "fecha": fecha,
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, sede=True)
        except urllib.error.URLError:
            return []
        return self._parse_board_table(html, "tablon")

    def _collect_seed_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            if "sedelectronica" in page_url or "PlanPublica" in page_url:
                continue
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            m = re.search(r"<title>([^<]+)", html, re.I)
            if m:
                page_title = _strip_html(m.group(1))
            for href_m in RE_DOC_HREF.finditer(html):
                href = href_m.group(1)
                if not any(
                    ext in href.lower()
                    for ext in (".pdf", "dropbox.com", "diputacionavila.es/bops")
                ):
                    continue
                doc_url = self._abs_wp(href) if href.startswith("/") else href
                if doc_url in seen:
                    continue
                seen.add(doc_url)
                ctx = html[max(0, href_m.start() - 250) : href_m.end() + 80]
                link_text = ""
                text_m = re.search(r">([^<]{3,160})</a>", ctx)
                if text_m:
                    link_text = _strip_html(text_m.group(1))
                if not link_text:
                    link_text = unescape(urllib.parse.unquote(Path(doc_url).name))
                blob = f"{page_title} {link_text} {doc_url}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob) and "urban" not in page_url.lower():
                    if "normas" not in blob.lower() and "plano" not in blob.lower():
                        continue
                rows.append(
                    {
                        "titulo": link_text[:500],
                        "url": page_url,
                        "pdf_url": doc_url,
                        "fecha": _fecha_from_blob(blob),
                        "origen": "wp_seed",
                        "page_title": page_title,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages = [
            (f"{self.wp_base}/bandos-y-pregones/", "ordenanzas y normativa urbanística"),
            (self.board_url, "tablón de anuncios — sede electrónica"),
            (f"{self.sede_base}/dossier", "trámites — sede electrónica"),
            (
                f"{PLAU_BASE}/searchVPubDocMuniPlau.do?"
                f"bInfoPublica=N&provincia=05&municipio=163",
                "archivo planeamiento urbanístico (Junta CYL)",
            ),
        ]
        rows: list[dict[str, Any]] = []
        for url, tipo in pages:
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
                    "nota": "Página informativa; no hay registro público de concesiones de licencia",
                    "origen": "wp_tramite",
                }
            )
        return rows

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "expte": row.get("expediente") or None,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            **({"pdf_url": row["pdf_url"]} if row.get("pdf_url") else {}),
        }

    def _plau_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = f"{row['titulo']} {row.get('instrumento', '')}"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("codigo") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "instrumento": row.get("instrumento"),
            "codigo_plau": row.get("codigo"),
        }
        self._enrich_geometry(rec)
        return rec

    def _seed_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = f"{row.get('titulo', '')} {row.get('pdf_url', '')} {row.get('page_title', '')}"
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or row.get("pdf_url") or f"{self.wp_base}/bandos-y-pregones/",
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(str(row.get(k) or "") for k in ("titulo", "procedimiento", "categoria", "descripcion"))
        if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() in ("urbanismo", "ordenanzas y reglamentos"):
            pass
        elif not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _wp_normativa_proyecto(self) -> dict[str, Any]:
        url = f"{self.wp_base}/bandos-y-pregones/"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": "Normas urbanísticas municipales de Navaluenga",
            "fecha": "2013-06-06",
            "tipo": "normas urbanísticas",
            "url": url,
            "source": "ayuntamiento",
            "origen": "wp_page",
        }
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

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for rec in self._collect_licencia_info_pages():
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "tramites": sum(1 for r in rows if r.get("origen") == "wp_tramite"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats["rows"]
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

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for item in self._collect_plau():
            add(self._plau_to_proyecto(item))
        add(self._wp_normativa_proyecto())
        for item in self._collect_seed_docs():
            add(self._seed_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "idecyl_wfs": sum(1 for r in rows if r.get("origen") == "idecyl_wfs"),
            "plau_jcyl": sum(1 for r in rows if r.get("origen") == "plau_jcyl"),
            "wp_page": sum(1 for r in rows if r.get("origen") == "wp_page"),
            "wp_seed": sum(1 for r in rows if r.get("origen") == "wp_seed"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats["rows"]
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
