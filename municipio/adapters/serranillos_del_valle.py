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
from municipio.gis.sitcm import (
    WFS_BASE,
    _merge_geometries,
    resolve_ambito_geometry,
    resolve_municipio_wfs,
)

WP_BASE = "https://www.serranillosdelvalle.es"
SEDE_BASE = "https://sede.serranillosdelvalle.es/eAdmin"
MUNICIPIO = "Serranillos del Valle"
ID_PREFIX = "serranillos-del-valle"

TABLON_URL = f"{SEDE_BASE}/Tablon.do?action=verAnuncios&tipoTablon=1"
NORMATIVA_URL = f"{WP_BASE}/normativa/"
DOCUMENTS_URL = f"{WP_BASE}/documents/"
SITCM_VISOR_URL = "https://www.madrid.org/cartografia/sitcm/html/visor.htm"

WFS_TYPE = "sitcm:VPLA_V_AMBITO"
WFS_MUNICIPIO = "SERRANILLOS DEL VALLE"

DEFAULT_SEED_PAGES: list[str] = [
    NORMATIVA_URL,
    DOCUMENTS_URL,
]

RE_TABLON_ROW = re.compile(
    r"<tr>\s*<td[^>]*>.*?verAnuncio&id=([A-F0-9]+).*?"
    r"</td>\s*<td[^>]*>\s*(.*?)\s*<br>.*?"
    r"Periodo:</span>\s*([^<]+)</td>",
    re.I | re.S,
)
RE_DOC_TOKEN = re.compile(r"abrirOriginal\('([^']+)'\)")
RE_PERIOD = re.compile(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})")
RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia (?:de |urban|municipal)|"
    r"notificaci[oó]n.*licencia|edicto.*licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|nnss|normas urban|"
    r"informaci[oó]n p[uú]blica|expediente|reparcel|aprobaci[oó]n|certificado|avance|"
    r"modificaci[oó]n|estudio (?:ac[uú]stico|ambiental)|memoria|bocm|edicto|"
    r"convenio|parcela|suelo|suz[\.\-\s]|plan sector)",
)
RE_EXCLUDE = re.compile(
    r"(?i)(campamento urbano|casco urbano|concurso de paellas|carnaval|becas de ingl[eé]s|"
    r"juez de paz|bolsa de empleo|ayudas.*deportiv|quioscos municipales|autos locos)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads)/(\d{4})/(\d{2})/")
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", " ", text or "")).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _pdf_url(sede_base: str, token: str) -> str:
    return (
        f"{sede_base.rstrip('/')}/ValidarDocumento.do?"
        f"id_Documento={urllib.parse.quote(token, safe='')}&tipo=doc&mode=ori"
    )


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "certificado" in n or "avance" in n:
        return "certificado aprobación"
    if "normas urban" in n or "pgou" in n or "memoria" in n:
        return "planeamiento"
    if "plan parcial" in n or "sector" in n or "suz" in n:
        return "planeamiento"
    if "informaci" in n:
        return "información pública"
    if "aprobaci" in n:
        return "aprobación"
    return "urbanismo"


class SerranillosDelValleAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress TownPress (lsvr_document) + sede eAdmin tablón + SITCM WFS (partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.wp_base = str(self.config.get("wp_base") or WP_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_url = str(geom_cfg.get("wfs_url") or WFS_BASE)
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.wfs_municipio = str(geom_cfg.get("municipio_filter") or WFS_MUNICIPIO)
        self._wfs_municipio_resolved: str | None = None

    def _fetch(self, url: str, data: bytes | None = None) -> str:
        time.sleep(self.delay_s)
        headers = {
            "User-Agent": self.config.get("user_agent", "poc-bocm-serranillos-del-valle/1.0"),
        }
        if data is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset()
            if not charset:
                charset = "iso-8859-1" if "eAdmin" in url or "sede." in url else "utf-8"
            return raw.decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _municipio_wfs(self) -> str:
        if self._wfs_municipio_resolved is None:
            self._wfs_municipio_resolved = (
                resolve_municipio_wfs(self.wfs_municipio) or self.wfs_municipio
            )
        return self._wfs_municipio_resolved

    def _parse_tablon_html(self, html: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TABLON_ROW.finditer(html):
            ann_id, title_raw, period_raw = m.groups()
            title = _strip_html(title_raw)
            if not title:
                continue
            row_html = m.group(0)
            doc_m = RE_DOC_TOKEN.search(row_html)
            period_m = RE_PERIOD.search(period_raw or "")
            fecha_ini = _parse_fecha_dmy(period_m.group(1)) if period_m else None
            detail_url = f"{self.sede_base}/Tablon.do?action=verAnuncio&id={ann_id}"
            rec: dict[str, Any] = {
                "ann_id": ann_id,
                "titulo": title[:500],
                "fecha": fecha_ini,
                "url": detail_url,
                "origen": "tablon_sede",
            }
            if doc_m:
                rec["pdf_url"] = _pdf_url(self.sede_base, doc_m.group(1))
            rows.append(rec)
        return rows

    def _collect_tablon(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url)
        except urllib.error.URLError:
            return []
        return self._parse_tablon_html(html)

    def _collect_lsvr_documents(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 1
        while page <= 5:
            url = (
                f"{self.wp_base}/wp-json/wp/v2/lsvr_document"
                f"?per_page=100&page={page}&_fields=id,link,title,date,slug"
            )
            try:
                docs = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(docs, list) or not docs:
                break
            for doc in docs:
                if not isinstance(doc, dict):
                    continue
                title = str((doc.get("title") or {}).get("rendered") or "").strip()
                link = str(doc.get("link") or "").strip()
                fecha = _iso_date_wp(str(doc.get("date") or ""))
                if not title or not link:
                    continue
                try:
                    html = self._fetch(link)
                except urllib.error.URLError:
                    html = ""
                pdfs = RE_PDF_HREF.findall(html)
                if pdfs:
                    for pdf in pdfs:
                        pdf_url = urllib.parse.urljoin(link, pdf)
                        rows.append(
                            {
                                "titulo": f"{title} — {Path(pdf_url).name}"[:500],
                                "fecha": fecha or _fecha_from_url(pdf_url),
                                "url": link,
                                "pdf_url": pdf_url,
                                "origen": "lsvr_document",
                            }
                        )
                else:
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": fecha,
                            "url": link,
                            "origen": "lsvr_document",
                        }
                    )
            if len(docs) < 100:
                break
            page += 1
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        tramites = [
            (
                f"{self.sede_base}/Registrar.do?action=inicioPortalTramites",
                "trámites sede electrónica",
                "Portal de trámites — sede electrónica",
            ),
            (
                "https://sede.serranillosdelvalle.es/Formularios/Sol-Lic-Urbanist-2022.pdf",
                "solicitud licencia urbanística",
                "Formulario solicitud licencia urbanística",
            ),
            (
                "https://sede.serranillosdelvalle.es/Formularios/DEC-RESP-OBRAS.pdf",
                "declaración responsable obras",
                "Declaración responsable de obras",
            ),
            (
                self.tablon_url,
                "tablón de anuncios",
                "Tablón de anuncios — sede electrónica",
            ),
            (
                NORMATIVA_URL,
                "normativa urbanística",
                "Normativa municipal (PGOU / normas urbanísticas)",
            ),
        ]
        rows: list[dict[str, Any]] = []
        for url, tipo, titulo in tramites:
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": tipo,
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa; concesiones publicadas en tablón cuando proceda",
                    "origen": "sede_tramite",
                }
            )
        return rows

    def _wfs_query(self, cql: str, count: int = 50) -> list[dict[str, Any]]:
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
        return [f for f in (data.get("features") or []) if isinstance(f, dict)]

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom, meta = resolve_ambito_geometry(self._municipio_wfs(), rec.get("titulo") or "")
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = (
                f"{self.wfs_url}?service=WFS&request=GetFeature&typeName={self.wfs_type}"
            )
            rec["coord_source"] = "portal_geometry_centroid"
            if meta.get("ambito_name"):
                rec["ambito_sit"] = meta["ambito_name"]
            cen = geometry_centroid(geom)
            if cen:
                rec.setdefault("lat", cen[0])
                rec.setdefault("lon", cen[1])

    def _collect_sit_ambitos(self) -> list[dict[str, Any]]:
        muni = self._municipio_wfs().replace("'", "''")
        feats = self._wfs_query(f"DS_MUNICIPIO='{muni}'", count=120)
        by_name: dict[str, dict[str, Any]] = {}
        for f in feats:
            name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "").strip()
            if name:
                by_name[name] = f
        rows: list[dict[str, Any]] = []
        for name, feat in by_name.items():
            props = feat.get("properties") or {}
            fig = str(props.get("DS_FIG_DES") or props.get("DS_CLAS_SUE") or "").strip()
            titulo = f"{name} — {fig}" if fig else name
            merged = _merge_geometries([feat])
            rec: dict[str, Any] = {
                "id": _stable_id("proy", f"sit:{name}"),
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": _proyecto_tipo(name),
                "url": SITCM_VISOR_URL,
                "source": "ayuntamiento",
                "origen": "sit_wfs",
                "ambito_sit": name,
            }
            if merged:
                rec["geom_geojson"] = merged
                rec["geometry_source"] = "portal_wfs"
                cql = (
                    f"DS_MUNICIPIO='{muni}' "
                    f"AND DS_NOMB_AMB='{name.replace(chr(39), chr(39)*2)}'"
                )
                rec["geometry_source_url"] = (
                    f"{self.wfs_url}?service=WFS&request=GetFeature&CQL_FILTER={urllib.parse.quote(cql)}"
                )
                rec["coord_source"] = "portal_geometry_centroid"
                cen = geometry_centroid(merged)
                if cen:
                    rec["lat"], rec["lon"] = cen
            rows.append(rec)
        return rows

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if RE_EXCLUDE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("ann_id") or row["url"] + "|" + blob
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": blob[:500],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("titulo") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("ann_id") or row["url"]
        return {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": blob[:500],
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": "tablon_sede",
        }

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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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
        for item in self._collect_tablon():
            rec = self._tablon_to_licencia(item)
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

        for item in self._collect_lsvr_documents():
            add(self._row_to_proyecto(item))
        for item in self._collect_tablon():
            add(self._row_to_proyecto(item))
        for rec in self._collect_sit_ambitos():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "lsvr_docs": sum(1 for r in rows if r.get("origen") == "lsvr_document"),
            "tablon_items": sum(1 for r in rows if r.get("origen") == "tablon_sede"),
            "sit_wfs": sum(1 for r in rows if r.get("origen") == "sit_wfs"),
            "with_geometry": sum(1 for r in rows if record_geometry(r)),
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
