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

BASE = "https://burriana.es"
SEDE_BASE = "https://burriana.sedelectronica.es"
MUNICIPIO = "Burriana"
ID_PREFIX = "burriana"
INE_COD_MUN = "12039"

PGOU_URL = f"{BASE}/ayuntamiento/normativa/plan-general-de-ordenacion-urbana/"
URBANISMO_URL = f"{BASE}/servicios-municipales/urbanismo/"
TABLON_ORDENACION = f"{BASE}/ayuninf/tablon/ORDENACION/"

DIPCAS_API = (
    "https://dipcas.opendatasoft.com/api/explore/v2.1/catalog/datasets/"
    "planeamiento-urbanistico/records"
)
GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_TYPE = "Planeamiento.Zonificacion"

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|inicio de obra)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pai|p\.a\.i|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"aprobaci[oó]n|unidad(?:es)? de ejecuci[oó]n|\bue[\s-]|sector|urbanizaci[oó]n|"
    r"colector|normas subsidiarias|edusi|puep|plan especial|casco hist[oó]rico|"
    r"gesti[oó]n directa|cam[ií] xamussa|sant gregori|serratella|artelina|"
    r"ca[nñ]ada blanch|villa f[aá]tima|zona mar[ií]tima)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"modificaci[oó]n de cr[eé]ditos|notar[ií]a|teatro pay)",
)
RE_BOARD_ROW = re.compile(r"<tr[^>]*>\s*<td class=\"class_name\".*?</tr>", re.I | re.S)
RE_BOARD_CELL = re.compile(r'class="(class_[^"]+)"[^>]*>(.*?)</td>', re.I | re.S)
RE_PREVIEW_LINK = re.compile(
    r'href="((?:https://burriana\.sedelectronica\.es)?/preview-document/[a-f0-9-]+)"',
    re.I,
)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads|ayuninf)/(\d{4})[./-](\d{2})[./-]")
RE_UE_CODE = re.compile(r"(?i)\b(UE[\s-][A-Z0-9./-]+|PAI[\s«\"][^»\"]+|sector[\s-][\w\s-]+)")
RE_DIR_LINK = re.compile(r'href="([^"]+)"[^>]*>([^<]+)</a>', re.I)


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if not m:
        return None
    try:
        return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pai" in n or "programa de actuaci" in n:
        return "PAI"
    if re.search(r"\bue[\s-]", n) or "unidad de ejecuci" in n:
        return "unidad de ejecución"
    if "reparcel" in n:
        return "reparcelación"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "plan especial" in n or "puep" in n:
        return "plan especial"
    if "pgou" in n or "normas subsidiarias" in n or "plan general" in n:
        return "planeamiento"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "colector" in n or "urbanizaci" in n:
        return "obra urbanística"
    if "licita" in n or "adjudica" in n:
        return "contratación obra"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lat, lng = nums[i], nums[i + 1]
        ring.append([lng, lat])
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def _merge_geometries(geoms: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for g in geoms:
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


class BurrianaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress burriana.es + tablón espublico + DipCAS/GVA WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.board_url = str(self.config.get("board_url") or f"{self.sede_base}/board")
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._jar),
            urllib.request.HTTPSHandler(context=self._ssl_ctx),
        )
        self._geom_cache: list[dict[str, Any]] | None = None
        self._gva_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-burriana/1.0")},
        )
        with self._opener.open(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str = BASE) -> str:
        return urllib.parse.urljoin(base, href)

    def _extract_pdfs(self, html: str, base: str = BASE) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1), base)
            if "favicon" in u.lower():
                continue
            out.append(u)
        return list(dict.fromkeys(out))

    def _collect_wp_posts(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        page = 1
        while page <= 5:
            url = f"{BASE}/wp-json/wp/v2/posts?search=urbanismo&per_page=100&page={page}"
            try:
                posts = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
                break
            if not isinstance(posts, list) or not posts:
                break
            for post in posts:
                link = str(post.get("link") or "").strip()
                title = _strip_html(str((post.get("title") or {}).get("rendered") or ""))
                if not link or link in seen:
                    continue
                if not RE_PROYECTO.search(title) and not RE_LICENCIA.search(title):
                    continue
                seen.add(link)
                content = str((post.get("content") or {}).get("rendered") or "")
                rows.append(
                    {
                        "titulo": title[:500],
                        "fecha": _iso_date_wp(str(post.get("date") or "")),
                        "url": link,
                        "pdfs": self._extract_pdfs(content),
                        "origen": "wp_search",
                    }
                )
            if len(posts) < 100:
                break
            page += 1
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        seeds = [
            (PGOU_URL, "pgou"),
            (URBANISMO_URL, "urbanismo"),
            (TABLON_ORDENACION, "tablon_ordenacion"),
            f"{BASE}/servicios-municipales/urbanismo/plan-de-recuperacion-del-casco-historico-de-burriana/",
            f"{BASE}/servicios-municipales/urbanismo/concurso-ideas-pla/",
        ]
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for url, origen in seeds:
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for pdf in self._extract_pdfs(html, url):
                if pdf in seen:
                    continue
                seen.add(pdf)
                name = unescape(urllib.parse.unquote(Path(pdf).name))
                rows.append(
                    {
                        "titulo": name[:500],
                        "fecha": _fecha_from_url(pdf),
                        "url": pdf,
                        "pdf_url": pdf,
                        "origen": origen,
                    }
                )
            if origen == "tablon_ordenacion":
                for href, label in RE_DIR_LINK.findall(html):
                    full = self._abs_url(href, TABLON_ORDENACION)
                    label = _strip_html(label)
                    if not label or label in seen:
                        continue
                    if not RE_PROYECTO.search(label) and "plan" not in label.lower():
                        continue
                    seen.add(full)
                    rows.append(
                        {
                            "titulo": label[:500],
                            "fecha": _fecha_from_url(full),
                            "url": full,
                            "origen": "tablon_dir",
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
            row_html = m.group(0)
            cells: dict[str, str] = {}
            for cm in RE_BOARD_CELL.finditer(row_html):
                cells[cm.group(1)] = _strip_html(cm.group(2))
            documento = cells.get("class_name", "")
            if not documento or documento in ("Documento",):
                continue
            preview_m = RE_PREVIEW_LINK.search(row_html)
            title_m = re.search(r'title="([^"]+)"', row_html)
            url = preview_m.group(1) if preview_m else self.board_url
            if url.startswith("/"):
                url = f"{self.sede_base}{url}"
            titulo = cells.get("class_description") or cells.get("class_name") or documento
            if title_m and title_m.group(1).strip():
                titulo = title_m.group(1).strip()
            expediente = cells.get("class_folderCode", "")
            if expediente and expediente not in titulo:
                titulo = f"{titulo} (exp. {expediente})"
            rows.append(
                {
                    "titulo": titulo[:500],
                    "expediente": expediente[:120],
                    "procedimiento": cells.get("class_folderName", "")[:200],
                    "categoria": cells.get("class_boardCategory", "")[:120],
                    "fecha": _parse_fecha_dmy(cells.get("class_dateFrom", "")),
                    "url": url,
                    "origen": "sede_board",
                    "blob": f"{documento} {expediente} {cells.get('class_folderName', '')} {titulo}",
                }
            )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.board_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — sede electrónica Burriana",
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
                "nota": "Licencias de obra y actividad vía sede; sin histórico público de concesiones",
                "origen": "sede_tramite",
            },
        ]

    def _load_dipcas_geometries(self) -> list[dict[str, Any]]:
        if self._geom_cache is not None:
            return self._geom_cache
        url = (
            f"{DIPCAS_API}?where=cod_mun%3D%27{INE_COD_MUN}%27"
            "&limit=100&select=denominacion,tipo_suelo,tipo_urba,geo_shape"
        )
        cache: list[dict[str, Any]] = []
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._geom_cache = cache
            return cache
        for rec in data.get("results") or []:
            shape = rec.get("geo_shape") or {}
            geom = shape.get("geometry") if isinstance(shape, dict) else None
            if not isinstance(geom, dict):
                continue
            label = str(rec.get("denominacion") or rec.get("tipo_suelo") or "").strip()
            cache.append(
                {
                    "label": label,
                    "tipo_suelo": str(rec.get("tipo_suelo") or ""),
                    "geom": geom,
                    "source_url": url,
                }
            )
        self._geom_cache = cache
        return cache

    def _load_gva_features(self) -> list[dict[str, Any]]:
        if self._gva_cache is not None:
            return self._gva_cache
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": GVA_WFS_TYPE,
                "outputFormat": "GML3",
                "srsName": "EPSG:4326",
                "count": "5000",
            }
        )
        url = f"{GVA_WFS}?{params}"
        feats: list[dict[str, Any]] = []
        try:
            raw = self._fetch(url, timeout=120)
            root = ET.fromstring(raw)
        except (urllib.error.URLError, ET.ParseError):
            self._gva_cache = feats
            return feats
        ns = {
            "wfs": "http://www.opengis.net/wfs/2.0",
            "gml": "http://www.opengis.net/gml",
        }
        for member in root.findall(".//wfs:member", ns):
            feat_el = member[0]
            props: dict[str, str] = {}
            geom = None
            for child in feat_el:
                tag = child.tag.split("}")[-1]
                if tag == "msGeometry":
                    pos = child.find(".//gml:posList", ns)
                    if pos is not None and pos.text:
                        geom = _gml_poslist_to_polygon(pos.text)
                else:
                    props[tag] = (child.text or "").strip()
            if props.get("cod_ine_mun") != INE_COD_MUN and props.get("noms_mun") != "Burriana":
                continue
            if not geom:
                continue
            label = props.get("denominaci") or props.get("expediente") or ""
            feats.append(
                {
                    "label": label,
                    "expediente": props.get("expediente") or "",
                    "geom": geom,
                    "source_url": (
                        f"{GVA_WFS}?service=WFS&request=GetFeature&"
                        f"CQL_FILTER=cod_ine_mun%3D%27{INE_COD_MUN}%27"
                    ),
                }
            )
        self._gva_cache = feats
        return feats

    def _match_keywords(self, title: str) -> list[str]:
        low = title.lower()
        keys: list[str] = []
        for m in RE_UE_CODE.finditer(title):
            keys.append(m.group(0).lower().strip())
        for token in (
            "artelina",
            "xamussa",
            "xamussa",
            "sant gregori",
            "serratella",
            "cañada blanch",
            "canada blanch",
            "villa fátima",
            "villa fatima",
            "zona marítima",
            "zona maritima",
            "casco histórico",
            "casco historico",
            "malvarrosa",
            "puep",
            "edusi",
            "normas subsidiarias",
            "plan general",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        keys = self._match_keywords(title)
        title_low = title.lower()
        candidates: list[tuple[float, dict[str, Any], str]] = []

        for item in self._load_dipcas_geometries():
            label = item["label"].lower()
            score = 0.0
            for k in keys:
                if k in label or k in title_low:
                    score += 20
            if "normas subsidiarias" in title_low and "normas subsidiarias" in label:
                score += 15
            if score >= 15:
                candidates.append((score, item["geom"], item["source_url"]))

        for item in self._load_gva_features():
            label = item["label"].lower()
            score = 0.0
            for k in keys:
                if k in label:
                    score += 30
            if "artelina" in title_low and "artelina" in label:
                score += 40
            if score >= 20:
                candidates.append((score, item["geom"], item["source_url"]))

        if not candidates:
            return None
        candidates.sort(key=lambda x: -x[0])
        _, geom, source_url = candidates[0]
        merged = _merge_geometries([geom])
        if not merged:
            return None
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": source_url,
            "coord_source": "portal_geometry_centroid",
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

    def _board_is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        proc = (row.get("procedimiento") or "").lower()
        if any(k in proc for k in ("planeamiento", "licencia", "urban", "actividad", "obra")):
            return True
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _wp_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row["titulo"]):
            return None
        key = row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        self._enrich_geometry(rec)
        return rec

    def _board_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        if not RE_LICENCIA.search(row.get("blob") or row.get("titulo") or ""):
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
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": "sede_board",
        }

    def _board_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._board_is_urban(row):
            return None
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": "sede_board",
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
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_board"),
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

        for item in self._collect_wp_posts():
            add(self._wp_to_proyecto(item))
        for item in self._collect_seed_pages():
            add(self._wp_to_proyecto(item))
        for item in self._collect_board():
            add(self._board_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "wp": sum(1 for r in rows if r.get("origen") == "wp_search"),
            "seed": sum(1 for r in rows if r.get("origen") in ("pgou", "urbanismo", "tablon_ordenacion", "tablon_dir")),
            "tablon": sum(1 for r in rows if r.get("origen") == "sede_board"),
            "with_geometry": with_geom,
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
