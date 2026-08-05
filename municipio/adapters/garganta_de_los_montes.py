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
from municipio.geometry import geometry_centroid
from municipio.gis.sitcm import resolve_ambito_geometry

WP_BASE = "https://www.gargantadelosmontes.org"
SEDE_BASE = "https://gargantadelosmontes.sedelectronica.es"
MUNICIPIO = "Garganta de los Montes"
ID_PREFIX = "garganta-de-los-montes"
WFS_MUNICIPIO = "GARGANTA DE LOS MONTES"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WP_BASE}/ordenanzas-reglamentos/",
    f"{WP_BASE}/impresos/",
    f"{WP_BASE}/documento-ambiental-estrategico-de-los-gargantales/",
    f"{WP_BASE}/informacion-publica/",
    f"{WP_BASE}/transparencia/",
    f"{WP_BASE}/recuperando-el-casco-historico-de-garganta-proximamente-comenzaran-las-obras-en/",
    f"{WP_BASE}/haciendo-pueblo-transformamos-nuestro-casco-historico-arrancan-las-obras/",
]

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|de actividad|de apertura|de obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"licencias urban|ocupaci[oó]n de v[ií]a)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|ponp|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"redacci[oó]n del plan|normas subsidiarias|nnss|subasta|cat[aá]logo|"
    r"gargantales|urbanizaci[oó]n|casco hist[oó]rico|ambiental estrat[eé]gico|"
    r"t[ií]tulos habilitantes|ordenanza.*urban)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(empleo p[uú]blico|oposici[oó]n|proceso selectivo|iae|padr[oó]n fiscal|"
    r"campaña limpieza|juegos infantiles|parques municipales|desbroce|quema|"
    r"autobuses interurbanos|colonia felina|barbacoa|fiestas|carnaval|"
    r"campamento urbano|mundial|copa del mundo|pantalla gigante|cine por favor)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://gargantadelosmontes\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://(?:www\.)?gargantadelosmontes\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)

IMPRESOS_LICENCIA_URLS: list[tuple[str, str]] = [
    (
        f"{WP_BASE}/wp-content/uploads/2024/02/E-5.SOLICITUD-DE-LICENCIA-DE-OBRA-MAYOR.pdf",
        "Solicitud de licencia de obra mayor",
    ),
    (
        f"{WP_BASE}/wp-content/uploads/2024/02/E-4.SOLICITUD-DECLARACION-RESPONSABLEMENOR.pdf",
        "Solicitud declaración responsable / obra menor",
    ),
    (
        f"{WP_BASE}/wp-content/uploads/2024/02/E-7.-OCUPACION-DE-VIA-PUBLICA.pdf",
        "Solicitud ocupación de vía pública",
    ),
]


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _planeamiento_tipo(name: str) -> str:
    n = name.lower()
    if "ambiental estrat" in n or "dae" in n:
        return "documento ambiental estratégico"
    if "memoria" in n:
        return "memoria planeamiento"
    if "planos" in n or "plano" in n or n.startswith("p-"):
        return "planos planeamiento"
    if "titulos habilitantes" in n or "habilitantes" in n:
        return "ordenanza urbanística"
    if "licencias urban" in n:
        return "ordenanza licencias"
    if "normas" in n or "subsidiari" in n or "nnss" in n:
        return "normas subsidiarias"
    if "pgou" in n or "plan" in n:
        return "planeamiento"
    return "documento urbanístico"


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "gargantales" in n and "plan parcial" in n:
        return "plan parcial"
    if "gargantales" in n:
        return "urbanización Los Gargantales"
    if "ambiental estrat" in n:
        return "documento ambiental estratégico"
    if "informaci" in n and "p[uú]blica" in n:
        return "información pública"
    if "casco hist" in n or "recuperando" in n:
        return "rehabilitación casco histórico"
    if "urbanizaci" in n:
        return "urbanización"
    if "pgou" in n or "plan general" in n or "planeamiento" in n:
        return "planeamiento"
    if "normas subsidiarias" in n or "nnss" in n:
        return "normas subsidiarias"
    return "urbanismo"


class GargantaDeLosMontesAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress + tablón eHome (espublico gestiona) + PDFs ordenanzas/impresos."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.impresos_url = str(self.config.get("impresos_url") or f"{WP_BASE}/impresos/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.wp_api = str(self.config.get("wp_api_base") or f"{WP_BASE}/wp-json/wp/v2").rstrip("/")
        self.wfs_municipio = str(self.config.get("wfs_municipio") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        use_insecure = self.config.get("insecure_ssl", True) if insecure is None else insecure
        ctx = self._ssl_ctx if use_insecure and "sedelectronica" in url else None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url, insecure=False))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, insecure=True)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "preview-document" not in row_html:
                continue
            cells = [_strip_html(c) for c in RE_BOARD_CELL.findall(row_html)]
            cells = [c for c in cells if c]
            if len(cells) < 4:
                continue
            if cells[0] in ("Documento", "Expediente"):
                continue

            documento = cells[0] if len(cells) > 0 else ""
            expediente = cells[1] if len(cells) > 1 else ""
            procedimiento = cells[2] if len(cells) > 2 else ""
            categoria = cells[3] if len(cells) > 3 else ""
            descripcion = cells[4] if len(cells) > 4 else ""
            fecha_raw = cells[5] if len(cells) > 5 else ""

            preview_m = RE_PREVIEW_LINK.search(row_html)
            url = preview_m.group(1) if preview_m else self.board_url

            titulo = descripcion or documento
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            blob = f"{documento} {expediente} {procedimiento} {categoria} {descripcion}"
            if RE_EXCLUDE.search(blob):
                continue

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": blob,
                    "origen": "tablon_sede",
                }
            )
        return rows

    def _collect_seed_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url, insecure=False)
            except urllib.error.URLError:
                continue
            for m in RE_WP_PDF.finditer(html):
                raw = m.group(1)
                pdf = raw if raw.startswith("http") else urllib.parse.urljoin(f"{WP_BASE}/", raw)
                if pdf in seen:
                    continue
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                blob = f"{name} {page_url}"
                if RE_EXCLUDE.search(blob) and not RE_PROYECTO.search(blob):
                    continue
                if not RE_PROYECTO.search(blob):
                    continue
                seen.add(pdf)
                rows.append(
                    {
                        "id": _stable_id("proy", pdf),
                        "municipio": MUNICIPIO,
                        "titulo": f"{MUNICIPIO}: {name}",
                        "fecha": _fecha_from_blob(pdf) or _fecha_from_blob(name),
                        "tipo": _planeamiento_tipo(name),
                        "url": page_url,
                        "pdf_url": pdf,
                        "source": "ayuntamiento",
                        "origen": "planeamiento_web",
                    }
                )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[int] = set()
        for term in (
            "gargantales",
            "plan parcial",
            "ambiental estrategico",
            "casco historico",
            "urbanizacion",
            "planeamiento",
            "informacion publica",
        ):
            url = f"{self.wp_api}/posts?search={urllib.parse.quote(term)}&per_page=50&status=publish"
            try:
                posts = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                continue
            if not isinstance(posts, list):
                continue
            for post in posts:
                wp_id = post.get("id")
                if wp_id in seen:
                    continue
                title_obj = post.get("title") or {}
                titulo = unescape(str(title_obj.get("rendered") or "")).strip()
                if not titulo or RE_EXCLUDE.search(titulo):
                    continue
                if not RE_PROYECTO.search(titulo):
                    continue
                seen.add(wp_id)
                link = str(post.get("link") or WP_BASE)
                fecha = str(post.get("date") or "")[:10] or None
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": fecha,
                        "url": link,
                        "tipo": _proyecto_tipo(titulo),
                        "origen": "wp_rest",
                        "wp_id": wp_id,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        pages: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.impresos_url),
                "fecha_concesion": None,
                "tipo": "impresos licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Impresos — licencias, declaración responsable y ocupación vía",
                "url": self.impresos_url,
                "source": "ayuntamiento",
                "nota": "Formularios E-4, E-5, E-7 y otros trámites municipales",
                "origen": "impresos_web",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — catálogo de trámites",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes urbanísticas",
                "origen": "sede_tramites",
            },
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Publicación de edictos y licencias cuando proceda",
                "origen": "tablon_sede",
            },
        ]
        for pdf_url, label in IMPRESOS_LICENCIA_URLS:
            pages.append(
                {
                    "id": _stable_id("lic", pdf_url),
                    "fecha_concesion": None,
                    "tipo": "formulario licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": label,
                    "url": pdf_url,
                    "source": "ayuntamiento",
                    "nota": "Impreso descargable del ayuntamiento",
                    "origen": "impresos_pdf",
                }
            )
        return pages

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if rec.get("geom_geojson"):
            return
        titulo = rec.get("titulo") or ""
        geom, meta = resolve_ambito_geometry(self.wfs_municipio, titulo)
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = (
            "https://idem.comunidad.madrid/geoserver3/ows"
            f"?service=WFS&typeName=sitcm:VPLA_V_AMBITO&CQL_FILTER=DS_MUNICIPIO='{self.wfs_municipio}'"
        )
        rec["coord_source"] = "portal_geometry_centroid"
        if meta.get("ambito_name"):
            rec["ambito_sit"] = meta["ambito_name"]
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("expediente") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        key = str(row.get("wp_id") or row["url"])
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "urbanismo",
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
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
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "impresos_tablon"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for row in self._collect_board():
            rec = self._board_to_licencia(row)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_seed_pdfs():
            self._enrich_geometry(rec)
            add(rec)
        for row in self._collect_wp_posts():
            add(self._wp_to_proyecto(row))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "planeamiento_pdfs": sum(1 for r in rows if r.get("origen") == "planeamiento_web"),
            "wp_posts": sum(1 for r in rows if r.get("origen") == "wp_rest"),
            "tablon_items": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "with_geometry": sum(1 for r in rows if r.get("geom_geojson")),
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
