from __future__ import annotations

import hashlib
import json
import re
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

BASE = "https://www.lalfas.es"
SEDE_URL = "https://ciudadano.lalfas.es/PortalCiudadania/"
TABLON_URL = f"{BASE}/list-transparencia/tablon-de-anuncios/"
PGOU_URL = f"{BASE}/servicios/urbanismo/pgou-vsp/"
URBANISMO_URL = f"{BASE}/servicios/urbanismo/"
MUNICIPIO = "L'Alfàs del Pi"
ID_PREFIX = "lalfas"
INE_COD_MUN = "03009"

GVA_WFS = "https://terramapas.icv.gva.es/0702_Planeamiento"
GVA_WFS_TYPE = "ms:Planeamiento.Zonificacion"

MESES = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|obra mayor|obra menor|"
    r"primera ocupaci[oó]n|inicio de obra|incoaci[oó]n|apertura de (?:centro|actividad|local))",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|pai|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n p[uú]blica|expediente|expte|proyecto|"
    r"modificaci[oó]n|reparcel|aprobaci[oó]n|sector|finca roca|urbanizaci[oó]n|"
    r"programa de actuaci|normas subsidiarias|dogv|bopa|clima|energ[ií]a sostenible|"
    r"licencia ambiental|vpp|vut|nou albir|albir ii)",
)
RE_BOARD_NON_URBAN = re.compile(
    r"(?i)(selecci[oó]n de personal|nombramiento|convocatoria.*empleo|"
    r"padron|padr[oó]n|mercadillo|iae|cobranza|taxi|hacienda\.|prescripci[oó]n|"
    r"auxiliar|empleo p[uú]blico|matrimonio|bono|subvenci[oó]n)",
)
RE_TABLON_ENTRY = re.compile(
    r'<h2[^>]*class="entry-title"[^>]*>\s*<a href="([^"]+)"[^>]*>(.*?)</a>\s*</h2>'
    r'\s*<p class="post-meta"><span class="published">([^<]+)</span>',
    re.I | re.S,
)
RE_PUBLISHED = re.compile(r"(\d{1,2})\s+(\w+)\s+(\d{4})")
RE_EXPDTE = re.compile(
    r"(?i)(?:EXPTE\.?|EXPEDIENTE)[:\s]*([A-Z]{2,6}/\d+/\d+)|\b(BAS|PROY|LAAC|URB)/\d+/\d+\b",
)
RE_PDF_HREF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


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


def _parse_published(text: str) -> str | None:
    m = RE_PUBLISHED.search(text or "")
    if not m:
        return None
    day, month_name, year = int(m.group(1)), m.group(2).lower(), int(m.group(3))
    month = MESES.get(month_name)
    if not month:
        return None
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _iso_date_wp(date_str: str) -> str | None:
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return date_str[:10] if len(date_str) >= 10 else None


def _extract_expediente(text: str) -> str | None:
    m = RE_EXPDTE.search(text or "")
    if not m:
        return None
    return (m.group(1) or m.group(2) or "").strip()


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "pai" in n or "programa de actuaci" in n or "finca roca" in n:
        return "PAI"
    if "plan parcial" in n or "sector" in n:
        return "plan parcial"
    if "pgou" in n or "plan general" in n:
        return "PGOU"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "licencia ambiental" in n:
        return "licencia ambiental"
    if "clima" in n or "paces" in n:
        return "plan climático"
    if "licencia" in n or "incoaci" in n or "apertura" in n:
        return "licencia / actividad"
    return "urbanismo"


def _gml_poslist_to_polygon(poslist: str) -> dict[str, Any] | None:
    nums = [float(x) for x in poslist.split() if x.strip()]
    if len(nums) < 6:
        return None
    ring: list[list[float]] = []
    for i in range(0, len(nums) - 1, 2):
        lng, lat = nums[i], nums[i + 1]
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


class LAlfasDelPiAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress lalfas.es tablón + PGOU PDFs + ICV GVA WFS (geometría partial)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or BASE).rstrip("/")
        self.sede_url = str(self.config.get("sede_url") or SEDE_URL)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        self.pgou_url = str(self.config.get("pgou_url") or PGOU_URL)
        self.urbanismo_url = str(self.config.get("urbanismo_url") or URBANISMO_URL)
        self.cod_ine_mun = str(self.config.get("cod_ine_mun") or INE_COD_MUN)
        geom_cfg = self.config.get("geometry") or {}
        self.gva_wfs = str(geom_cfg.get("wfs_url") or GVA_WFS).rstrip("/")
        self.gva_type = str(geom_cfg.get("type_name") or GVA_WFS_TYPE)
        self._gva_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 60) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-l-alfas-del-pi/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _abs_url(self, href: str, base: str | None = None) -> str:
        return urllib.parse.urljoin(base or self.web_base, href)

    def _extract_pdfs(self, html: str, base: str | None = None) -> list[str]:
        out: list[str] = []
        for m in RE_PDF_HREF.finditer(html):
            u = self._abs_url(m.group(1), base or self.web_base)
            if "favicon" not in u.lower():
                out.append(u)
        return list(dict.fromkeys(out))

    def _collect_tablon(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page in range(1, 21):
            url = self.tablon_url if page == 1 else f"{self.tablon_url}page/{page}/"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                break
            matches = RE_TABLON_ENTRY.findall(html)
            if not matches:
                break
            for link, title_html, published in matches:
                link = link.strip()
                if link in seen:
                    continue
                seen.add(link)
                titulo = _strip_html(title_html)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": _parse_published(published),
                        "url": link,
                        "expediente": _extract_expediente(titulo) or "",
                        "origen": "tablon",
                        "blob": titulo,
                    }
                )
        return rows

    def _collect_wp_search(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for term in ("expediente", "planeamiento", "urbanismo", "licencia", "pgou", "informacion publica"):
            page = 1
            while page <= 3:
                q = urllib.parse.quote(term)
                url = f"{self.web_base}/wp-json/wp/v2/search?search={q}&per_page=100&page={page}"
                try:
                    posts = self._fetch_json(url)
                except (urllib.error.URLError, json.JSONDecodeError):
                    break
                if not isinstance(posts, list) or not posts:
                    break
                for post in posts:
                    link = str(post.get("url") or "").strip()
                    title = _strip_html(str(post.get("title") or ""))
                    if not link or link in seen:
                        continue
                    if not RE_PROYECTO.search(title) and not RE_LICENCIA.search(title):
                        continue
                    seen.add(link)
                    rows.append(
                        {
                            "titulo": title[:500],
                            "fecha": None,
                            "url": link,
                            "expediente": _extract_expediente(title) or "",
                            "origen": "wp_search",
                            "blob": title,
                        }
                    )
                if len(posts) < 100:
                    break
                page += 1
        return rows

    def _collect_seed_pages(self) -> list[dict[str, Any]]:
        seeds = [
            (self.pgou_url, "pgou"),
            (self.urbanismo_url, "urbanismo"),
            (f"{self.urbanismo_url}registro-de-programas-y-aiu/", "aiu"),
            (f"{self.urbanismo_url}nou-albir-ii/", "nou_albir"),
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
                        "fecha": None,
                        "url": pdf,
                        "pdf_url": pdf,
                        "origen": origen,
                        "blob": name,
                    }
                )
            titulo = f"Instrumentos urbanismo — {origen.replace('_', ' ')}"
            page_url = url
            if page_url not in seen:
                seen.add(page_url)
                rows.append(
                    {
                        "titulo": titulo[:500],
                        "fecha": None,
                        "url": page_url,
                        "origen": origen,
                        "blob": titulo,
                    }
                )
        return rows

    def _collect_licencia_info_pages(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tablon_url),
                "fecha_concesion": None,
                "tipo": "tablón de anuncios",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Tablón de anuncios — L'Alfàs del Pi",
                "url": self.tablon_url,
                "source": "ayuntamiento",
                "nota": "Edictos e informaciones públicas (WordPress)",
                "origen": "web_tablon",
            },
            {
                "id": _stable_id("lic", self.sede_url),
                "fecha_concesion": None,
                "tipo": "sede electrónica — trámites",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — licencias y comunicaciones previas",
                "url": self.sede_url,
                "source": "ayuntamiento",
                "nota": "Portal Maggioli; requiere identificación; sin histórico público",
                "origen": "sede_tramite",
            },
        ]

    def _load_gva_features(self) -> list[dict[str, Any]]:
        if self._gva_cache is not None:
            return self._gva_cache
        feats: list[dict[str, Any]] = []
        start = 0
        count = 200
        ns = {"wfs": "http://www.opengis.net/wfs/2.0", "gml": "http://www.opengis.net/gml"}
        source_url = (
            f"{self.gva_wfs}?service=WFS&request=GetFeature&"
            f"CQL_FILTER=cod_ine_mun%3D%27{self.cod_ine_mun}%27"
        )
        while start < 2000:
            params = urllib.parse.urlencode(
                {
                    "service": "WFS",
                    "version": "2.0.0",
                    "request": "GetFeature",
                    "typeName": self.gva_type,
                    "outputFormat": "GML3",
                    "srsName": "EPSG:4326",
                    "count": str(count),
                    "startIndex": str(start),
                    "CQL_FILTER": f"cod_ine_mun='{self.cod_ine_mun}'",
                }
            )
            url = f"{self.gva_wfs}?{params}"
            try:
                raw = self._fetch(url, timeout=120)
                root = ET.fromstring(raw)
            except (urllib.error.URLError, ET.ParseError):
                break
            members = root.findall(".//wfs:member", ns)
            if not members:
                break
            for member in members:
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
                if not geom:
                    continue
                label = props.get("denominaci") or props.get("expediente") or ""
                if "MUNICIPIO SIN PLANEAMIENTO" in label.upper():
                    continue
                feats.append(
                    {
                        "label": label,
                        "expediente": props.get("expediente") or "",
                        "zon_suelo": props.get("zon_suelo") or "",
                        "descripcio": props.get("descripcio") or "",
                        "geom": geom,
                        "source_url": source_url,
                    }
                )
            if len(members) < count:
                break
            start += count
        self._gva_cache = feats
        return feats

    def _match_keywords(self, title: str) -> list[str]:
        low = title.lower()
        keys: list[str] = []
        exp = _extract_expediente(title)
        if exp:
            keys.append(exp.lower())
            for part in re.split(r"[/\s]+", exp):
                if len(part) >= 3:
                    keys.append(part.lower())
        for token in (
            "finca roca",
            "nou albir",
            "albir",
            "nenieta",
            "sector c",
            "sector 5",
            "sau 3",
            "sau 4",
            "sau-3",
            "pgou",
            "plan general",
            "plan parcial",
            "normas subsidiarias",
            "pai",
            "urbanizaci",
        ):
            if token in low:
                keys.append(token)
        return keys

    def _fetch_geometry(self, titulo: str) -> dict[str, Any] | None:
        title = titulo or ""
        keys = self._match_keywords(title)
        title_low = title.lower()
        candidates: list[tuple[float, dict[str, Any], str]] = []

        for item in self._load_gva_features():
            label = item["label"].lower()
            exp = item.get("expediente", "").lower()
            zon = item.get("zon_suelo", "").lower()
            desc = item.get("descripcio", "").lower()
            blob = f"{label} {exp} {zon} {desc}"
            score = 0.0
            for k in keys:
                if k in blob or k in title_low:
                    score += 20
            if "finca roca" in title_low and "roca" in label:
                score += 35
            if "pgou" in title_low and "plan general" in label:
                score += 25
            if "sector" in title_low and "sector" in label:
                score += 20
            if "pai" in title_low and ("pai" in label or "programa" in label):
                score += 25
            if score >= 20:
                candidates.append((score, item["geom"], item["source_url"]))

        if not candidates:
            return None
        candidates.sort(key=lambda x: -x[0])
        top = candidates[0][0]
        geoms = [g for s, g, _ in candidates if s >= top - 5]
        merged = _merge_geometries(geoms)
        if not merged:
            return None
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": candidates[0][2],
            "coord_source": "portal_geometry_centroid",
        }

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        geom = self._fetch_geometry(rec.get("titulo") or "")
        if not geom:
            return
        rec.update(geom)
        cen = geometry_centroid(geom["geom_geojson"])
        if cen:
            rec.setdefault("lat", cen[0])
            rec.setdefault("lon", cen[1])

    def _is_urban(self, row: dict[str, Any]) -> bool:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_BOARD_NON_URBAN.search(blob) and not RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return False
        return bool(RE_LICENCIA.search(blob) or RE_PROYECTO.search(blob))

    def _tablon_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban(row):
            return None
        blob = row.get("blob") or ""
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            if "informaci" not in blob.lower() and "exposici" not in blob.lower():
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
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _tablon_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not self._is_urban(row):
            return None
        blob = row.get("blob") or ""
        if not RE_LICENCIA.search(blob):
            return None
        key = row.get("expediente") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", key),
            "fecha_concesion": row.get("fecha"),
            "tipo": "licencia / actividad",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": row["titulo"],
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        self._enrich_geometry(rec)
        return rec

    def _item_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if not RE_PROYECTO.search(row.get("blob") or row.get("titulo") or ""):
            if row.get("origen") not in ("pgou", "urbanismo", "aiu", "nou_albir"):
                return None
        key = row.get("expediente") or row.get("pdf_url") or row["url"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": row["titulo"],
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(row["titulo"]),
            "url": row["url"],
            "source": "ayuntamiento",
            "expte": row.get("expediente") or None,
            "origen": row.get("origen"),
        }
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
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
        for item in self._collect_tablon() + self._collect_wp_search():
            rec = self._tablon_to_licencia(item)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "wp_search")),
            "info": sum(1 for r in rows if r.get("origen") in ("web_tablon", "sede_tramite")),
        }

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
        for rec in self._collect_licencia_info_pages():
            existing[rec["id"]] = rec
        for item in self._collect_tablon() + self._collect_wp_search():
            rec = self._tablon_to_licencia(item)
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

        for item in self._collect_seed_pages():
            add(self._item_to_proyecto(item))
        for item in self._collect_tablon() + self._collect_wp_search():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "seed": sum(1 for r in rows if r.get("origen") in ("pgou", "urbanismo", "aiu", "nou_albir")),
            "tablon": sum(1 for r in rows if r.get("origen") in ("tablon", "wp_search")),
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
        return stats
