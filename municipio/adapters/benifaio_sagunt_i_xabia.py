from __future__ import annotations

import hashlib
import http.cookiejar
import json
import re
import ssl
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

ID_PREFIX = "benifaio-sagunt-i-xabia"
WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "InventarioSuSuz"

MUNICIPALITIES: list[dict[str, Any]] = [
    {
        "key": "benifaio",
        "nombre": "Benifaió",
        "ine": "46071",
        "centroid": [39.2842, -0.4250],
        "source": "espublico",
        "sede_base": "https://benifaio.sedelectronica.es",
        "board_url": "https://benifaio.sedelectronica.es/board",
    },
    {
        "key": "sagunt",
        "nombre": "Sagunt",
        "ine": "46220",
        "centroid": [39.6792, -0.2789],
        "source": "sedipualba",
        "sede_base": "https://sagunt.sedipualba.es",
        "tablon_rss": "https://sagunt.sedipualba.es/tablondeanuncios/tablon_rss.aspx",
        "web_base": "https://www.aytosagunto.es",
    },
    {
        "key": "xabia",
        "nombre": "Xàbia",
        "ine": "03094",
        "centroid": [38.7896, 0.1660],
        "source": "espublico",
        "web_base": "https://www.ajxabia.com",
        "sede_base": "https://xabia.sedelectronica.es",
        "board_url": "https://xabia.sedelectronica.es/board",
        "transparency_folders": [
            {
                "titulo": "7.1. Planeamiento Urbanístico",
                "url": "https://xabia.sedelectronica.es/transparency/fcfa421c-24d4-4865-8f58-3ea515cd827e/",
                "nota": "2741 documentos en portal transparencia (carga AJAX)",
            },
            {
                "titulo": "7.3. Normativa Urbanística y Planes Sectoriales",
                "url": "https://xabia.sedelectronica.es/transparency/fcfa421c-24d4-4865-8f58-3ea515cd827e/",
                "nota": "30 documentos en portal transparencia",
            },
            {
                "titulo": "7.4. Obras Públicas e Infraestructuras",
                "url": "https://xabia.sedelectronica.es/transparency/fcfa421c-24d4-4865-8f58-3ea515cd827e/",
                "nota": "24 documentos en portal transparencia",
            },
        ],
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|primera ocupaci[oó]n|informe urban|obra[s]? (?:major|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pge|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:de )?detalle|sector|ue-|sd-|suz|normativa urban|plantejament|"
    r"homologaci[oó]n|catalogo de protecc|cat[aà]leg de protecc|sequiar|pri\b|"
    r"reurbaniz|participaci[oó]n p[uú]blica|enajenaci[oó]n parcela|ordenanza urban)",
)
RE_NOISE = re.compile(
    r"(?i)(botella de|lata de|caja de cart|ivace|subvenci[oó]n.*empresarial|"
    r"seguretat i autoprotecci|urban q-?art|balneari|balneario|horts urbans|"
    r"huertos urbanos|selecci[oó]n de personal|empleo p[uú]blico|bop.*bases|"
    r"cobranza.*iae|pol[ií]gonos ivace|projectes 202[0-9]|proyectos 202[0-9]|"
    r"censo electoral|recaudatorio|padron|padr[oó]n|subvenci[oó]n|huerto urbano|"
    r"estructura de costes|peis |mercado exterior|cooperaci[oó] internacion|"
    r"d[ií]a municipal de la agricultura|prestaciones econ[oó]micas individualizadas|"
    r"pppnt ciclo integral del agua|corredor ferroviario)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://[^/]+\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


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
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "modificaci" in n and ("pgou" in n or "plan general" in n):
        return "modificación PGOU"
    if "plan parcial" in n or re.search(r"\bpp\b", n):
        return "plan parcial"
    if "plan especial" in n or "suz" in n:
        return "plan especial"
    if "informaci" in n or "exposici" in n or "consulta p" in n:
        return "información pública"
    if "pgou" in n or "planeam" in n or "pge" in n:
        return "planeamiento"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
    if "enajenaci" in n and "parcela" in n:
        return "enajenación suelo"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.strip().split()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lon = nums[i], nums[i + 1]
        ring.append([lon, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


class BenifaioSaguntIXabiaAyuntamientoAdapter(AyuntamientoAdapter):
    """Benifaió (espublico) + Sagunt (sedipualba) + Xàbia (espublico) + ICV WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or "https://benifaio.sedelectronica.es")
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.municipalities = list(self.config.get("municipalities") or MUNICIPALITIES)
        self._wfs_cache: dict[str, list[dict[str, Any]]] = {}
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

    def _collect_espublico_board(self, mun: dict[str, Any]) -> list[dict[str, Any]]:
        board_url = str(mun.get("board_url") or "")
        sede_base = str(mun.get("sede_base") or "").rstrip("/")
        if not board_url:
            return []
        try:
            html = self._fetch(board_url)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento", "Document"):
                continue

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else board_url
            if url.startswith("/"):
                url = f"{sede_base}{url}"

            titulo = cells.get("class_description") or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            expediente = cells.get("class_folderCode", "")
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"

            blob = " ".join(
                filter(
                    None,
                    [
                        documento,
                        expediente,
                        cells.get("class_folderName", ""),
                        cells.get("class_boardCategory", ""),
                        cells.get("class_description", ""),
                        title_m.group(1) if title_m else "",
                    ],
                )
            )
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120] or None,
                    "procedimiento": cells.get("class_folderName", "")[:200],
                    "fecha": _parse_fecha_dmy(cells.get("class_dateFrom", "")),
                    "url": url,
                    "blob": blob,
                    "origen": "tablon",
                    "municipio": mun["nombre"],
                    "mun_key": mun["key"],
                }
            )
        return rows

    def _collect_sedipualba_rss(self, mun: dict[str, Any]) -> list[dict[str, Any]]:
        rss_url = str(mun.get("tablon_rss") or "")
        if not rss_url:
            return []
        try:
            raw = self._fetch(rss_url, timeout=60)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            return []

        rows: list[dict[str, Any]] = []
        for item in root.findall(".//item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            if not title or not link:
                continue
            fecha = None
            if date_el is not None and date_el.text:
                try:
                    fecha = parsedate_to_datetime(date_el.text.strip()).strftime("%Y-%m-%d")
                except (TypeError, ValueError, IndexError):
                    fecha = None
            rows.append(
                {
                    "titulo": title[:500],
                    "url": link,
                    "fecha": fecha,
                    "blob": title,
                    "origen": "tablon_rss",
                    "municipio": mun["nombre"],
                    "mun_key": mun["key"],
                }
            )
        return rows

    def _collect_transparency_folders(self, mun: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for folder in mun.get("transparency_folders") or []:
            titulo = str(folder.get("titulo") or "").strip()
            url = str(folder.get("url") or "").strip()
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "blob": f"{titulo} {folder.get('nota', '')}",
                    "origen": "transparencia",
                    "municipio": mun["nombre"],
                    "mun_key": mun["key"],
                }
            )
        return rows

    def _parse_wfs_feature(self, feat_el: ET.Element, mun: dict[str, Any]) -> dict[str, Any] | None:
        props: dict[str, Any] = {}
        geom: dict[str, Any] | None = None
        for child in feat_el:
            tag = child.tag.split("}", 1)[-1]
            if tag == "msGeometry":
                for gchild in child.iter():
                    gtag = gchild.tag.split("}", 1)[-1]
                    if gtag == "posList" and gchild.text:
                        geom = _gml_poslist_to_polygon(gchild.text)
            elif child.text and tag not in {"boundedBy", "msGeometry"}:
                props[tag] = child.text.strip()
        if props.get("cod_ine_mun") != mun["ine"]:
            return None
        titulo = _strip_html(str(props.get("pp") or props.get("ue") or props.get("clasificacion") or ""))
        if not titulo:
            return None
        fecha = _parse_fecha_iso(str(props.get("f_aprob") or "")) or _parse_fecha_iso(
            str(props.get("f_public") or "")
        )
        key = f"{mun['key']}:wfs:{props.get('id') or titulo}"
        wfs_url = (
            f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
            f"&count=1&STARTINDEX=0"
        )
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": mun["nombre"],
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _proyecto_tipo(f"{titulo} {props.get('clasificacion', '')}"),
            "url": mun.get("web_base") or mun.get("sede_base") or self.base_url,
            "source": "ayuntamiento",
            "origen": "icv_wfs",
            "mun_key": mun["key"],
        }
        if geom:
            rec["geom_geojson"] = geom
            rec["geometry_source"] = "portal_wfs"
            rec["geometry_source_url"] = wfs_url
            rec["coord_source"] = "portal_geometry_centroid"
            centroid = geometry_centroid(geom)
            if centroid:
                rec["lat"], rec["lon"] = centroid
        return rec

    def _collect_wfs_proyectos(self, mun: dict[str, Any]) -> list[dict[str, Any]]:
        cache_key = str(mun["ine"])
        if cache_key in self._wfs_cache:
            return self._wfs_cache[cache_key]

        rows: list[dict[str, Any]] = []
        start = 0
        step = 200
        while True:
            url = (
                f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
                f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
                f"&count={step}&STARTINDEX={start}"
            )
            try:
                raw = self._fetch_bytes(url)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = [el for el in root if el.tag.endswith("member")]
            if not members:
                break
            for member in members:
                rec = self._parse_wfs_feature(member[0], mun)
                if rec:
                    rows.append(rec)
            start += step
            if len(members) < step:
                break

        self._wfs_cache[cache_key] = rows
        return rows

    def _enrich_geometry(self, rec: dict[str, Any], mun: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "").lower()
        for wfs_rec in self._collect_wfs_proyectos(mun):
            wfs_title = str(wfs_rec.get("titulo") or "").lower()
            if titulo and (titulo in wfs_title or wfs_title in titulo):
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

    def _apply_centroid(self, rec: dict[str, Any], mun: dict[str, Any]) -> None:
        if rec.get("lat") is not None and rec.get("lon") is not None:
            return
        centroid = mun.get("centroid")
        if isinstance(centroid, (list, tuple)) and len(centroid) >= 2:
            rec["lat"], rec["lon"] = float(centroid[0]), float(centroid[1])
            rec["coord_source"] = rec.get("coord_source") or "municipio_centroid"

    def _is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_NOISE.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = f"{row.get('mun_key')}:{row.get('expediente') or row['url']}"
        rec = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("procedimiento") or "licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "municipio": row.get("municipio"),
        }
        self._apply_centroid(rec, next(m for m in self.municipalities if m["key"] == row.get("mun_key")))
        return rec

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc:
            return None
        mun = next(m for m in self.municipalities if m["key"] == row.get("mun_key"))
        key = f"{row.get('mun_key')}:{row.get('expediente') or row['url']}"
        rec = {
            "id": _stable_id("proy", key),
            "municipio": row.get("municipio"),
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec, mun)
        self._apply_centroid(rec, mun)
        return rec

    def _transparency_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        mun = next(m for m in self.municipalities if m["key"] == row.get("mun_key"))
        key = f"{row.get('mun_key')}:transparency:{row.get('url') or row['titulo']}"
        rec = {
            "id": _stable_id("proy", key),
            "municipio": row.get("municipio"),
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(f"{row['titulo']} {row.get('blob', '')}"),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "transparencia",
        }
        self._enrich_geometry(rec, mun)
        self._apply_centroid(rec, mun)
        return rec

    def _licencia_info_pages(self, mun: dict[str, Any]) -> list[dict[str, Any]]:
        sede = str(mun.get("sede_base") or "").rstrip("/")
        board = mun.get("board_url") or f"{sede}/tablondeanuncios/" if mun.get("source") == "sedipualba" else mun.get("board_url")
        pages = [
            {
                "url": board or sede,
                "titulo": f"Tablón de anuncios — {mun['nombre']}",
                "tipo": "tablón licencias y urbanismo",
                "origen": "tablon_info",
            },
            {
                "url": f"{sede}/dossier" if mun.get("source") == "espublico" else f"{sede}/catalogoservicios.aspx",
                "titulo": f"Catálogo trámites urbanismo — {mun['nombre']}",
                "tipo": "catálogo trámites urbanismo",
                "origen": "sede_tramite",
            },
        ]
        rows: list[dict[str, Any]] = []
        for page in pages:
            rec = {
                "id": _stable_id("lic", f"{mun['key']}:{page['url']}"),
                "fecha_concesion": None,
                "tipo": page["tipo"],
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": page["titulo"],
                "url": page["url"],
                "source": "ayuntamiento",
                "origen": page["origen"],
                "municipio": mun["nombre"],
                "nota": "Sin listado histórico público de licencias concedidas",
            }
            self._apply_centroid(rec, mun)
            rows.append(rec)
        return rows

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
        for mun in self.municipalities:
            for rec in self._licencia_info_pages(mun):
                if rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
            tablon = (
                self._collect_espublico_board(mun)
                if mun.get("source") == "espublico"
                else self._collect_sedipualba_rss(mun)
            )
            for item in tablon:
                rec = self._board_to_licencia(item)
                if rec and rec["id"] not in seen:
                    seen.add(rec["id"])
                    rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for mun in self.municipalities:
            for rec in self._collect_wfs_proyectos(mun):
                add(rec)
            if mun.get("source") == "espublico":
                for item in self._collect_espublico_board(mun):
                    add(self._row_to_proyecto(item))
            elif mun.get("source") == "sedipualba":
                for item in self._collect_sedipualba_rss(mun):
                    add(self._row_to_proyecto(item))
            for item in self._collect_transparency_folders(mun):
                add(self._transparency_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "tablon_rss")),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
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
