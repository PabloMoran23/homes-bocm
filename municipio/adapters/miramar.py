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
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://ajumiramar.org"
SEDE_BASE = "https://miramar.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board/"
DOSSIER_URL = f"{SEDE_BASE}/dossier/.0"
MUNICIPIO = "Miramar"
ID_PREFIX = "miramar"
INE_MUN = "46154"

ICV_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
ICV_LAYER = "ms:InventarioSuSuz"

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ajuntament/serveis/urbanisme/",
    f"{WEB_BASE}/ajuntament/plans-municipals/pgou/",
    f"{WEB_BASE}/ajuntament/plans-municipals/pgou/modificaciones-pgou/",
    f"{WEB_BASE}/ajuntament/plans-municipals/pgou/planols-pgou/",
    f"{WEB_BASE}/ajuntament/plans-municipals/pgou/normes-urbanistiques-de-caracter-estructural/",
    f"{WEB_BASE}/ajuntament/plans-municipals/pgou/normes-urbanistiques-de-lordenacio-detallada/",
    f"{WEB_BASE}/ajuntament/sollicituds/",
    f"{WEB_BASE}/ajuntament/tauler-danuncis/edictes/",
]

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licència|llic[eè]ncia|declaraci[oó]n responsable|comunicaci[oó]n previa|"
    r"autorizaci[oó]n.*obra|primera ocupaci[oó]n|segunda ocupaci[oó]n|obra[s]? (?:major|menor)|"
    r"ocupaci[oó]n|segregaci[oó]n|certificat de compatibilitat|informe urban)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plantejament|plan (?:parcial|especial|general)|pgou|pgom|"
    r"informaci[oó]n p[uú]blica|expedient|proyecto|modificaci[oó]n|reparcel|"
    r"estudi(?:s)? (?:de )?detall|sector|ue[\-\s]*\d+|ais\s*\d+|in[\-\s]*\d+|"
    r"normes urban|ordenaci[oó]n|plano|planol|clasificaci[oó]n del suelo|"
    r"ordenanza.*vado|vado)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"cobranza iae|modificaci[oó]n de cr[eé]ditos|presupuest|subvenci[oó]n|"
    r"jurado|mercado estival|sorteo puestos|ordenanza fiscal|ibi\b|ivace)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://miramar\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_DOSSIER_LINK = re.compile(
    r'href="(https://miramar\.sedelectronica\.es/catalog/t/[a-f0-9\-]+)"[^>]*>([^<]{3,200})</a>',
    re.I,
)
RE_PDF_HREF = re.compile(
    r'href="((?:https://ajumiramar\.org)?/wp-content/uploads/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_SECTOR_TOKEN = re.compile(
    r"(?i)\b((?:UE|SD|PP|SECTOR|AIS|IN)[\s\-]?(?:IND\s*)?[\dA-ZÁÉÍÓÚ'._\-]+(?:[\s,\-yY/]+[\dA-ZÁÉÍÓÚ'._\-]+)*)\b",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

_GML_NS = {
    "gml": "http://www.opengis.net/gml",
    "ms": "http://mapserver.gis.umn.edu/mapserver",
    "wfs": "http://www.opengis.net/wfs/2.0",
}


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
    if "pgou" in n or "plan general" in n or "pla general" in n:
        return "PGOU"
    if "plan parcial" in n or re.search(r"\bsector\s*\d+", n):
        return "plan parcial"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "normes urban" in n or "normativa urban" in n:
        return "normativa urbanística"
    if "clasificaci" in n and "suelo" in n:
        return "clasificación del suelo"
    if "ordenanza" in n and "vado" in n:
        return "ordenanza vados"
    if re.search(r"\bue[\-\s]*\d+", n):
        return "unidad de ejecución"
    if re.search(r"\bais\s*\d+", n):
        return "ámbito de intervención sectorial"
    return "planeamiento"


def _sector_tokens(text: str) -> list[str]:
    tokens: list[str] = []
    for m in RE_SECTOR_TOKEN.finditer(text or ""):
        tok = _strip_html(m.group(1))
        if len(tok) >= 3:
            tokens.append(tok)
    return tokens


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    parts = [float(x) for x in poslist.split() if x.strip()]
    if len(parts) < 6:
        return None
    coords: list[list[float]] = []
    for i in range(0, len(parts) - 1, 2):
        lat, lon = parts[i], parts[i + 1]
        coords.append([lon, lat])
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _gml_feature_to_geojson(feat: ET.Element) -> dict[str, Any] | None:
    poly = feat.find(".//gml:Polygon", _GML_NS)
    if poly is None:
        return None
    pos = poly.find(".//gml:posList", _GML_NS)
    if pos is None or not (pos.text or "").strip():
        return None
    return _gml_poslist_to_polygon(pos.text.strip())


class MiramarAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress ajumiramar.org + sede espublico gestiona + ICV WFS InventarioSuSuz."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.dossier_url = str(self.config.get("dossier_url") or DOSSIER_URL)
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.icv_wfs_url = str(geom_cfg.get("wfs_url") or ICV_WFS).rstrip("/")
        self.icv_layer = str(geom_cfg.get("type_name") or ICV_LAYER)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or INE_MUN)
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
        self._wfs_by_key: dict[str, dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60, use_opener: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-miramar/1.0")},
        )
        if use_opener:
            with self._opener.open(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", unescape(href))

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

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (
            r'<h1[^>]*class="[^"]*entry-title[^"]*"[^>]*>([^<]+)',
            r"<h1[^>]*>([^<]+)",
            r"<title>([^<]+)",
        ):
            m = re.search(pat, html, re.I)
            if m:
                t = _strip_html(m.group(1))
                t = re.sub(r"\s*[-|].*Ajuntament.*$", "", t, flags=re.I).strip()
                if t and len(t) > 3:
                    return t[:500]
        return fallback

    def _collect_board(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.board_url, use_opener=True)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        for m in RE_BOARD_ROW.finditer(html):
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))

            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue

            expediente = cells.get("class_folderCode", "")
            procedimiento = cells.get("class_folderName", "")
            categoria = cells.get("class_boardCategory", "")
            descripcion = cells.get("class_description", "")
            fecha_raw = cells.get("class_dateFrom", "")

            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"

            titulo = descripcion or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            if expediente and expediente not in titulo and expediente != "Mis Documentos":
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
                    "blob": (
                        f"{documento} {expediente} {procedimiento} {categoria} "
                        f"{descripcion} {title_m.group(1) if title_m else ''}"
                    ),
                    "origen": "tablon",
                }
            )
        return rows

    def _collect_dossier_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.dossier_url, timeout=90, use_opener=True)
        except urllib.error.URLError:
            return []

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_DOSSIER_LINK.findall(html):
            url = href.strip()
            titulo = _strip_html(title)
            if url in seen:
                continue
            seen.add(url)
            rows.append({"titulo": titulo, "url": url, "origen": "sede_tramite"})
        return rows

    def _collect_wordpress_pages(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_urls: set[str] = set()

        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue

            title = self._page_title(html, page_url.rsplit("/", 2)[-2].replace("-", " "))
            if page_url not in seen_urls:
                seen_urls.add(page_url)
                rows.append(
                    {
                        "titulo": title,
                        "url": page_url,
                        "fecha": _fecha_from_blob(html) or _fecha_from_blob(title),
                        "origen": "wordpress_pagina",
                    }
                )

            for pdf_m in RE_PDF_HREF.finditer(html):
                pdf_url = self._abs_web(pdf_m.group(1))
                if pdf_url in seen_urls:
                    continue
                seen_urls.add(pdf_url)
                pdf_name = urllib.parse.unquote(pdf_url.rsplit("/", 1)[-1])
                pdf_title = re.sub(r"[_\-]+\.(pdf|PDF)$", "", pdf_name).replace("_", " ").replace("-", " ")
                rows.append(
                    {
                        "titulo": f"{title} — {pdf_title}"[:500],
                        "url": pdf_url,
                        "fecha": _fecha_from_blob(pdf_name) or _fecha_from_blob(title),
                        "origen": "wordpress_pdf",
                        "parent_url": page_url,
                    }
                )
        return rows

    def _wfs_page_url(self, start: int) -> str:
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.icv_layer,
                "count": "200",
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "STARTINDEX": str(start),
            }
        )
        return f"{self.icv_wfs_url}?{params}"

    def _collect_icv_wfs(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache

        rows: list[dict[str, Any]] = []
        start = 0
        while start < 9000:
            url = self._wfs_page_url(start)
            try:
                raw = self._fetch(url, timeout=90)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", _GML_NS)
            if not members:
                break
            page_hits = 0
            for member in members:
                feat = member.find("ms:InventarioSuSuz", _GML_NS)
                if feat is None:
                    continue
                cod = feat.findtext("ms:cod_ine_mun", default="", namespaces=_GML_NS)
                if cod != self.cod_ine_mun:
                    continue
                page_hits += 1
                fid = feat.findtext("ms:id", default="", namespaces=_GML_NS) or ""
                pp = _strip_html(feat.findtext("ms:pp", default="", namespaces=_GML_NS) or "")
                ue = _strip_html(feat.findtext("ms:ue", default="", namespaces=_GML_NS) or "")
                clas = _strip_html(feat.findtext("ms:clasificacion", default="", namespaces=_GML_NS) or "")
                f_aprob = feat.findtext("ms:f_aprob", default="", namespaces=_GML_NS) or None
                titulo = pp
                if ue and ue not in titulo:
                    titulo = f"{pp} ({ue})" if pp else ue
                if not titulo:
                    titulo = f"Sector {fid}"
                geom = _gml_feature_to_geojson(feat)
                rec: dict[str, Any] = {
                    "titulo": titulo[:500],
                    "fecha": f_aprob,
                    "url": url,
                    "tipo": "sector SU/SUZ" if clas else "sector planeamiento",
                    "clasificacion": clas or None,
                    "pp": pp or None,
                    "ue": ue or None,
                    "wfs_id": fid,
                    "origen": "icv_wfs",
                }
                if geom:
                    rec["geom_geojson"] = geom
                    rec["geometry_source"] = "portal_wfs"
                    rec["geometry_source_url"] = url
                    rec["coord_source"] = "portal_geometry_centroid"
                    centroid = geometry_centroid(geom)
                    if centroid:
                        rec["lat"], rec["lon"] = centroid
                rows.append(rec)
            if page_hits == 0 and start > 7000:
                break
            start += 200

        self._wfs_cache = rows
        self._wfs_by_key = {}
        for rec in rows:
            for key in (rec.get("titulo") or "", rec.get("pp") or "", rec.get("ue") or ""):
                low = str(key).lower().strip()
                if low:
                    self._wfs_by_key[low] = rec
            for tok in _sector_tokens(rec.get("titulo") or ""):
                self._wfs_by_key[tok.lower()] = rec
        return rows

    def _match_wfs(self, text: str) -> dict[str, Any] | None:
        if self._wfs_by_key is None:
            self._collect_icv_wfs()
        low = (text or "").lower()
        best: dict[str, Any] | None = None
        best_len = 0
        for key, rec in (self._wfs_by_key or {}).items():
            if len(key) >= 4 and key in low and len(key) > best_len:
                best = rec
                best_len = len(key)
        if best:
            return best
        for tok in _sector_tokens(text):
            hit = (self._wfs_by_key or {}).get(tok.lower())
            if hit:
                return hit
        return None

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = " ".join(str(rec.get(k) or "") for k in ("titulo", "descripcion", "pp", "ue", "documento"))
        hit = self._match_wfs(blob)
        if not hit:
            return
        for key in ("geom_geojson", "geometry_source", "geometry_source_url", "coord_source", "lat", "lon"):
            if hit.get(key) is not None:
                rec[key] = hit[key]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        cat = (row.get("categoria") or "").lower()
        proc = (row.get("procedimiento") or "").lower()
        if "urban" in cat or "ordenanza" in cat:
            return True
        if any(k in proc for k in ("urban", "licencia", "ocupaci", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_LICENCIA.search(row["titulo"]):
            return None
        return {
            "id": _stable_id("lic", row["url"]),
            "fecha_concesion": None,
            "tipo": "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": "Página informativa sede espublico; sin registro público de concesiones",
            "origen": row.get("origen"),
        }

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        tipo = row.get("procedimiento") or "licencia"
        if "ocupaci" in proc:
            tipo = "licencia de ocupación"
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": tipo,
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._attach_geometry(rec)
        return rec

    def _to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        blob = row.get("titulo") or ""
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("wfs_id") or row["url"]),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        for key in (
            "pp",
            "ue",
            "clasificacion",
            "wfs_id",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "coord_source",
            "lat",
            "lon",
            "parent_url",
        ):
            if row.get(key) is not None:
                rec[key] = row[key]
        self._attach_geometry(rec)
        return rec

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob) and "urban" not in (row.get("categoria") or "").lower():
            if row.get("origen") != "wordpress_pdf" and row.get("origen") != "wordpress_pagina":
                return None
        if row.get("origen") == "wordpress_pagina":
            low = (row.get("titulo") or "").lower()
            if not any(k in low for k in ("urban", "pgou", "plan", "norm", "sollicitud", "edict")):
                if "pgou" not in row.get("url", "").lower() and "urban" not in row.get("url", "").lower():
                    return None
        return self._to_proyecto(row)

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in self._collect_dossier_tramites():
            rec = self._tramite_to_licencia(item)
            if rec and rec["id"] not in seen:
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
            "tramites": sum(1 for r in rows if r.get("origen") == "sede_tramite"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        result = self.backfill_licencias(out_jsonl)
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

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_icv_wfs():
            add(self._to_proyecto(item))
        for item in self._collect_wordpress_pages():
            add(self._row_to_proyecto(item))
        for item in self._collect_board():
            add(self._row_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "icv_wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "wordpress": sum(1 for r in rows if str(r.get("origen", "")).startswith("wordpress")),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
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
                    "with_geometry": result.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok", **result}
