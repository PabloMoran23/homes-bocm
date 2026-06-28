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

BASE = "https://www.majadahonda.org"
MUNICIPIO = "Majadahonda"
ID_PREFIX = "majadahonda"
WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
WFS_TYPE = "sitcm:VPLA_V_AMBITO"

DEFAULT_LISTING_PAGES: list[str] = [
    f"{BASE}/informacion-publica-anuncios-urbanisticos",
    f"{BASE}/anuncios-urbanisticos",
]

DEFAULT_PLANEAMIENTO_PAGES: list[str] = [
    f"{BASE}/planes-parciales",
    f"{BASE}/planes-especiales",
    f"{BASE}/estudios-de-detalle",
    f"{BASE}/planeamiento-urban%C3%ADstico",
    f"{BASE}/disciplina-urbanistica",
]

DEFAULT_LICENCIA_SLUGS: list[str] = [
    "licencia-urbanistica-de-obras-lic-01-obras-cuc-",
    "declaracion-responsable-de-obras-que-requieren-titulo-habilitante-y-no-estan-sujetas-a-licencia-dr-02a-obras-",
    "licencia-urbanistica-de-implantacion-o-modificacion-de-actividades-lic-02-ima-obras-",
    "declaracion-responsable-urbanistica-de-actividades-implantacion-o-modificacion-que-requieren-titulo-habilitante-pero-no-esten-sujetas-a-licencia-dr--1",
    "licencia-urbanistica-de-funcionamiento-de-actividades",
    "solicitud-de-licencia-de-parcelacion-lic-04-parcelacion-",
    "declaracion-responsable-de-agrupacion-de-parcelas-dr-06-agrupacion-parcelas-",
    "declaracion-responsable-de-primera-ocupacion-y-funcionamiento-de-actuaciones-que-hayan-sido-objeto-de-licencia-urbanistica",
]

RE_TITLE_LINK = re.compile(
    r'<a[^>]*href="([^"]+)"[^>]*class="title"[^>]*>([^<]+)</a>',
    re.I,
)
RE_PUB_DATE = re.compile(r"Fecha de publicación</span>\s*(\d{1,2}/\d{1,2}/\d{2,4})")
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{2,4})")
RE_FECHA_ES = re.compile(
    r"(\d{1,2})\s+"
    r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)"
    r"\s+(\d{4})",
    re.I,
)
RE_DOC_PDF = re.compile(
    r'href="((?:https://www\.majadahonda\.org)?/documents/\d+/\d+/[^"]+\.pdf[^"]*)"',
    re.I,
)
RE_IMPRESO_LINK = re.compile(
    r'href="(https://www\.majadahonda\.org/urbanismo-impresos/-/asset_publisher/[^"]+/content/[^"?#]+)"',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(licencia|declaraci[oó]n responsable|comunicaci[oó]n previa|autorizaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planeam|plan |pgou|convenio|informaci[oó]n p[uú]blica|expediente|"
    r"modificaci[oó]n|estudio de detalle|reparcel|aprobaci[oó]n|sector|parcial|especial)",
)

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

SKIP_PDF = re.compile(r"(?i)registro\+de\+actividades")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if y < 100:
        y += 2000
    try:
        return datetime(y, mo, d).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_fecha_es(text: str) -> str | None:
    m = RE_FECHA_ES.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), MESES[m.group(2).lower()], int(m.group(1))).strftime(
            "%Y-%m-%d"
        )
    except (ValueError, KeyError):
        return None


def _parse_fecha(text: str) -> str | None:
    return _parse_fecha_dmy(text) or _parse_fecha_es(text)


def _abs_url(href: str) -> str:
    return urllib.parse.urljoin(f"{BASE}/", href)


def _proyecto_tipo(title: str) -> str:
    n = title.lower()
    if "plan especial" in n or "pem " in n:
        return "plan especial"
    if "plan parcial" in n or "sector p." in n or "sector pp" in n:
        return "plan parcial"
    if "estudio de detalle" in n:
        return "estudio de detalle"
    if "modificaci" in n and "pgou" in n:
        return "modificación PGOU"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n or "exposici" in n:
        return "información pública"
    if "ordenanza" in n:
        return "normativa urbanística"
    return "planeamiento"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for feat in features:
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Polygon" and isinstance(coords, list):
            polys.append(coords)
        elif gtype == "MultiPolygon" and isinstance(coords, list):
            polys.extend(coords)
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


class MajadahondaAyuntamientoAdapter(AyuntamientoAdapter):
    """Liferay portal: anuncios IP urbanísticos + planeamiento + trámites licencia."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.listing_pages = [str(u) for u in (self.config.get("listing_pages") or DEFAULT_LISTING_PAGES)]
        self.planeamiento_pages = [
            str(u) for u in (self.config.get("planeamiento_pages") or DEFAULT_PLANEAMIENTO_PAGES)
        ]
        self.licencia_slugs = list(self.config.get("licencia_slugs") or DEFAULT_LICENCIA_SLUGS)
        self._ambit_cache: list[dict[str, Any]] | None = None
        self._ambit_names: list[str] | None = None

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-majadahonda/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", "poc-bocm-majadahonda/1.0")},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _parse_listing_page(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_TITLE_LINK.finditer(html):
            url = m.group(1).split("#")[0]
            title = unescape(re.sub(r"\s+", " ", m.group(2))).strip()
            if not title or not RE_PROYECTO.search(title):
                continue
            chunk = html[m.start() : m.start() + 1500]
            pub = RE_PUB_DATE.search(chunk)
            fecha = _parse_fecha_dmy(pub.group(1)) if pub else None
            rows.append(
                {
                    "id": _stable_id("proy", url),
                    "municipio": MUNICIPIO,
                    "titulo": title[:500],
                    "fecha": fecha,
                    "tipo": _proyecto_tipo(title),
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "anuncios_ip",
                    "listado_url": page_url,
                }
            )
        return rows

    def _enrich_detail(self, rec: dict[str, Any]) -> None:
        url = str(rec.get("url") or "")
        if not url or "asset_publisher" not in url:
            return
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return
        if not rec.get("fecha"):
            rec["fecha"] = _parse_fecha_es(html) or _parse_fecha_dmy(html)
        pdfs = [
            _abs_url(p.split("#")[0])
            for p in RE_DOC_PDF.findall(html)
            if not SKIP_PDF.search(p)
        ]
        if pdfs:
            rec["pdf_url"] = pdfs[0]
        self._attach_geometry(rec)

    def _collect_listing_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for page_url in self.listing_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for rec in self._parse_listing_page(html, page_url):
                if rec["id"] in seen:
                    continue
                seen.add(rec["id"])
                self._enrich_detail(rec)
                rows.append(rec)
        return rows

    def _collect_planeamiento_pdfs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url in self.planeamiento_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            page_title = ""
            tm = re.search(r"<h[12][^>]*>([^<]+)", html, re.I)
            if tm:
                page_title = unescape(tm.group(1).strip())[:120]
            for pdf in RE_DOC_PDF.findall(html):
                if SKIP_PDF.search(pdf):
                    continue
                pdf_url = _abs_url(pdf.split("#")[0])
                rec_id = _stable_id("proy", pdf_url)
                if rec_id in seen:
                    continue
                seen.add(rec_id)
                name = unescape(urllib.parse.unquote(Path(pdf_url).name))[:500]
                titulo = name if len(name) > 8 else f"{page_title}: {name}"
                rec = {
                    "id": rec_id,
                    "municipio": MUNICIPIO,
                    "titulo": titulo,
                    "fecha": None,
                    "tipo": "documento planeamiento",
                    "url": page_url,
                    "pdf_url": pdf_url,
                    "source": "ayuntamiento",
                    "origen": "planeamiento",
                }
                self._attach_geometry(rec)
                rows.append(rec)
        return rows

    def _load_ambitos(self) -> tuple[list[dict[str, Any]], list[str]]:
        if self._ambit_cache is not None and self._ambit_names is not None:
            return self._ambit_cache, self._ambit_names
        cql = "DS_MUNICIPIO='MAJADAHONDA'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "200",
                "CQL_FILTER": cql,
            }
        )
        url = f"{WFS_BASE}?{params}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError):
            self._ambit_cache = []
            self._ambit_names = []
            return self._ambit_cache, self._ambit_names
        feats = data.get("features") if isinstance(data, dict) else []
        self._ambit_cache = [f for f in feats or [] if isinstance(f, dict)]
        self._ambit_names = sorted(
            {
                str(f.get("properties", {}).get("DS_NOMB_AMB") or "")
                for f in self._ambit_cache
                if f.get("properties", {}).get("DS_NOMB_AMB")
            }
        )
        return self._ambit_cache, self._ambit_names

    def _match_ambit_name(self, title: str, names: list[str]) -> str | None:
        t = title.lower()
        keywords: list[str] = []
        for q in re.findall(r'[«"]([^»"]+)[»"]', title):
            keywords.extend(w for w in re.split(r"[\s,]+", q.strip()) if len(w) >= 4)
        keywords.extend(m.group(1) for m in re.finditer(r"Sector\s+([A-Z0-9.\-]+)", title, re.I))
        for m in re.finditer(
            r"(?:Urbanización|urbanizaci[oó]n)\s+([A-Za-zÁÉÍÓÚáéíóúñÑ\s]+?)"
            r"(?:\s+establecido|\s+en\s|\s+del\s|$)",
            title,
            re.I,
        ):
            keywords.append(m.group(1).strip())
        for token in (
            "Arcipreste",
            "Leontina",
            "Nortron",
            "Carralero",
            "Pinar",
            "Satélites",
            "Satelites",
            "Montepríncipe",
            "Monteprincipe",
            "Granadilla",
            "Paular",
            "Cementerio",
            "Plantío",
            "Plantio",
            "Cerro del Espino",
            "Guadarrama",
        ):
            if token.lower() in t:
                keywords.append(token)
        keywords = list(dict.fromkeys(k for k in keywords if k))
        best: str | None = None
        best_score = 0
        for name in names:
            nf = name.lower()
            score = 0
            for kw in keywords:
                kl = kw.lower()
                if kl in nf or nf in kl:
                    score += 10
                else:
                    for part in re.split(r"[\s\-]+", kl):
                        if len(part) >= 4 and part in nf:
                            score += 3
            if score > best_score:
                best_score = score
                best = name
        return best if best_score >= 6 else None

    def _fetch_geometry(self, title: str) -> dict[str, Any] | None:
        feats, names = self._load_ambitos()
        if not feats or not names:
            return None
        ambit = self._match_ambit_name(title, names)
        if not ambit:
            return None
        chosen = [f for f in feats if str(f.get("properties", {}).get("DS_NOMB_AMB")) == ambit]
        merged = _merge_geometries(chosen)
        if not merged:
            return None
        cql = f"DS_MUNICIPIO='MAJADAHONDA' AND DS_NOMB_AMB='{ambit.replace(chr(39), chr(39)*2)}'"
        params = urllib.parse.urlencode(
            {
                "service": "WFS",
                "version": "2.0.0",
                "request": "GetFeature",
                "typeName": WFS_TYPE,
                "outputFormat": "application/json",
                "srsName": "EPSG:4326",
                "count": "20",
                "CQL_FILTER": cql,
            }
        )
        query_url = f"{WFS_BASE}?{params}"
        return {
            "geom_geojson": merged,
            "geometry_source": "portal_wfs",
            "geometry_source_url": query_url,
            "coord_source": "portal_geometry_centroid",
            "geometry_ambit": ambit,
        }

    def _attach_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        title = str(rec.get("titulo") or "")
        geom = self._fetch_geometry(title)
        if not geom:
            return
        rec.update(geom)
        centroid = geometry_centroid(geom["geom_geojson"])
        if centroid:
            rec["lat"], rec["lon"] = centroid

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        try:
            html = self._fetch(f"{BASE}/urbanismo-impresos")
        except urllib.error.URLError:
            html = ""
        links: list[str] = []
        if html:
            for m in RE_IMPRESO_LINK.finditer(html):
                slug = m.group(1).split("/content/")[-1].rstrip("-")
                if slug in self.licencia_slugs or RE_LICENCIA.search(slug.replace("-", " ")):
                    links.append(m.group(1).split("#")[0])
        if not links:
            publisher = "BSAuZu43Knd3"
            for slug in self.licencia_slugs:
                links.append(
                    f"{BASE}/urbanismo-impresos/-/asset_publisher/{publisher}/content/{slug}"
                )
        for url in dict.fromkeys(links):
            slug = url.split("/content/")[-1].rstrip("-").replace("-", " ")
            titulo = unescape(slug.title())[:500]
            rec_id = _stable_id("lic", url)
            if rec_id in seen:
                continue
            seen.add(rec_id)
            rows.append(
                {
                    "id": rec_id,
                    "fecha_concesion": None,
                    "tipo": titulo[:120],
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Página informativa de trámite; no concesión publicada en tablón",
                }
            )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "urbanismo_impresos"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencia_tramites():
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for rec in self._collect_listing_proyectos():
            add(rec)
        for rec in self._collect_planeamiento_pdfs():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "anuncios_ip": sum(1 for r in rows if r.get("origen") == "anuncios_ip"),
            "planeamiento_docs": sum(1 for r in rows if r.get("origen") == "planeamiento"),
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
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": after, "added": max(0, after - before), "status": "ok"}
