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

WEB_BASE = "https://lalcora.es"
SEDE_BASE = "https://lalcora.sedelectronica.es"
BOARD_URL = f"{SEDE_BASE}/board"
TRANSPARENCY_URL = f"{SEDE_BASE}/transparency"
URBANISMO_URL = f"{WEB_BASE}/arees-i-serveis-municipals/urbanisme/"
MUNICIPIO = "L'Alcora"
ID_PREFIX = "l-alcora"
WFS_BASE = "https://terramapas.icv.gva.es/0702_Planeamiento"
WFS_TYPE = "InventarioSuSuz"
INE_MUN = "12011"

DEFAULT_TRANSPARENCY_FOLDERS: list[dict[str, str]] = [
    {
        "titulo": "7. URBANISME, OBRES PÚBLIQUES I MEDI AMBIENT",
        "url": TRANSPARENCY_URL,
        "nota": "216 documentos en portal transparencia (carga AJAX Wicket)",
    },
]

POST_SITEMAPS: tuple[str, ...] = (
    f"{WEB_BASE}/post-sitemap.xml",
    f"{WEB_BASE}/post-sitemap2.xml",
)

POST_KEYWORDS: tuple[str, ...] = (
    "pgou",
    "planeam",
    "modificaci",
    "informaci",
    "dogv",
    "sector",
    "licenc",
    "llicenc",
    "expedient",
    "unidad",
    "reparcel",
    "parquing",
    "norma urban",
    "urbanisme",
    "planejament",
)

POST_EXCLUDE: tuple[str, ...] = (
    "beca de formaci",
    "beca formaci",
    "concurs de fotografia",
    "escola d'estiu",
    "piscines municipals",
    "itv",
)

RE_LICENCIA = re.compile(
    r"(?i)(solicitud de licencia|licencia(?:s)?(?: de)?(?: obra| urban| municipal| de actividad)?|"
    r"llic[eè]ncia|notificaci[oó]n.*licencia|edicto.*(?:licencia|actividad)|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"obra (?:mayor|menor))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|edicto|"
    r"reparcel|estudio de detalle|modificaci[oó]n|sector|normativa urban|"
    r"obres p[uú]bliques|infraestructur|suz|sua|pp\s*\d|pau\s*\d|"
    r"concessi[oó] demanial|certificat.*urban|visor|parquing|planejament)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|plaza de|empleo p[uú]blico|"
    r"cobranza|iae|ibi|vados|notificaci[oó]n deudas|liquidaci[oó]n tributaria|"
    r"subvenci[oó]n|concurs albaes|cadafals|festes)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://lalcora\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_ISO = re.compile(r"\b((?:19|20)\d{2})-(\d{2})-(\d{2})\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SECTOR = re.compile(
    r"(?i)\b(?:sector|ue|sua|suz|agr[ií]cola|barranc|monte|pont|playa)\s*[\w\s-]{0,30}"
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


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "plan especial" in n or "suz" in n:
        return "plan especial"
    if "plan parcial" in n or re.search(r"\bpp\s*\d", n):
        return "plan parcial"
    if "sua" in n and "sector" in n:
        return "sector urbanizable"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "pgou" in n or "planeam" in n or "modificaci" in n:
        return "planeamiento"
    if "licencia" in n or "llic" in n:
        return "licencia publicada"
    if "parquing" in n or "obra" in n:
        return "obra urbanística"
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


class LAlcoraAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress lalcora.es + sede espublico gestiona + ICV InventarioSuSuz WFS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or BOARD_URL)
        self.transparency_folders: list[dict[str, str]] = list(
            self.config.get("transparency_folders") or DEFAULT_TRANSPARENCY_FOLDERS
        )
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
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

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-l-alcora/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_bytes(self, url: str, *, timeout: int = 90) -> bytes:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-l-alcora/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read()

    def _collect_board(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen_docs: set[str] = set()
        for page in range(1, 25):
            url = self.board_url if page == 1 else f"{self.board_url}?page={page}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            page_rows = 0
            for m in RE_BOARD_ROW.finditer(html):
                row_html = m.group(0)
                cells: dict[str, str] = {}
                for cm in RE_BOARD_CELL.finditer(row_html):
                    cells[cm.group(1)] = _strip_html(cm.group(2))

                documento = cells.get("class_name", "")
                if not documento or documento in ("Documento",) or documento in seen_docs:
                    continue
                seen_docs.add(documento)
                page_rows += 1

                expediente = cells.get("class_folderCode", "")
                procedimiento = cells.get("class_folderName", "")
                categoria = cells.get("class_boardCategory", "")
                descripcion = cells.get("class_description", "")
                fecha_raw = cells.get("class_dateFrom", "")

                preview_m = RE_PREVIEW_LINK.search(row_html)
                title_m = re.search(r'title="([^"]+)"', row_html)
                doc_url = preview_m.group(1) if preview_m else self.board_url
                if doc_url.startswith("/"):
                    doc_url = f"{self.sede_base}{doc_url}"

                titulo = descripcion or documento
                if title_m and title_m.group(1).strip():
                    titulo = title_m.group(1).strip()
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
                        "url": doc_url,
                        "blob": (
                            f"{documento} {expediente} {procedimiento} {categoria} "
                            f"{descripcion} {title_m.group(1) if title_m else ''}"
                        ),
                    }
                )
            if page_rows == 0:
                break
        return rows

    def _collect_transparency_folders(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for folder in self.transparency_folders:
            titulo = str(folder.get("titulo") or "").strip()
            url = str(folder.get("url") or TRANSPARENCY_URL).strip()
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo[:500],
                    "fecha": _fecha_from_blob(titulo),
                    "url": url,
                    "procedimiento": "planeamiento urbanístico",
                    "blob": f"{titulo} {folder.get('nota', '')}",
                    "origen": "transparencia",
                }
            )
        return rows

    def _post_url_relevant(self, url: str) -> bool:
        low = url.lower()
        if not any(k in low for k in POST_KEYWORDS):
            return False
        return not any(ex in low for ex in POST_EXCLUDE)

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sitemap_url in POST_SITEMAPS:
            try:
                xml = self._fetch(sitemap_url, timeout=30)
            except urllib.error.URLError:
                continue
            for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
                if not self._post_url_relevant(loc) or loc in seen:
                    continue
                seen.add(loc)
                try:
                    html = self._fetch(loc, timeout=30)
                except urllib.error.URLError:
                    continue
                title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
                titulo = _strip_html(title_m.group(1)) if title_m else loc
                titulo = re.sub(r"\s*-\s*Ajuntament.*$", "", titulo, flags=re.I).strip()
                if not RE_PROYECTO.search(titulo) and not RE_LICENCIA.search(titulo):
                    continue
                fecha = None
                for pat in (
                    r'datetime="(\d{4}-\d{2}-\d{2})"',
                    r'property="article:published_time"\s+content="(\d{4}-\d{2}-\d{2})"',
                ):
                    fm = re.search(pat, html, re.I)
                    if fm:
                        fecha = fm.group(1)
                        break
                if not fecha:
                    fecha = _fecha_from_blob(titulo)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": fecha,
                        "url": loc,
                        "blob": titulo,
                        "origen": "wp_noticia",
                    }
                )
        return rows

    def _collect_urbanismo_seed(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        try:
            html = self._fetch(URBANISMO_URL)
        except urllib.error.URLError:
            return rows
        rows.append(
            {
                "titulo": "Àrea d'Urbanisme — Ajuntament de l'Alcora",
                "fecha": None,
                "url": URBANISMO_URL,
                "blob": "urbanisme planejament pgou",
                "origen": "urbanismo_page",
            }
        )
        for href in re.findall(r'href="(https://lalcora\.es/[^"#?]+)"', html, re.I):
            if href == URBANISMO_URL:
                continue
            if not any(
                k in href.lower()
                for k in ("urbanisme", "pgou", "planeam", "parquing", "modificaci")
            ):
                continue
            if href in {r["url"] for r in rows}:
                continue
            rows.append(
                {
                    "titulo": unescape(urllib.parse.unquote(Path(href).name.replace("-", " ")))[:500],
                    "fecha": _fecha_from_blob(href),
                    "url": href,
                    "blob": href,
                    "origen": "urbanismo_link",
                }
            )
        return rows

    def _parse_wfs_feature(self, feat_el: ET.Element) -> dict[str, Any] | None:
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
        if props.get("cod_ine_mun") != self.ine_mun:
            return None
        pp = str(props.get("pp") or "").strip()
        ue = str(props.get("ue") or "").strip()
        clas = str(props.get("clasificacion") or "").strip()
        titulo = _strip_html(pp or ue or clas)
        if not titulo:
            return None
        if ue and ue not in titulo:
            titulo = f"{titulo} — {ue}".strip(" —")
        fecha = _parse_fecha_iso(str(props.get("f_aprob") or "")) or _parse_fecha_iso(
            str(props.get("f_public") or "")
        )
        key = str(props.get("id") or titulo)
        wfs_url = (
            f"{self.wfs_base}?service=WFS&version=2.0.0&request=GetFeature"
            f"&typename={self.wfs_type}&outputFormat=GML3&srsName=EPSG:4326"
            f"&count=1&STARTINDEX=0"
        )
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"wfs:{key}"),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": fecha,
            "tipo": _proyecto_tipo(f"{titulo} {clas}"),
            "url": (
                f"https://visor.gva.es/visor/?capas=spaicv0702_inventario_su_suz"
                f"#municipio={urllib.parse.quote(MUNICIPIO)}"
            ),
            "source": "ayuntamiento",
            "origen": "icv_wfs",
            "clasificacion": clas or None,
            "uso": props.get("uso"),
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

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
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
                feat_el = member[0]
                rec = self._parse_wfs_feature(feat_el)
                if rec:
                    rows.append(rec)
            start += step
            if len(members) < step:
                break
        self._wfs_cache = rows
        return rows

    def _match_wfs_title(self, title: str, wfs_title: str) -> bool:
        a = re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()
        b = re.sub(r"[^a-z0-9]+", " ", (wfs_title or "").lower()).strip()
        if not a or not b:
            return False
        if a in b or b in a:
            return True
        for token in re.findall(r"[a-z]{4,}", a):
            if token in b and token not in {"sector", "alcora", "lalcora", "urban", "planeam"}:
                return True
        return False

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        titulo = str(rec.get("titulo") or "")
        titulo_low = titulo.lower()
        candidates: list[tuple[float, dict[str, Any]]] = []
        for wfs_rec in self._collect_wfs_proyectos():
            wfs_title = str(wfs_rec.get("titulo") or "")
            score = 0.0
            if self._match_wfs_title(titulo, wfs_title):
                score += 30
            for m in RE_SECTOR.finditer(titulo):
                if m.group(0).lower() in wfs_title.lower():
                    score += 25
            if "agrícola" in titulo_low and "agr" in wfs_title.lower():
                score += 20
            if score >= 20:
                candidates.append((score, wfs_rec))
        if not candidates:
            return
        candidates.sort(key=lambda x: -x[0])
        wfs_rec = candidates[0][1]
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

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica L'Alcora",
                "url": self.board_url,
                "source": "ayuntamiento",
                "nota": "Anuncios y exposiciones públicas (espublico gestiona)",
                "origen": "sede_tablon",
            },
            {
                "id": _stable_id("lic", f"{self.sede_base}/dossier"),
                "fecha_concesion": None,
                "tipo": "catálogo trámites urbanismo",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Catálogo de trámites — licencias y comunicaciones previas",
                "url": f"{self.sede_base}/dossier",
                "source": "ayuntamiento",
                "nota": "Licencias de obra vía sede; sin histórico público de concesiones",
                "origen": "sede_tramite",
            },
        ]

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra", "certificad")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
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
            "origen": "tablon",
        }

    def _row_to_proyecto(self, row: dict[str, Any], *, origen: str) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("url") or row.get("titulo") or origen
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"{origen}:{key}"),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url") or URBANISMO_URL,
            "source": "ayuntamiento",
            "origen": origen,
        }
        if row.get("expediente"):
            rec["expte"] = row["expediente"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        proc = (row.get("procedimiento") or "").lower()
        if not RE_PROYECTO.search(blob) and "planeamiento" not in proc and "urban" not in proc:
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
            "origen": "tablon",
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
            "info": sum(1 for r in rows if r.get("origen") in ("sede_tablon", "sede_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_board():
            rec = self._board_to_licencia(item)
            if rec:
                existing[rec["id"]] = rec
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {
                    "last_run": datetime.now(timezone.utc).isoformat(),
                    "count": len(rows),
                    "added": max(0, len(rows) - before),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": max(0, len(rows) - before), "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for item in self._collect_board():
            add(self._board_to_proyecto(item))
        for item in self._collect_transparency_folders():
            add(self._row_to_proyecto(item, origen="transparencia"))
        for item in self._collect_wp_posts():
            add(self._row_to_proyecto(item, origen="wp_noticia"))
        for item in self._collect_urbanismo_seed():
            add(self._row_to_proyecto(item, origen=item.get("origen", "urbanismo")))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs": sum(1 for r in rows if r.get("origen") == "icv_wfs"),
            "tablon": sum(1 for r in rows if r.get("origen") == "tablon"),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia"),
            "wp": sum(1 for r in rows if r.get("origen") == "wp_noticia"),
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
        return {"rows": after, "added": max(0, after - before), "status": "ok", **stats}
