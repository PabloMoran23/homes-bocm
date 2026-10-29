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

WEB_BASE = "https://www.almendralejo.es"
SEDE_BASE = "https://almendralejo.sedelectronica.es"
GEOPORTAL_URL = "https://mapas.almendralejo.es/geoportal/"
WFS_BASE = "https://mapas.almendralejo.es/geoserver/ows"
MUNICIPIO = "Almendralejo"
ID_PREFIX = "almendralejo"

DEFAULT_TRANSPARENCY_URLS = (
    f"{SEDE_BASE}/transparency/7acc26a6-c6e6-4bb1-81e0-52583f315bf4/",
    f"{SEDE_BASE}/transparency/4c518d06-0b9d-49ba-a2ad-30d98ace7e59/",
)
WEB_PROYECTO_SEEDS: tuple[tuple[str, str, str], ...] = (
    (GEOPORTAL_URL, "Geoportal urbanístico municipal (Enmapa / Nexus Geographics)", "visor planeamiento"),
    (
        f"{WEB_BASE}/contenido.php?id_area=22&id_bloque=47",
        "Protocolo de Actuaciones Urbanísticas",
        "documentación urbanismo",
    ),
    (f"{WEB_BASE}/contenido.php?id_area=22", "Concejalía de Urbanismo y Patrimonio", "información urbanismo"),
)

RE_PREVIEW = re.compile(
    rf'href="({re.escape(SEDE_BASE)}/preview-document/[^"]+)"',
    re.I,
)
RE_CATALOG = re.compile(
    rf'href="({re.escape(SEDE_BASE)}/catalog/t/[^"]+)"[^>]*>([^<]+)</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra menor|obras de edificaci)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pgm|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto de actuaci|estudio de detalle|"
    r"modificaci[oó]n|aprobaci[oó]n (?:inicial|definitiva)|reparcel|sector|"
    r"edicto|bando.*parcel|actuaci[oó]n urban|protocolo.*urban|visor|geoportal|"
    r"certificado.*urban|ordenanza|pleno|acuerdo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YMD = re.compile(r"\b((?:19|20)\d{2})(\d{2})(\d{2})\b")
RE_REFCAT = re.compile(r"\b(\d{5,7}[A-Z]{1,2}\d{4}[A-Z0-9]{0,6})\b", re.I)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{prefix}-{h}"


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


def _fecha_from_blob(text: str) -> str | None:
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    m = RE_FECHA_YMD.search(text or "")
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


class AlmendralejoAyuntamientoAdapter(AyuntamientoAdapter):
    """Web municipal + sede espublico (tablón, trámites, transparencia) + GeoServer Enmapa."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self.info_url = str(self.config.get("info_url") or f"{self.sede_base}/info")
        self.dossier_url = str(self.config.get("dossier_url") or f"{self.sede_base}/dossier")
        self.transparency_urls = [
            str(u) for u in (self.config.get("transparency_urls") or DEFAULT_TRANSPARENCY_URLS)
        ]
        self.wfs_base = str(self.config.get("wfs_base") or WFS_BASE).rstrip("/")
        self._municipal_geom: dict[str, Any] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almendralejo/1.0")},
        )
        with self._opener.open(req, timeout=120) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-almendralejo/1.0")},
        )
        with self._opener.open(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def _parse_board_table(self, html: str, origen: str) -> list[dict[str, Any]]:
        tbody_m = re.search(r'<tbody[^>]*id="[^"]*">(.*?)</tbody>', html, re.S | re.I)
        if not tbody_m:
            return []
        rows: list[dict[str, Any]] = []
        sede_esc = re.escape(self.sede_base)
        for tr in re.findall(r"<tr>(.*?)</tr>", tbody_m.group(1), re.S):
            if "preview-document" not in tr:
                continue
            cells = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
            if len(cells) < 6:
                continue
            link_m = re.search(
                rf'href="({sede_esc}/preview-document/[^"]+)"',
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

    def _parse_board_links(self, html: str, origen: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_PREVIEW.finditer(html):
            url = m.group(1)
            local = html[max(0, m.start() - 400) : m.end() + 200]
            title_m = re.search(r'title="([^"]*)"', local, re.I)
            text_m = re.search(rf'href="{re.escape(url)}"[^>]*>([^<]+)<', local, re.I)
            titulo = ""
            if title_m:
                titulo = unescape(title_m.group(1).strip())
            elif text_m:
                titulo = unescape(text_m.group(1).strip())
            spans = [_strip_html(s) for s in re.findall(r"<span>([^<]+)</span>", local)]
            categoria = procedimiento = descripcion = ""
            fecha = None
            for s in spans:
                if RE_FECHA_DMY.search(s):
                    fecha = _parse_fecha_dmy(s)
            if len(spans) >= 3:
                useful = [s for s in spans if s not in ("Categoría", "Descripción", "Fecha de Publicación")]
                if useful:
                    categoria = useful[0] if len(useful) > 2 else ""
                    procedimiento = useful[1] if len(useful) > 2 else useful[0]
                    descripcion = useful[-2] if len(useful) > 2 else useful[-1]
                    if not fecha:
                        fecha = _parse_fecha_dmy(useful[-1])
            rows.append(
                {
                    "titulo": (titulo or descripcion or url)[:500],
                    "doc_label": titulo[:500],
                    "expediente": "",
                    "procedimiento": procedimiento,
                    "categoria": categoria,
                    "descripcion": descripcion or titulo,
                    "fecha": fecha or _fecha_from_blob(titulo),
                    "url": url,
                    "pdf_url": url,
                    "origen": origen,
                }
            )
        return rows

    def _collect_board(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url, origen in ((self.board_url, "tablon"), (self.info_url, "info_tablon")):
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            items = self._parse_board_table(html, origen)
            if not items:
                items = self._parse_board_links(html, origen)
            for rec in items:
                by_url[rec["url"]] = rec
        return list(by_url.values())

    def _collect_transparency(self) -> list[dict[str, Any]]:
        by_url: dict[str, dict[str, Any]] = {}
        for url in self.transparency_urls:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for item in self._parse_board_links(html, "transparencia"):
                by_url[item["url"]] = item
        return list(by_url.values())

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_CATALOG.finditer(html):
            url, titulo = m.group(1), unescape(m.group(2).strip())
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

    def _collect_web_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url, titulo, tipo in WEB_PROYECTO_SEEDS:
            rows.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "tipo": tipo,
                    "origen": "web_municipal",
                    "fecha": None,
                }
            )
        return rows

    def _municipal_boundary(self) -> dict[str, Any] | None:
        if self._municipal_geom is not None:
            return self._municipal_geom
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "almendralejogis:bt_municipios_a",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "1",
            }
        )
        url = f"{self.wfs_base}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._municipal_geom = None
            return None
        feats = data.get("features") or []
        if feats and isinstance(feats[0], dict):
            geom = feats[0].get("geometry")
            if isinstance(geom, dict) and geom.get("type"):
                self._municipal_geom = geom
                return geom
        self._municipal_geom = None
        return None

    def _fetch_parcel_geometry(self, refcat: str) -> tuple[dict[str, Any], str] | None:
        filt = f"refcat='{refcat.upper()}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": "almendralejogis:cad_parcela_a",
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "1",
                "CQL_FILTER": filt,
            }
        )
        url = f"{self.wfs_base}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            return None
        feats = data.get("features") or []
        if not feats:
            return None
        geom = feats[0].get("geometry")
        if isinstance(geom, dict) and geom.get("type"):
            return geom, url
        return None

    def _apply_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "expte"))
        m = RE_REFCAT.search(blob)
        if m:
            hit = self._fetch_parcel_geometry(m.group(1))
            if hit:
                geom, url = hit
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = url
                rec["coord_source"] = "portal_geometry_centroid"
                rec["geometry_crs"] = "EPSG:4326"
                centroid = geometry_centroid(geom)
                if centroid:
                    rec["lat"], rec["lon"] = centroid

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
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
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._apply_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = " ".join(
            str(row.get(k) or "")
            for k in ("titulo", "procedimiento", "categoria", "descripcion", "doc_label")
        )
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if row.get("categoria", "").lower() == "urbanismo":
            pass
        elif not RE_PROYECTO.search(blob):
            if row.get("categoria") != "Órganos de gobierno":
                if row.get("origen") != "transparencia":
                    return None
            if not re.search(r"(?i)pleno|convocatoria|acuerdo|ordenanza|urban", blob):
                return None
        tipo = "urbanismo"
        if re.search(r"(?i)informaci[oó]n p[uú]blica", blob):
            tipo = "información pública"
        elif re.search(r"(?i)planeamiento|estudio de detalle|plan (?:parcial|especial|general)", blob):
            tipo = "planeamiento"
        elif re.search(r"(?i)convocatoria.*pleno|acuerdo plenario|acta.*pleno", blob):
            tipo = "acuerdo plenario"
        elif re.search(r"(?i)convenio", blob):
            tipo = "convenio"
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha") or _fecha_from_blob(row["titulo"]),
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._apply_geometry(rec)
        return rec

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa de trámite; no concesión publicada en tablón",
            "origen": row.get("origen"),
        }
        self._apply_geometry(rec)
        return rec

    def _tramite_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        if RE_LICENCIA.search(row["titulo"]) and not re.search(
            r"(?i)planeam|actuaci[oó]n urban|modificaci[oó]n del planeamiento|certificado.*urban",
            row["titulo"],
        ):
            return None
        tipo = (
            "planeamiento"
            if re.search(r"(?i)planeam|actuaci[oó]n urban|certificado.*urban", row["titulo"])
            else "trámite urbanismo"
        )
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": None,
            "tipo": tipo,
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._apply_geometry(rec)
        return rec

    def _web_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or "documentación urbanismo",
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if "geoportal" in row["url"]:
            rec["origen"] = "geoportal_wfs"
        self._apply_geometry(rec)
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
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        for item in self._collect_tramites():
            rec = self._tramite_to_licencia(item)
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

        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_transparency():
            add(self._board_to_proyecto(item))
        for item in self._collect_tramites():
            add(self._tramite_to_proyecto(item))
        for item in self._collect_web_proyectos():
            add(self._web_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "info_tablon")),
            "tramites": sum(1 for r in rows if r.get("origen") == "catalogo_tramites"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "web": sum(1 for r in rows if r.get("origen") in ("web_municipal", "geoportal_wfs")),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        self.backfill_proyectos(out_jsonl)
        after = len(self._load_jsonl(out_jsonl))
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
