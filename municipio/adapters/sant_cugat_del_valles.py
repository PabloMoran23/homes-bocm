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
from municipio.geometry import record_geometry

SEDE_BASE = "https://seu.santcugat.cat/seu"
WEB_BASE = "https://www.santcugat.cat"
MUNICIPIO = "Sant Cugat del Vallès"
ID_PREFIX = "sant-cugat-del-valles"

TABLON_URBANISME = f"{SEDE_BASE}/Tablon.aspx?id_grupo=18"
TABLON_GENERAL = f"{SEDE_BASE}/Tablon.aspx?id_grupo=1"
PROCEDIMIENTOS_OBRAS = f"{SEDE_BASE}/Procedimientos.aspx?id_grupo=507"

WFS_BASE = "https://geo.santcugat.cat/geoserver/wfs"
WFS_BOUNDARY_TYPE = "stcugatgufons:PLANOL_MUNICIPIS_G5"

DEFAULT_LICENCIA_PAGES: list[tuple[str, str]] = [
    (PROCEDIMIENTOS_OBRAS, "Llicències d'obres particulars — seu electrònica"),
    (
        f"{SEDE_BASE}/Procedimiento_ver_doc.aspx?plantilla=6221",
        "Guia de tràmits — informació urbanística",
    ),
    (
        f"{WEB_BASE}/web/planejament-i-gestio-urbanistics",
        "Planejament i gestió urbanística",
    ),
]

RE_LICENCIA = re.compile(
    r"(?i)(llicen[cs]ia|llicència|comunicaci[oó] previa|declaraci[oó] responsable|"
    r"autoritzaci[oó] (?:previa|urban)|edificaci[oó]n|obra particular)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|pgm|projecte|reurban|itinerari|suspensi[oó]|modificaci[oó]|"
    r"mem[oò]ria t[eè]cnica|informaci[oó] p[uú]blica|expedient|aprovaci[oó]|"
    r"restauraci[oó]|capella|zbe|pol[ií]gon industrial|can mag[ií]|masia|"
    r"licen[cs]ia|comunicaci[oó])",
)
RE_EXCLUDE = re.compile(
    r"(?i)(funerari|drets funeraris|atorgament de drets funeraris|subvencions en r[eè]gim|"
    r"plantilla|personal municipal|policia local|borsa de)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_TABLON_ROW = re.compile(
    r'<tr class="GridViewRow">\s*<td>\s*(.*?)\s*</td>\s*'
    r"<td>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>\s*"
    r"<td>\s*(\d{1,2}/\d{1,2}/\d{4})\s*</td>\s*"
    r"<td>\s*([^<]*?)\s*</td>\s*<td>.*?href=\"([^\"]*DetalleTablon\.aspx\?id=\d+)\"",
    re.S,
)
RE_EXPEDIENTE = re.compile(r"(?i)Exp\.?\s*(\d+/\d+)")
RE_DOC_LINK = re.compile(
    r'href="([^"]*Tablon_ver_doc\.aspx\?[^"]+)"[^>]*>([^<]{3,200})',
    re.I,
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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _tipo_proyecto(titulo: str) -> str:
    blob = titulo.lower()
    if "suspensi" in blob and "llicen" in blob:
        return "suspensión de licencias"
    if "reurban" in blob:
        return "reurbanización"
    if "itinerari" in blob or "ciclist" in blob:
        return "itinerario viario"
    if "modificaci" in blob and "pgm" in blob:
        return "modificación PGM"
    if "memòria" in blob or "memoria" in blob:
        return "memoria técnica"
    if "aprovaci" in blob and "inicial" in blob:
        return "aprobación inicial"
    if "aprovaci" in blob and "definitiva" in blob:
        return "aprobación definitiva"
    if "restauraci" in blob:
        return "restauración patrimonio"
    return "anuncio urbanismo"


class SantCugatDelVallesAyuntamientoAdapter(AyuntamientoAdapter):
    """Seu electrònica ASP.NET (tabló T101 Urbanisme) + tràmits obres; GIS GeoServer (auth en GetFeature)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.wfs_url = str(self.config.get("wfs_url") or WFS_BASE)
        self.wfs_boundary_type = str(self.config.get("wfs_boundary_type") or WFS_BOUNDARY_TYPE)
        self.tablon_urbanisme = str(self.config.get("tablon_urbanisme") or TABLON_URBANISME)
        self.licencia_pages = [
            (str(u), str(t))
            for u, t in (self.config.get("licencia_pages") or DEFAULT_LICENCIA_PAGES)
        ]
        self._boundary_geom: dict[str, Any] | None | bool = False
        self.enrich_details = bool(self.config.get("enrich_details", True))

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.get("user_agent", "poc-bocm-sant-cugat-del-valles/1.0"),
            },
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.sede_base}/", href)

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
                    rows.append(json.loads(line))
        return rows

    def _try_wfs_boundary(self) -> dict[str, Any] | None:
        if self._boundary_geom is not False:
            return self._boundary_geom
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_boundary_type,
                "outputFormat": "application/json",
                "count": "5",
                "srsName": "EPSG:4326",
            }
        )
        url = f"{self.wfs_url}?{params}"
        geom_out: dict[str, Any] | None = None
        try:
            data = self._fetch_json(url)
            if isinstance(data, dict) and data.get("features"):
                for feat in data["features"]:
                    if not isinstance(feat, dict):
                        continue
                    geom = feat.get("geometry")
                    if isinstance(geom, dict) and geom.get("type") in {"Polygon", "MultiPolygon"}:
                        geom_out = geom
                        break
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            geom_out = None
        self._boundary_geom = geom_out
        return geom_out

    def _parse_tablon(self, html: str, *, urban_only: bool) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            titulo = _strip_html(m.group(1))
            fecha_pub = _parse_fecha_dmy(m.group(2))
            fecha_fin = _parse_fecha_dmy(m.group(4)) if m.group(4).strip() else None
            detail_href = m.group(5)
            detail_url = self._abs_url(detail_href)

            if RE_EXCLUDE.search(titulo):
                continue
            if urban_only and not RE_PROYECTO.search(titulo):
                continue

            rec: dict[str, Any] = {
                "id": _stable_id("proy", detail_url),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha_pub,
                "fecha_fin_ip": fecha_fin,
                "tipo": _tipo_proyecto(titulo),
                "url": detail_url,
                "source": "ayuntamiento",
                "origen": "sede_tablon_urbanisme",
            }
            rows.append(rec)
        return rows

    def _enrich_detail(self, rec: dict[str, Any]) -> None:
        url = str(rec.get("url") or "")
        if not url:
            return
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return

        desc_m = re.search(
            r'id="ctl00_Content_LDescripcionPub"[^>]*>[^<]*</span>\s*'
            r'<span class="LitDetalle">(.*?)</span>',
            html,
            re.S,
        )
        if desc_m:
            desc = _strip_html(desc_m.group(1))
            if desc and len(desc) > len(str(rec.get("titulo") or "")):
                rec["titulo"] = desc[:500]

        exp_m = RE_EXPEDIENTE.search(html)
        if exp_m:
            rec["expediente"] = exp_m.group(1)

        docs: list[dict[str, str]] = []
        for dm in RE_DOC_LINK.finditer(html):
            href = unescape(dm.group(1))
            label = _strip_html(dm.group(2))
            if "ValidarDocumento" in href:
                continue
            doc_url = self._abs_url(href)
            docs.append({"titulo": label[:300], "url": doc_url})
        if docs:
            rec["documentos"] = docs
            rec["pdf_url"] = docs[0]["url"]

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_urbanisme)
        except urllib.error.URLError:
            return []

        rows = self._parse_tablon(html, urban_only=True)

        for rec in rows:
            if self.enrich_details:
                self._enrich_detail(rec)

        return rows

    def _collect_licencias(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        try:
            html = self._fetch(self.tablon_urbanisme)
            for rec in self._parse_tablon(html, urban_only=False):
                if not RE_LICENCIA.search(rec["titulo"]):
                    continue
                lic = {
                    "id": _stable_id("lic", rec["url"]),
                    "fecha_concesion": rec.get("fecha"),
                    "tipo": "anuncio tablón urbanismo",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": rec["titulo"],
                    "url": rec["url"],
                    "source": "ayuntamiento",
                    "origen": "sede_tablon_urbanisme",
                }
                if lic["id"] not in seen:
                    seen.add(lic["id"])
                    rows.append(lic)
        except urllib.error.URLError:
            pass

        for page_url, titulo in self.licencia_pages:
            rec_id = _stable_id("lic", page_url)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia obra",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": page_url,
                    "source": "ayuntamiento",
                    "nota": "Sin listado público de concesiones; trámites y guía informativa",
                }
            )

        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_tablon_y_tramites"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
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
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "source": "sede_tablon_t101_urbanisme",
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
        return {
            "rows": after,
            "added": max(0, after - before),
            "with_geometry": stats.get("with_geometry", 0),
            "status": "ok",
        }
