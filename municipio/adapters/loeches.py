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

WP_BASE = "https://loeches.es"
SEDE_BASE = "https://loeches.sedelectronica.es"
MUNICIPIO = "Loeches"
ID_PREFIX = "loeches"
WFS_MUNICIPIO = "LOECHES"

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal|de actividad|de apertura)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"licencias urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgom|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|bocm|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva|provisional)|parcela|suelo|sector|"
    r"redacci[oó]n del plan|normas subsidiarias|nnss|l[ií]neas a[eé]reas)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(empleo p[uú]blico|oposici[oó]n|proceso selectivo|iae|padr[oó]n fiscal|"
    r"campaña limpieza|juegos infantiles|parques municipales)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(\d{4})-(\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_BOARD_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="(https://loeches\.sedelectronica\.es/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_WP_PDF = re.compile(
    r'href="((?:https://loeches\.es)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)


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


def _pgou_tipo(name: str) -> str:
    n = name.lower()
    if "memoria" in n:
        return "memoria PGOU"
    if "planos" in n or "plano" in n:
        return "planos PGOU"
    if "tript" in n:
        return "documentación PGOU"
    if "pgou" in n or "plan" in n:
        return "planeamiento"
    return "documento PGOU"


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "informaci" in n and "p[uú]blica" in n:
        return "información pública"
    if "pgou" in n or "plan general" in n or "planeamiento" in n:
        return "planeamiento"
    if "sector" in n:
        return "sector urbanístico"
    if "convenio" in n:
        return "convenio"
    if "licencia" in n and "actividad" in n:
        return "licencia de actividad"
    return "urbanismo"


class LoechesAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo + tablón eHome (espublico) + PGOU PDFs + SITCM WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board/")
        self.urbanismo_url = str(self.config.get("urbanismo_url") or f"{WP_BASE}/urbanismo/")
        self.pgou_url = str(self.config.get("pgou_url") or f"{WP_BASE}/plan-general-de-ordenacion-urbana/")
        self.wp_api = str(self.config.get("wp_api_base") or f"{WP_BASE}/wp-json/wp/v2").rstrip("/")
        self.urbanismo_cat = int(self.config.get("urbanismo_category_id") or 34)
        self.wfs_municipio = str(self.config.get("wfs_municipio") or WFS_MUNICIPIO)
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE

    def _fetch(self, url: str, *, insecure: bool | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-loeches/1.0")},
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

    def _collect_pgou_pdfs(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.pgou_url, insecure=False)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_WP_PDF.finditer(html):
            raw = m.group(1)
            pdf = raw if raw.startswith("http") else urllib.parse.urljoin(f"{WP_BASE}/", raw)
            if pdf in seen:
                continue
            seen.add(pdf)
            name = unescape(urllib.parse.unquote(Path(pdf).name))
            rows.append(
                {
                    "id": _stable_id("proy", pdf),
                    "municipio": MUNICIPIO,
                    "titulo": f"PGOU Loeches: {name}",
                    "fecha": _fecha_from_blob(pdf) or "2023-03-31",
                    "tipo": _pgou_tipo(name),
                    "url": self.pgou_url,
                    "pdf_url": pdf,
                    "source": "ayuntamiento",
                    "origen": "pgou_web",
                }
            )
        return rows

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        url = f"{self.wp_api}/posts?categories={self.urbanismo_cat}&per_page=50&status=publish"
        try:
            posts = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return []
        if not isinstance(posts, list):
            return []

        rows: list[dict[str, Any]] = []
        for post in posts:
            title_obj = post.get("title") or {}
            titulo = unescape(str(title_obj.get("rendered") or "")).strip()
            if not titulo or RE_EXCLUDE.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo):
                continue
            link = str(post.get("link") or self.urbanismo_url)
            fecha = str(post.get("date") or "")[:10] or None
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "url": link,
                    "tipo": _proyecto_tipo(titulo),
                    "origen": "wp_rest",
                    "wp_id": post.get("id"),
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "id": _stable_id("lic", self.urbanismo_url),
                "fecha_concesion": None,
                "tipo": "trámite licencia urbanística",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — trámites y documentación",
                "url": self.urbanismo_url,
                "source": "ayuntamiento",
                "nota": "Página informativa; concesiones publicadas en tablón cuando proceda",
                "origen": "urbanismo_web",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/"),
                "fecha_concesion": None,
                "tipo": "sede electrónica urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — trámites urbanísticos",
                "url": f"{self.sede_base}/",
                "source": "ayuntamiento",
                "nota": "Presentación electrónica de solicitudes",
                "origen": "sede_tramites",
            },
        ]
        return rows

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
            "pgou_pdfs": sum(1 for r in rows if r.get("origen") == "pgou_web"),
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
