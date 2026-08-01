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

WP_BASE = "https://www.sevillalanueva.es"
SEDE_BASE = "https://sevillalanueva.sedelectronica.es"
MUNICIPIO = "Sevilla la Nueva"
ID_PREFIX = "sevilla-la-nueva"

PLANEAMIENTO_URL = f"{WP_BASE}/planeamiento/"
PGOU_AVANCE_URL = f"{WP_BASE}/urbanismo/avance-plan-general-de-ordenacion-urbana/"
TRAMITES_URL = f"{WP_BASE}/urbanismo/tramites/"
LICENCIAS_URL = f"{WP_BASE}/tramites-de-urbanismo-solicitudes-licencias/"

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "SEVILLA LA NUEVA"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|obra)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"c[eé]dula urban|disciplina urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|parcela|suelo|normas subsidiarias|"
    r"expropiaci|ocupaci[oó]n|nnss|zona \d|valdelagua|los cortijos|los manantiales|"
    r"catalogo|inventario|anexo|biocorredor)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(padr[oó]n|personal|polic[ií]a local|oposici[oó]n|psicot[eé]cn|"
    r"reglamento.*(?:dec|c[aá]mara corporal)|ordenanza.*medio ambiente|"
    r"dispositivo el[eé]ctrico)",
)
RE_SKIP_PDF = re.compile(r"(?i)observatorio-de-empleo")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})[-/](\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://sevillalanueva\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://www\.sevillalanueva\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_DROPBOX = re.compile(
    r'href="(https://www\.dropbox\.com/[^"]+)"',
    re.I,
)
RE_AMBIT_CODE = re.compile(
    r"(?i)\b((?:SAU|UE|API|ERU)-\d+(?:[ .][A-Z0-9 .-]+)?)\b",
)
RE_ZONA = re.compile(r"(?i)\bZona\s+(\d{1,2})\b")


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


def _fecha_from_blob(text: str, url: str = "") -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = re.search(r"BOCM[- ]?(\d{4})(\d{2})(\d{2})", text or "", re.I)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    m = RE_FECHA_YM.search(url or text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(f"{text} {url}") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _abs_url(href: str, base: str = WP_BASE) -> str:
    return urllib.parse.urljoin(base, unescape(href))


def _proyecto_tipo(title: str, url: str = "") -> str:
    blob = f"{title} {url}".lower()
    if "expropiaci" in blob or "ocupaci" in blob:
        return "expropiación"
    if "pgou" in blob or "avance" in blob:
        return "planeamiento"
    if "modificaci" in blob or "puntual" in blob:
        return "modificación puntual"
    if "normas subsidiarias" in blob or "nnss" in blob or "plano" in blob:
        return "normas subsidiarias"
    if "catalogo" in blob or "inventario" in blob:
        return "planeamiento"
    if "informaci" in blob:
        return "información pública"
    if "convenio" in blob:
        return "convenio urbanístico"
    return "urbanismo"


def _sector_ilike_parts(text: str) -> list[str]:
    low = text.lower()
    for marker in (" del pgou", " pgou", " bocm", " aprob", " anuncio", " modificación"):
        if marker in low:
            low = low.split(marker, 1)[0]
    parts = [p for p in re.split(r"[\s,;/|()]+", low) if len(p) >= 4]
    out: list[str] = []
    seen: set[str] = set()
    for p in parts:
        if p not in seen and not re.fullmatch(r"\d{4}", p):
            seen.add(p)
            out.append(p)
    return out[:8]


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
        t = g.get("type")
        coords = g.get("coordinates")
        if t == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif t == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class SevillaLaNuevaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress planeamiento + tablón eHome (espublico) + WFS SIT CM (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.planeamiento_url = str(self.config.get("planeamiento_url") or PLANEAMIENTO_URL)
        self.pgou_avance_url = str(self.config.get("pgou_avance_url") or PGOU_AVANCE_URL)
        self.tramites_url = str(self.config.get("tramites_url") or TRAMITES_URL)
        self.licencias_url = str(self.config.get("licencias_url") or LICENCIAS_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_cache: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-sevilla-la-nueva/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _collect_pdf_links(self, page_url: str, origen: str) -> list[dict[str, Any]]:
        try:
            html = self._fetch(page_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            pdf = _abs_url(m.group(1), page_url)
            if pdf in seen or RE_SKIP_PDF.search(pdf):
                continue
            seen.add(pdf)
            anchor_m = re.search(
                rf'href="{re.escape(m.group(1))}"[^>]*>(.*?)</a>',
                html[m.start() : m.start() + 1500],
                re.I | re.S,
            )
            label = _strip_html(anchor_m.group(1)) if anchor_m else ""
            if not label:
                label = unescape(Path(urllib.parse.unquote(pdf)).stem.replace("_", " "))
            rows.append(
                {
                    "titulo": label[:500],
                    "url": page_url,
                    "pdf_url": pdf,
                    "fecha": _fecha_from_blob(label, pdf),
                    "origen": origen,
                    "blob": f"{label} {pdf}",
                }
            )
        return rows

    def _collect_dropbox_links(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.pgou_avance_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_DROPBOX.finditer(html):
            link = m.group(1)
            if link in seen:
                continue
            seen.add(link)
            anchor_m = re.search(
                rf'href="{re.escape(link)}"[^>]*>(.*?)</a>',
                html[m.start() : m.start() + 1200],
                re.I | re.S,
            )
            label = _strip_html(anchor_m.group(1)) if anchor_m else ""
            if not label:
                label = unescape(urllib.parse.unquote(link.split("/")[-1].split("?")[0]))
            rows.append(
                {
                    "titulo": f"Avance PGOU: {label}"[:500],
                    "url": self.pgou_avance_url,
                    "pdf_url": link,
                    "fecha": "2024-01-01",
                    "origen": "pgou_avance_dropbox",
                    "blob": f"{label} pgou avance planeamiento",
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(1)
            if "preview-document" not in row_html:
                continue
            cells = [_strip_html(c) for c in RE_BOARD_CELL.findall(row_html)]
            cells = [c for c in cells if c]
            if len(cells) < 4 or cells[0] in ("Documento", "Expediente"):
                continue

            documento = cells[0]
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tramites_url),
                "fecha_concesion": None,
                "tipo": "trámites licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Trámites de urbanismo — licencias y cédulas urbanísticas",
                "url": self.tramites_url,
                "source": "ayuntamiento",
                "nota": "Página informativa; solicitudes vía sede electrónica",
            },
            {
                "id": _stable_id("lic", self.licencias_url),
                "fecha_concesion": None,
                "tipo": "solicitud licencia de obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Solicitudes de licencias de urbanismo",
                "url": self.licencias_url,
                "source": "ayuntamiento",
                "nota": "Enlace a sede; requiere certificado digital",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Presentación digital de solicitudes",
            },
        ]

    def _wfs_query(self, cql: str, count: int = 20) -> list[dict[str, Any]]:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(count),
                "CQL_FILTER": cql,
            }
        )
        url = f"{self.wfs_url}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(data, dict):
            return []
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _load_wfs_ambitos(self) -> dict[str, dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        muni = self.wfs_municipio.replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        cache: dict[str, dict[str, Any]] = {}
        for f in feats:
            props = f.get("properties") or {}
            name = str(props.get("DS_NOMB_AMB") or "").strip()
            if not name:
                continue
            cache.setdefault(name.upper(), f)
            code_m = RE_AMBIT_CODE.search(name)
            if code_m:
                cache.setdefault(code_m.group(1).upper(), f)
        self._wfs_cache = cache
        return cache

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        cache = self._load_wfs_ambitos()
        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for m in RE_AMBIT_CODE.finditer(title):
            code = m.group(1).upper().split()[0]
            feat = cache.get(code) or cache.get(m.group(1).upper())
            if feat:
                candidates.append((100.0, code, feat))

        zona_m = RE_ZONA.search(title)
        if zona_m:
            zona = zona_m.group(1)
            for key, feat in cache.items():
                if f"ZONA {zona}" in key or f"ZONA{zona}" in key.replace(" ", ""):
                    candidates.append((60.0, key, feat))

        for part in _sector_ilike_parts(title):
            if part.lower() in {"valdelagua", "manantiales", "cortijos", "sevilla", "nueva"}:
                for key, feat in cache.items():
                    if part.lower() in key.lower():
                        candidates.append((40.0, key, feat))

        if not candidates:
            return None

        candidates.sort(key=lambda x: (-x[0], x[1]))
        best_score, best_name, _ = candidates[0]
        if best_score < 40:
            return None

        same_name = [
            f
            for _, name, f in candidates
            if str((f.get("properties") or {}).get("DS_NOMB_AMB") or "").upper() == best_name
            or name == best_name
        ]
        if not same_name:
            same_name = [candidates[0][2]]

        merged = _merge_geometries(same_name)
        if not merged:
            return None

        cql = (
            f"DS_MUNICIPIO='{self.wfs_municipio.replace(chr(39), chr(39) * 2)}' "
            f"AND DS_NOMB_AMB='{best_name.replace(chr(39), chr(39) * 2)}'"
        )
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": (
                f"{self.wfs_url}?service=WFS&request=GetFeature&srsName=EPSG:4326&CQL_FILTER="
                f"{urllib.parse.quote(cql)}"
            ),
            "coord_source": "portal_geometry_centroid",
            "ambito_sit": best_name,
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if geom:
            rec.update(geom)
            cen = geometry_centroid(geom["geom_geojson"])
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _pdf_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        pdf = row.get("pdf_url") or ""
        if RE_SKIP_PDF.search(pdf):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = pdf or row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"][:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"], pdf),
            "url": row.get("url") or self.planeamiento_url,
            "pdf_url": pdf or None,
            "source": "ayuntamiento",
            "origen": row.get("origen", "planeamiento_pdf"),
        }
        self._enrich_geometry(rec)
        return rec

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        meta = f"{row.get('categoria', '')} {row.get('procedimiento', '')} {row.get('blob', '')}"
        if RE_BOARD_NON_URBAN.search(meta):
            return False
        return True

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        return {
            "id": _stable_id("lic", row.get("expediente") or row["url"]),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / edicto urbanismo",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"][:500],
            "expte": row.get("expediente"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sede",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
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
            "tipo": _proyecto_tipo(row["titulo"], row.get("url") or ""),
            "url": row["url"],
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
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_tablon"}

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

        for row in self._collect_pdf_links(self.planeamiento_url, "planeamiento_pdf"):
            add(self._pdf_to_proyecto(row))
        for row in self._collect_dropbox_links():
            add(self._pdf_to_proyecto(row))
        for row in self._collect_board():
            add(self._board_to_proyecto(row))

        self._write_jsonl(out_jsonl, rows)
        pdf_n = sum(1 for r in rows if str(r.get("origen", "")).endswith("_pdf"))
        dropbox_n = sum(1 for r in rows if r.get("origen") == "pgou_avance_dropbox")
        tablon_n = sum(1 for r in rows if r.get("origen") == "tablon_sede")
        geom_n = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "planeamiento_pdfs": pdf_n,
            "pgou_dropbox": dropbox_n,
            "tablon_items": tablon_n,
            "with_geometry": geom_n,
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": after,
                    "added": max(0, after - before),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
