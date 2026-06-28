from __future__ import annotations

import hashlib
import json
import math
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

WP_BASE = "https://navalcarnero.es"
URBANISMO_BASE = f"{WP_BASE}/navalcarnero/urbanismo"
TRANSPARENCIA_URB = "https://transparencia.navalcarnero.es/obras-publicas-y-urbanismo"
TABLON_FEED = f"{WP_BASE}/navalcarnero/tablondeanuncios/feed/"
URBANISMO_FEED = f"{URBANISMO_BASE}/feed/"
TRAMITES_URB = f"{WP_BASE}/navalcarnero/tramites/?category=71"
SEDE_BASE = "https://sede.navalcarnero.es"
MUNICIPIO = "Navalcarnero"
ID_PREFIX = "navalcarnero"

TRANSPARENCIA_SEED_PAGES = (
    f"{TRANSPARENCIA_URB}/convenios-urbanisticos/",
    f"{TRANSPARENCIA_URB}/planes-especiales/",
    f"{TRANSPARENCIA_URB}/informacion-del-pgou/",
    f"{TRANSPARENCIA_URB}/planes-parciales/",
)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|licencias|solicitud de licencia|comunicaci[oó]n previa|"
    r"declaraci[oó]n responsable|autorizaci[oó]n (?:previa|urban)|inicio de obra|"
    r"autoliquidaci[oó]n.*licencia)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan (?:parcial|especial|general)|pgou|convenio|"
    r"informaci[oó]n p[uú]blica|expediente|proyecto|modificaci[oó]n|reparcel|"
    r"estudio (?:ac[uú]stico|ambiental|de detalle)|memoria|planos|edicto|"
    r"aprobaci[oó]n (?:inicial|definitiva)|soterramiento|fotovoltaica|"
    r"infraestructura|dominio.*inmatricul|rectificaci[oó]n descriptiva|"
    r"obra(?:s)? (?:p[uú]blica|municipal|mejora)|acera|mediana|polideportivo)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_YM = re.compile(r"/(?:uploads|wp-content/uploads|files)/(\d{4})[-/](\d{2})/")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_PDF_HREF = re.compile(
    r'href="((?:https?://(?:transparencia\.)?navalcarnero\.es)?/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_TRAMITE_LINK = re.compile(
    r'href="(https://navalcarnero\.es/navalcarnero/tramites/[^"]+)"[^>]*>([^<]+)',
    re.I,
)
RE_OBRA_ROW = re.compile(
    r"<td[^>]*>([^<]+)</td>\s*<td[^>]*>(\d{4})</td>",
    re.I | re.S,
)
RE_OBRA_PDF = re.compile(
    r'href="((?:https?://navalcarnero\.es)?/navalcarnero/urbanismo/files/[^"]+\.pdf)"',
    re.I,
)
RE_MAPDATA = re.compile(r"var\s+mapdata\s*=\s*(\{.*?\});", re.S)


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


def _fecha_from_url(url: str) -> str | None:
    m = RE_FECHA_YM.search(url)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), 1).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(x.group(1)) for x in RE_YEAR.finditer(Path(url).name) if 1980 <= int(x.group(1)) <= 2030]
    if years:
        return f"{max(years)}-01-01"
    return None


def _iso_from_rss(pub_date: str) -> str | None:
    if not pub_date:
        return None
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z"):
        try:
            return datetime.strptime(pub_date.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _point_buffer_polygon(lat: float, lng: float, meters: float = 30.0) -> dict[str, Any]:
    dlat = meters / 111_320.0
    dlng = meters / (111_320.0 * max(0.2, math.cos(math.radians(lat))))
    return {
        "type": "Polygon",
        "coordinates": [
            [
                [lng - dlng, lat - dlat],
                [lng + dlng, lat - dlat],
                [lng + dlng, lat + dlat],
                [lng - dlng, lat + dlat],
                [lng - dlng, lat - dlat],
            ]
        ],
    }


def _pdf_tipo(name: str) -> str:
    n = name.lower()
    if "convenio" in n:
        return "convenio urbanístico"
    if "plan especial" in n or "psf" in n or "fotovoltaica" in n:
        return "plan especial"
    if "modificacion" in n or "modificación" in n or "pgou" in n:
        return "modificación PGOU"
    if "plan parcial" in n:
        return "plan parcial"
    if "memoria" in n:
        return "memoria planeamiento"
    if "plano" in n:
        return "plano PGOU"
    return "documento urbanismo"


class NavalcarneroAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress multi-subsite: urbanismo MapPress + transparencia + tablón RSS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WP_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.urbanismo_base = str(self.config.get("urbanismo_base") or URBANISMO_BASE).rstrip("/")
        self.transparencia_urb = str(self.config.get("transparencia_urb") or TRANSPARENCIA_URB).rstrip("/")
        self.tablon_feed = str(self.config.get("tablon_feed") or TABLON_FEED)
        self.urbanismo_feed = str(self.config.get("urbanismo_feed") or URBANISMO_FEED)
        self.tramites_urb = str(self.config.get("tramites_urbanismo") or TRAMITES_URB)
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.transparencia_pages = list(
            self.config.get("transparencia_seed_pages") or TRANSPARENCIA_SEED_PAGES
        )

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-navalcarnero/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _abs(self, href: str, base: str = WP_BASE) -> str:
        return urllib.parse.urljoin(f"{base}/", href)

    def _parse_rss_items(self, xml_text: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return items
        channel = root.find("channel")
        if channel is None:
            return items
        for item in channel.findall("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            date_el = item.find("pubDate")
            desc_el = item.find("description")
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = (link_el.text or "").strip() if link_el is not None else ""
            pub = (date_el.text or "").strip() if date_el is not None else ""
            desc = (desc_el.text or "").strip() if desc_el is not None else ""
            if title and link:
                items.append(
                    {
                        "titulo": unescape(title)[:500],
                        "url": link,
                        "fecha": _iso_from_rss(pub),
                        "descripcion": unescape(_strip_html(desc))[:1000],
                    }
                )
        return items

    def _collect_mappress_obras(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(f"{self.urbanismo_base}/")
        except urllib.error.URLError:
            return []

        poi_by_title: dict[str, dict[str, Any]] = {}
        m = RE_MAPDATA.search(html)
        if m:
            try:
                data = json.loads(m.group(1))
            except json.JSONDecodeError:
                data = {}
            for poi in data.get("pois") or []:
                title = str(poi.get("title") or "").strip()
                point = poi.get("point") or {}
                lat = point.get("lat")
                lng = point.get("lng")
                pdf_m = re.search(r'href=\\"([^"]+\.pdf)\\"', poi.get("body") or "")
                pdf_url = pdf_m.group(1).replace("\\/", "/") if pdf_m else None
                if title:
                    poi_by_title[title.lower()] = {
                        "titulo": title,
                        "lat": lat,
                        "lng": lng,
                        "pdf_url": pdf_url,
                    }

        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for obra_m in RE_OBRA_ROW.finditer(html):
            titulo = unescape(obra_m.group(1).strip())
            year = obra_m.group(2)
            if not titulo or titulo.lower() in {"obra", "año ejecución"}:
                continue
            chunk = html[obra_m.start() : obra_m.start() + 2500]
            pdf_m = RE_OBRA_PDF.search(chunk)
            pdf_url = self._abs(pdf_m.group(1), WP_BASE) if pdf_m else f"{self.urbanismo_base}/"
            key = titulo.lower()
            poi = poi_by_title.get(key) or next(
                (v for k, v in poi_by_title.items() if k in key or key in k),
                None,
            )
            rec_id = _stable_id("proy", f"obra:{titulo}:{year}")
            if rec_id in seen:
                continue
            seen.add(rec_id)
            fecha = f"{year}-06-01" if year.isdigit() else None
            rec: dict[str, Any] = {
                "id": rec_id,
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": fecha,
                "tipo": "obra municipal mejora urbana",
                "url": pdf_url,
                "source": "ayuntamiento",
                "origen": "urbanismo_mapa",
            }
            if poi and poi.get("lat") is not None and poi.get("lng") is not None:
                lat = float(poi["lat"])
                lng = float(poi["lng"])
                geom = _point_buffer_polygon(lat, lng)
                rec.update(
                    {
                        "lat": lat,
                        "lon": lng,
                        "geom_geojson": geom,
                        "geometry_source": "portal_mappress_map",
                        "geometry_source_url": f"{self.urbanismo_base}/",
                        "coord_source": "portal_geometry_centroid",
                    }
                )
            rows.append(rec)

        for poi in poi_by_title.values():
            titulo = poi["titulo"]
            rec_id = _stable_id("proy", f"mappa:{titulo}")
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rec = {
                "id": rec_id,
                "municipio": MUNICIPIO,
                "titulo": titulo[:500],
                "fecha": None,
                "tipo": "obra municipal mejora urbana",
                "url": poi.get("pdf_url") or f"{self.urbanismo_base}/",
                "source": "ayuntamiento",
                "origen": "urbanismo_mappress",
            }
            if poi.get("lat") is not None and poi.get("lng") is not None:
                lat = float(poi["lat"])
                lng = float(poi["lng"])
                geom = _point_buffer_polygon(lat, lng)
                rec.update(
                    {
                        "lat": lat,
                        "lon": lng,
                        "geom_geojson": geom,
                        "geometry_source": "portal_mappress_map",
                        "geometry_source_url": f"{self.urbanismo_base}/",
                        "coord_source": "portal_geometry_centroid",
                    }
                )
            rows.append(rec)
        return rows

    def _collect_urbanismo_feed(self) -> list[dict[str, Any]]:
        try:
            xml = self._fetch(self.urbanismo_feed)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._parse_rss_items(xml):
            blob = f"{item['titulo']} {item.get('descripcion', '')}"
            if not RE_PROYECTO.search(blob):
                continue
            tipo = "planeamiento"
            if re.search(r"(?i)modificaci[oó]n", blob):
                tipo = "modificación PGOU"
            elif re.search(r"(?i)plan especial", blob):
                tipo = "plan especial"
            rows.append(
                {
                    "id": _stable_id("proy", item["url"]),
                    "municipio": MUNICIPIO,
                    "titulo": item["titulo"],
                    "fecha": item.get("fecha"),
                    "tipo": tipo,
                    "url": item["url"],
                    "source": "ayuntamiento",
                    "origen": "urbanismo_rss",
                }
            )
        return rows

    def _collect_transparencia_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.transparencia_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for m in RE_PDF_HREF.finditer(html):
                url = m.group(1)
                if url in seen:
                    continue
                seen.add(url)
                name = unescape(urllib.parse.unquote(Path(url).name))
                name = re.sub(r"\.pdf$", "", name, flags=re.I).replace("-", " ").replace("_", " ")
                rows.append(
                    {
                        "id": _stable_id("proy", url),
                        "municipio": MUNICIPIO,
                        "titulo": name[:500],
                        "fecha": _fecha_from_url(url),
                        "tipo": _pdf_tipo(name),
                        "url": url,
                        "source": "ayuntamiento",
                        "origen": "transparencia_pdf",
                    }
                )
        return rows

    def _collect_tablon_feed(self) -> list[dict[str, Any]]:
        try:
            xml = self._fetch(self.tablon_feed)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for item in self._parse_rss_items(xml):
            blob = f"{item['titulo']} {item.get('descripcion', '')}"
            pdf_m = re.search(
                r"(https://navalcarnero\.es/navalcarnero/tablondeanuncios/files/[^\"]+\.pdf)",
                item.get("descripcion", ""),
            )
            pdf_url = pdf_m.group(1) if pdf_m else item["url"]
            rows.append(
                {
                    "titulo": item["titulo"],
                    "fecha": item.get("fecha"),
                    "url": pdf_url,
                    "page_url": item["url"],
                    "blob": blob,
                    "is_licencia": bool(RE_LICENCIA.search(blob)),
                    "is_proyecto": bool(RE_PROYECTO.search(blob)),
                }
            )
        return rows

    def _collect_tramites_licencias(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tramites_urb)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for m in RE_TRAMITE_LINK.finditer(html):
            url = m.group(1)
            title = unescape(_strip_html(m.group(2)))
            if not RE_LICENCIA.search(title):
                continue
            rec_id = _stable_id("lic", url)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": "trámite licencia urbanística",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title[:500],
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Formulario descargable; no es concesión publicada",
                }
            )
        return rows

    def _collect_licencia_info(self) -> list[dict[str, Any]]:
        return [
            {
                "id": _stable_id("lic", self.tramites_urb),
                "fecha_concesion": None,
                "tipo": "trámites urbanismo (descargas)",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Área de Urbanismo — formularios y trámites",
                "url": self.tramites_urb,
                "source": "ayuntamiento",
                "nota": "Página informativa de licencias y declaraciones responsables",
            },
            {
                "id": _stable_id("lic", self.sede_base),
                "fecha_concesion": None,
                "tipo": "sede electrónica",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Sede electrónica — presentación de trámites urbanísticos",
                "url": self.sede_base,
                "source": "ayuntamiento",
                "nota": "Requiere identificación para consulta de expedientes",
            },
            {
                "id": _stable_id("lic", f"{self.urbanismo_base}/descripcion-urbanismo/"),
                "fecha_concesion": None,
                "tipo": "información licencias y obras",
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": "Urbanismo — licencias de obra y actividades",
                "url": f"{self.urbanismo_base}/descripcion-urbanismo/",
                "source": "ayuntamiento",
            },
        ]

    def _tablon_to_proyecto(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if not item.get("is_proyecto"):
            return None
        if item.get("is_licencia") and not RE_PROYECTO.search(item.get("blob", "")):
            return None
        blob = item.get("blob") or item["titulo"]
        tipo = "anuncio municipal"
        if re.search(r"(?i)dominio|inmatricul", blob):
            tipo = "expediente dominio registral"
        elif re.search(r"(?i)urban|planeam|pgou", blob):
            tipo = "urbanismo"
        return {
            "id": _stable_id("proy", item.get("page_url") or item["url"]),
            "municipio": MUNICIPIO,
            "titulo": item["titulo"][:500],
            "fecha": item.get("fecha"),
            "tipo": tipo,
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "tablon_rss",
        }

    def _tablon_to_licencia(self, item: dict[str, Any]) -> dict[str, Any] | None:
        if not item.get("is_licencia"):
            return None
        return {
            "id": _stable_id("lic", item.get("page_url") or item["url"]),
            "fecha_concesion": item.get("fecha"),
            "tipo": "anuncio licencia / trámite",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": item["titulo"][:500],
            "url": item["url"],
            "source": "ayuntamiento",
            "origen": "tablon_rss",
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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for item in self._collect_tablon_feed():
            add(self._tablon_to_licencia(item))
        for rec in self._collect_tramites_licencias():
            add(rec)
        for rec in self._collect_licencia_info():
            add(rec)

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
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_mappress_obras():
            add(rec)
        for rec in self._collect_urbanismo_feed():
            add(rec)
        for rec in self._collect_transparencia_pdfs():
            add(rec)
        for item in self._collect_tablon_feed():
            add(self._tablon_to_proyecto(item))

        self._write_jsonl(out_jsonl, rows)
        return {
            "rows": len(rows),
            "status": "ok",
            "obras_mapa": sum(1 for r in rows if r.get("origen", "").startswith("urbanismo")),
            "transparencia": sum(1 for r in rows if r.get("origen") == "transparencia_pdf"),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        before = len(existing)
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
