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
from municipio.geometry import geometry_centroid

WP_BASE = "https://loeches.es"
SEDE_BASE = "https://loeches.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
PGOU_URL = f"{WP_BASE}/plan-general-de-ordenacion-urbana/"
URBANISMO_CATEGORY_ID = 34
MUNICIPIO = "Loeches"
ID_PREFIX = "loeches"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"licencias urban|licencias de actividad|taller|actividad de)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|sector|parcela|suelo|"
    r"normas subsidiarias|l[ií]neas? a[eé]reas|red el[eé]ctrica|emmdt|solares|"
    r"ordenaci[oó]n|anuncio.*p[uú]blica)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(empleo p[uú]blico|proceso selectivo|calificaciones|plantilla respuestas|"
    r"cobranza iae|padr[oó]n fiscal|subvencion)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})/(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://loeches\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="(https://loeches\.es/wp-content/uploads/[^"]+\.pdf)"',
    re.I,
)
RE_AMBITO_CODE = re.compile(r"\b([SU]-\d+)\b", re.I)

GEOM_HINTS: list[tuple[str, str]] = [
    ("valdepozuelo", "VALDEPOZUELO"),
    ("pancho chico", "PANCHO"),
    ("el crucero", "CRUCERO"),
    ("los prados", "PRADOS"),
    ("cabezo gordo", "CABEZO"),
    ("camino peralta", "PERALTA"),
    ("calle ronda", "RONDA"),
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


def _fecha_from_url_or_text(url: str, text: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = re.search(r"BOCM-(\d{4})(\d{2})(\d{2})", f"{url} {text}")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [
        int(x.group(1))
        for x in RE_YEAR.finditer(f"{url} {text}")
        if 1980 <= int(x.group(1)) <= 2035
    ]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "memoria" in n:
        return "memoria planeamiento"
    if "plano" in n:
        return "planos ordenación"
    if "tript" in n or "trípt" in n:
        return "documentación participación"
    return "planeamiento"


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "informaci" in n and "p" in n:
        return "información pública"
    if "sector industrial" in n or "calle ronda" in n:
        return "planeamiento"
    if "pgou" in n or "plan general" in n or "normas subsidiarias" in n:
        return "planeamiento"
    if "bocm" in n:
        return "publicación BOCM"
    if "líneas" in n or "eléctric" in n or "220 kv" in n:
        return "autorización urbanística"
    if "emmdt" in n:
        return "EMMDT"
    if "solares" in n or "terrenos privados" in n:
        return "ordenanza urbanística"
    return "urbanismo"


class LoechesAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo + PGOU PDFs + tablón espublico (eHome). Geometría parcial SITCM WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.urbanismo_category_id = int(
            self.config.get("urbanismo_category_id") or URBANISMO_CATEGORY_ID
        )
        self.citizen_service_url = str(
            self.config.get("citizen_service_urbanismo")
            or f"{self.sede_base}/citizen-service/7f14c9f4-69e3-4ff8-87ea-4b62749bdce5"
        )
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or MUNICIPIO)
        self._wfs_cache: list[dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, use_sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-loeches/1.0")},
        )
        if use_sede or "sedelectronica" in url:
            with self._opener.open(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_sede=True)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento:
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            titulo = descripcion or documento
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            rows.append(
                {
                    "documento": documento[:500],
                    "expediente": expediente[:120],
                    "procedimiento": procedimiento[:200],
                    "categoria": categoria[:120],
                    "titulo": titulo[:500],
                    "fecha": _parse_fecha_dmy(fecha_raw),
                    "url": url,
                    "blob": f"{documento} {expediente} {procedimiento} {categoria} {descripcion}",
                }
            )
        return rows

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.pgou_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            pdf = m.group(1)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            titulo = f"PGOU Loeches: {name}"
            rows.append(
                {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_url_or_text(pdf) or "2023-03-31",
                    "tipo": _pgou_tipo(name),
                    "url": self.pgou_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "pgou_web",
                }
            )
        return rows

    def _collect_wp_urbanismo(self) -> list[dict[str, Any]]:
        api_url = (
            f"{WP_BASE}/wp-json/wp/v2/posts"
            f"?categories={self.urbanismo_category_id}&per_page=50"
        )
        try:
            posts = self._fetch_json(api_url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []

        rows: list[dict[str, Any]] = []
        if not isinstance(posts, list):
            return rows

        for post in posts:
            if not isinstance(post, dict):
                continue
            title = unescape(str((post.get("title") or {}).get("rendered") or "")).strip()
            link = str(post.get("link") or self.pgou_url)
            fecha = str(post.get("date") or "")[:10] or None
            if not title or len(title) < 8:
                continue
            if not RE_PROYECTO.search(title):
                continue
            rows.append(
                {
                    "id": _stable_id("proy", link),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(title),
                    "url": link,
                    "source": "ayuntamiento",
                    "origen": "wp_urbanismo",
                }
            )
        return rows

    def _fetch_wfs_ambitos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": self.wfs_type,
            "outputFormat": "application/json",
            "maxFeatures": "50",
            "CQL_FILTER": f"DS_MUNICIPIO ILIKE '%{muni}%'",
        }
        url = self.wfs_url + "?" + urllib.parse.urlencode(params)
        try:
            data = self._fetch_json(url)
            self._wfs_cache = data.get("features") or []
        except (urllib.error.URLError, json.JSONDecodeError, AttributeError):
            self._wfs_cache = []
        return self._wfs_cache

    def _match_wfs_geometry(
        self, title: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        features = self._fetch_wfs_ambitos()
        if not features:
            return None, None

        title_up = title.upper()
        codes = [m.group(1).upper() for m in RE_AMBITO_CODE.finditer(title)]
        best: dict[str, Any] | None = None
        best_score = 0

        for needle, wfs_hint in GEOM_HINTS:
            if needle in title.lower():
                for feat in features:
                    amb = str((feat.get("properties") or {}).get("DS_NOMB_AMB") or "").upper()
                    if wfs_hint.upper() in amb:
                        score = 4
                        if score > best_score:
                            best_score = score
                            best = feat

        for feat in features:
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            if not isinstance(geom, dict):
                continue
            amb = str(props.get("DS_NOMB_AMB") or "").upper()
            score = 0
            for code in codes:
                if code in title_up and code in amb:
                    score += 3
            if amb and amb in title_up:
                score += 2
            for token in re.split(r"[\s,;/|]+", title_up):
                if len(token) >= 5 and token in amb:
                    score += 1
            if score > best_score:
                best_score = score
                best = feat

        if best_score < 2 or not best:
            return None, None
        return best.get("geometry"), best.get("properties") or {}

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        geom, props = self._match_wfs_geometry(rec.get("titulo") or "")
        if not geom:
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        muni = self.wfs_municipio.replace("'", "''")
        rec["geometry_source_url"] = (
            f"{self.wfs_url}?service=WFS&typeName={self.wfs_type}"
            f"&CQL_FILTER=DS_MUNICIPIO ILIKE '%25{muni}%25'"
        )
        rec["coord_source"] = "portal_geometry_centroid"
        if props.get("DS_NOMB_AMB"):
            rec["ambito_sit"] = props["DS_NOMB_AMB"]
        centroid = geometry_centroid(geom)
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón licencias urbanísticas",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — licencias y urbanismo",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios vigentes en sede electrónica",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", self.citizen_service_url),
                "fecha_concesion": None,
                "tipo": "trámite declaración responsable",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Declaración responsable o comunicación en materia urbanística",
                "url": self.citizen_service_url,
                "source": "ayuntamiento",
                "nota": "Catálogo trámites sede; sin listado de concesiones",
                "origen": "sede_tramite",
            },
        ]

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        fecha = row.get("fecha") or _fecha_from_url_or_text(row.get("url") or "", blob)
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("url") or blob),
            "fecha_concesion": fecha,
            "tipo": "licencia urbanística",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row.get("titulo") or row.get("documento"),
            "url": row.get("url") or self.board_url,
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": "tablon_sede",
        }
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        fecha = row.get("fecha") or _fecha_from_url_or_text(row.get("url") or "", blob)
        titulo = row.get("titulo") or row.get("documento") or "Anuncio urbanismo"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("url") or blob),
            "municipio": MUNICIPIO,
            "titulo": titulo[:500],
            "fecha": fecha,
            "tipo": _proyecto_tipo(titulo),
            "url": row.get("url") or self.board_url,
            "source": "ayuntamiento",
            "expte": row.get("expediente"),
            "origen": "tablon_sede",
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
        return {"rows": len(rows), "status": "ok", "source": "sede_tablon"}

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

        for rec in self._collect_pgou_pdfs():
            add(rec)
        for rec in self._collect_wp_urbanismo():
            self._enrich_geometry(rec)
            add(rec)
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "pgou": sum(1 for r in rows if r.get("origen") == "pgou_web"),
            "wp": sum(1 for r in rows if r.get("origen") == "wp_urbanismo"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)

        def merge(rec: dict[str, Any] | None) -> None:
            if rec:
                existing[rec["id"]] = rec

        for rec in self._collect_pgou_pdfs():
            merge(rec)
        for rec in self._collect_wp_urbanismo():
            self._enrich_geometry(rec)
            merge(rec)
        for row in self._collect_board():
            merge(self._board_to_proyecto(row))

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
