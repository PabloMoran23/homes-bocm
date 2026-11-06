from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path
from typing import Any

from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from shapely.validation import make_valid

from municipio.adapters.portal import AyuntamientoAdapter

URBAN_BASE = "https://urbanismo.montilla.es"
VISOR_BASE = "https://visorurbanistico.montilla.es"
# Centro aproximado del casco (Nominatim Montilla, Córdoba) — solo para filas informativas de licencias
MUNICIPIO_CENTROID_LAT = 37.5811178
MUNICIPIO_CENTROID_LON = -4.6414726

DEFAULT_RSS = f"{URBAN_BASE}/feed/"
DEFAULT_WFS = f"{VISOR_BASE}/geoserver/wfs"
DEFAULT_TYPE_INSTRUMENTOS = "urbancity_montilla_instrumentos:instrumentos"

RE_ITEM = re.compile(r"<item>(.*?)</item>", re.I | re.DOTALL)
RE_TAG = re.compile(r"<(title|link|pubDate|category|description)[^>]*>(.*?)</\1>", re.I | re.DOTALL)

RE_LICENCIA = re.compile(
    r"(?i)(licencia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"obra|edificaci[oó]n|instalaci[oó]n|ocupaci[oó]n|modificaci[oó]n de uso)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|pgou|pai|peri|plan parcial|plan especial|"
    r"convenio|instrumento|reforma interior|expediente|desarrollo|"
    r"ordenaci[oó]n|modelo de ciudad|agenda urbana|patrimonio)",
)


def _stable_id(prefix: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"montilla-{prefix}-{h}"


def _strip_tags(html: str) -> str:
    t = re.sub(r"<[^>]+>", " ", html or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_pub_date(raw: str) -> str | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.date().isoformat()
    except (ValueError, TypeError):
        return None


def _parse_iso_date_z(raw: str | None) -> str | None:
    if not raw:
        return None
    s = str(raw).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.date().isoformat()
    except ValueError:
        return None


def _clean_geojson_geometry(g: dict[str, Any] | None) -> dict[str, Any] | None:
    """GeoServer a veces devuelve anillos con vértices duplicados; Shapely los normaliza."""
    if not isinstance(g, dict) or not g.get("type"):
        return None
    try:
        geom = shape(g)
        if not geom.is_valid:
            geom = make_valid(geom)
        if geom.is_empty:
            return None
        gtype = geom.geom_type
        if gtype == "GeometryCollection":
            polys = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty]
            if not polys:
                return None
            geom = unary_union(polys)
            if geom.is_empty:
                return None
        if geom.geom_type not in ("Polygon", "MultiPolygon"):
            return None
        return mapping(geom)
    except Exception:
        return None


class MontillaAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress urbanismo (RSS) + visor GeoServer WFS (instrumentos) + páginas trámite licencias."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or URBAN_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.ua = str(self.config.get("user_agent", "poc-bocm-montilla/1.0"))
        self.rss_url = str(self.config.get("rss_url") or DEFAULT_RSS)
        self.wfs_base = str(self.config.get("wfs_base") or DEFAULT_WFS).rstrip("/")
        self.wfs_type = str(self.config.get("wfs_type_instrumentos") or DEFAULT_TYPE_INSTRUMENTOS)
        self._lic_pages: list[str] = [
            str(u) for u in (self.config.get("licencia_pages") or self._default_lic_pages())
        ]

    def _default_lic_pages(self) -> list[str]:
        return [
            f"{URBAN_BASE}/informacion-sobre-tramites-urbanisticos/",
            f"{URBAN_BASE}/licencia-de-edificacion-obras-e-instalaciones/",
            f"{URBAN_BASE}/declaracion-responsable-de-edificacion-obras-e-instalaciones/",
            f"{URBAN_BASE}/declaracion-responsable-de-ocupacion-o-utilizacion/",
            f"{URBAN_BASE}/declaracion-responsable-de-modificacion-de-uso/",
            f"{URBAN_BASE}/tramite-de-comunicacion-previa/",
        ]

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self.ua})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _parse_rss_item(self, block: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for m in RE_TAG.finditer(block):
            tag, inner = m.group(1).lower(), m.group(2)
            fields[tag] = _strip_tags(inner) if tag != "description" else inner
        if "title" not in fields and (
            m := re.search(r"<title><!\[CDATA\[(.*?)\]\]></title>", block, re.I | re.S)
        ):
            fields["title"] = m.group(1).strip()
        if "link" not in fields and (m := re.search(r"<link>([^<]+)</link>", block, re.I)):
            fields["link"] = m.group(1).strip()
        return fields

    def _rss_noticias_urbanismo(self) -> list[dict[str, Any]]:
        try:
            xml = self._fetch(self.rss_url)
        except (urllib.error.URLError, OSError):
            return []
        out: list[dict[str, Any]] = []
        for m in RE_ITEM.finditer(xml):
            f = self._parse_rss_item(m.group(1))
            title = (f.get("title") or "").strip()
            link = (f.get("link") or "").strip()
            if not title or not link:
                continue
            hay = f"{title} {f.get('category', '')}"
            if not (RE_PROYECTO.search(hay) or RE_LICENCIA.search(hay)):
                continue
            pub = _parse_pub_date(f.get("pubDate", ""))
            desc = _strip_tags(f.get("description", ""))[:800]
            key = f"{link}|{title}"
            geom_url = self.rss_url
            rec: dict[str, Any] = {
                "id": _stable_id("proy", key),
                "municipio": "Montilla",
                "titulo": title[:500],
                "fecha": pub,
                "tipo": "noticia urbanismo",
                "url": link,
                "source": "ayuntamiento",
                "descripcion": desc or None,
                "origen": "rss_urbanismo",
                "geometry_source": None,
                "geometry_source_url": geom_url,
                "coord_source": None,
            }
            out.append(rec)
        return out

    def _wfs_get_instrumentos_page(self, start_index: int, page_size: int) -> dict[str, Any]:
        q = urllib.parse.urlencode(
            {
                "service": "wfs",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeNames": self.wfs_type,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": str(page_size),
                "startIndex": str(start_index),
                "sortBy": "id",
            }
        )
        url = f"{self.wfs_base}?{q}"
        raw = self._fetch(url)
        return json.loads(raw)

    def _instrumentos_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page_size = int(self.config.get("wfs_page_size", 80))
        start = 0
        while True:
            try:
                data = self._wfs_get_instrumentos_page(start, page_size)
            except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError):
                break
            feats = data.get("features") or []
            if not feats:
                break
            for feat in feats:
                props = feat.get("properties") or {}
                geom = feat.get("geometry")
                fid = props.get("id")
                name = (props.get("name") or "").strip() or f"instrumento-{fid}"
                grp = (props.get("instrument_type_group_name") or "").strip()
                tipo = (props.get("instrument_type_name") or "").strip()
                fecha = (
                    _parse_iso_date_z(props.get("publish_date"))
                    or _parse_iso_date_z(props.get("approval_date"))
                )
                desc = (props.get("description") or "").strip()
                titulo = name
                if grp or tipo:
                    titulo = f"{name} ({grp}: {tipo})" if grp and tipo else f"{name} ({grp or tipo})"

                geom_q = urllib.parse.urlencode(
                    {
                        "service": "wfs",
                        "version": "2.0.0",
                        "request": "GetFeature",
                        "typeNames": self.wfs_type,
                        "outputFormat": "application/json",
                        "srsName": "EPSG:4326",
                        "count": "1",
                        "CQL_FILTER": f"id={fid}",
                    }
                )
                geom_url = f"{self.wfs_base}?{geom_q}"

                key = f"wfs-instrumentos|{fid}|{name}"
                rec: dict[str, Any] = {
                    "id": _stable_id("proy", key),
                    "municipio": "Montilla",
                    "titulo": titulo[:500],
                    "fecha": fecha,
                    "tipo": (tipo or grp or "instrumento planeamiento")[:200],
                    "url": f"{VISOR_BASE}/visor",
                    "source": "ayuntamiento",
                    "descripcion": desc[:1200] if desc else None,
                    "origen": "wfs_instrumentos",
                    "instrument_id": fid,
                    "instrument_type_group": grp or None,
                    "instrument_type": tipo or None,
                    "expte": str(fid) if fid is not None else None,
                    "expediente": str(fid) if fid is not None else None,
                }
                cleaned = _clean_geojson_geometry(geom if isinstance(geom, dict) else None)
                if cleaned:
                    rec["geom_geojson"] = cleaned
                    rec["geometry_source"] = "portal_wfs_geoserver"
                    rec["geometry_source_url"] = geom_url
                    rec["coord_source"] = "portal_geometry_centroid"
                rows.append(rec)
            if len(feats) < page_size:
                break
            start += page_size
        return rows

    def _collect_licencias_info(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for url in self._lic_pages:
            try:
                html = self._fetch(url)
            except (urllib.error.URLError, OSError):
                continue
            title_m = re.search(r"<title>([^<]+)</title>", html, re.I)
            title = (title_m.group(1).strip() if title_m else url.rsplit("/", 1)[-1])[:500]
            if not RE_LICENCIA.search(title + url):
                continue
            pdf_m = re.search(r'href="(https://montilla\.es/wp-content/uploads/[^"]+\.pdf)"', html, re.I)
            rec: dict[str, Any] = {
                "id": _stable_id("lic", url),
                "fecha_concesion": None,
                "tipo": "trámite licencia (información)",
                "distrito": None,
                "lat": MUNICIPIO_CENTROID_LAT,
                "lon": MUNICIPIO_CENTROID_LON,
                "titulo": title,
                "url": url,
                "source": "ayuntamiento",
                "nota": "Página informativa de trámites; no hay concesión fechada en HTML estático.",
                "coord_source": "municipio_centroid_reference",
            }
            if pdf_m:
                rec["pdf_url"] = pdf_m.group(1)
            rows.append(rec)
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        out: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out

    def _merge_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for rec in self._instrumentos_proyectos() + self._rss_noticias_urbanismo():
            i = rec.get("id")
            if i and i not in seen:
                seen.add(str(i))
                merged.append(rec)
        return merged

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias_info()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "tramites_wp"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias_info():
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
        rows = self._merge_proyectos()
        self._write_jsonl(out_jsonl, rows)
        n_geom = sum(1 for r in rows if isinstance(r.get("geom_geojson"), dict))
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs_instrumentos": sum(1 for r in rows if r.get("origen") == "wfs_instrumentos"),
            "rss": sum(1 for r in rows if r.get("origen") == "rss_urbanismo"),
            "with_geometry_hint": n_geom,
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
