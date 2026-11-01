from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any

from municipio.adapters.portal import AyuntamientoAdapter
from municipio.geometry import geometry_centroid, record_geometry

WEB_BASE = "https://www.viladecans.cat"
SEDE_BASE = "https://seuelectronica.viladecans.cat"
MUNICIPIO = "Viladecans"
ID_PREFIX = "viladecans"
INE_MUN = "08301"

AMB_EXP_LAYER = (
    "https://geoportal.amb.cat/geoserveisapp/rest/services/"
    "Planejament/Expedients/MapServer/3"
)

CATALOGO_URL = f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO"
TABLON_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all"
)

DEFAULT_SEED_PAGES: list[str] = [
    f"{WEB_BASE}/ca/planejament-en-tramitacio",
    f"{WEB_BASE}/ca/planejament-vigent",
    f"{WEB_BASE}/ca/planejament-supramunicipal-en-tramitacio",
    f"{WEB_BASE}/ca/mapa-dusos-del-sol",
    f"{WEB_BASE}/ca/tramits-4",
]

DEFAULT_LICENCIA_TRAMITES: list[dict[str, str]] = [
    {
        "titulo": "Comunicació d'obres exemptes de llicència (en línia)",
        "url": f"{WEB_BASE}/ca/tramits-4",
        "tipo": "comunicación previa",
    },
    {
        "titulo": "Llicència d'obra menor d'enderrocs (en línia)",
        "url": f"{WEB_BASE}/ca/tramits-4",
        "tipo": "licencia de obra menor",
    },
    {
        "titulo": "Llicència d'obra menor de millores d'accessibilitat (en línia)",
        "url": f"{WEB_BASE}/ca/tramits-4",
        "tipo": "licencia de obra menor",
    },
    {
        "titulo": "Llicència d'obra menor de nova construcció (construccions auxiliars)",
        "url": f"{WEB_BASE}/ca/tramits-4",
        "tipo": "licencia de obra menor",
    },
    {
        "titulo": "Llicència d'obra menor o instal·lacions puntuals (en línia)",
        "url": f"{WEB_BASE}/ca/tramits-4",
        "tipo": "licencia de obra menor",
    },
    {
        "titulo": "Llicència d'obres de rehabilitació i/o manteniment (en línia)",
        "url": f"{WEB_BASE}/ca/tramits-4",
        "tipo": "licencia de obra",
    },
]

DEFAULT_PLANEJAMENT_FALLBACK: list[dict[str, Any]] = [
    {
        "titulo": "Pla de millora urbana del sector 1 del Polígon Industrial Centre",
        "url": f"{WEB_BASE}/ca/planejament-en-tramitacio",
        "tipo": "plan parcial",
        "origen": "drupal_fallback",
    },
    {
        "titulo": "Pla Especial Urbanístic de Desenvolupament — Ctra. de la Vila, 6",
        "url": f"{WEB_BASE}/ca/planejament-en-tramitacio",
        "tipo": "plan especial",
        "origen": "drupal_fallback",
    },
    {
        "titulo": "Pla Especial Urbanístic de l'Equipament Metropolità de la carretera de Sant Climent",
        "url": f"{WEB_BASE}/ca/planejament-en-tramitacio",
        "tipo": "plan especial",
        "origen": "drupal_fallback",
    },
    {
        "titulo": "Pla especial d'assignació d'usos — antic casino de l'Alba-Rosa",
        "url": f"{WEB_BASE}/ca/planejament-en-tramitacio",
        "tipo": "plan especial",
        "origen": "drupal_fallback",
    },
    {
        "titulo": "Pla Especial Urbanístic de Protecció i Catàleg del Patrimoni Cultural i Ambiental",
        "url": f"{WEB_BASE}/ca/planejament-en-tramitacio",
        "tipo": "plan especial",
        "origen": "drupal_fallback",
    },
]

LICENCIA_TRAMITE_PATTERNS: tuple[str, ...] = (
    "llicència",
    "licencia",
    "licència",
    "comunicació",
    "comunicacion",
    "declaració responsable",
    "obra menor",
    "obres",
    "enderroc",
    "urbanístic",
    "urbanistic",
    "parcel",
    "llicencia",
)

RE_LICENCIA = re.compile(
    r"(?i)(licen[cs]i[ao]|llicen[cs]i[ao]|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"autorizaci[oó]n (?:previa|urban)|obra (?:major|menor)|enderroc|primera ocupaci[oó]n)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|plan (?:parcial|especial|general)|pgou|peup|pepcv|"
    r"informaci[oó]n p[uú]blica|exposici[oó]n|expedient|projecte|proyecto|modificaci[oó]n|"
    r"reparcel|sector|àmbit|ambit|millora urbana|pol[ií]gon|edicte|suspensi[oó]n de llic)",
)
RE_NOISE = re.compile(
    r"(?i)(proceso selectivo|oposici[oó]n|empleo p[uú]blico|subvenci[oó]n|festa major|"
    r"cita pr[eè]via farm[aà]cia)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_EXPTE = re.compile(
    r"(?i)(?:exp(?:te)?\.?|expedient|n[uú]mero d.?expedient)\s*[:\.]?\s*"
    r"(\d{1,4}/[A-Z0-9-]+(?:\s+\d{4}/\d+[A-Z]?)?|\d{4}/\d+[A-Z]?)",
)
RE_PDF = re.compile(r'href="([^"]+\.pdf[^"]*)"', re.I)
RE_H2_BLOCK = re.compile(r"<h2[^>]*>(.*?)</h2>(.*?)(?=<h2|$)", re.I | re.S)
RE_DRUPAL_LINK = re.compile(r'href="([^"]+)"[^>]*>\s*([^<]{4,200})\s*</a>', re.I)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).lower().strip()


def _clean_title(text: str) -> str:
    t = unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", t).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                continue
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "millora urbana" in n or "polígon industrial" in n or "poligon industrial" in n:
        return "plan parcial"
    if "pla especial" in n or "peup" in n or "pepcv" in n:
        return "plan especial"
    if "modificaci" in n:
        return "modificación planeamiento"
    if "informaci" in n and "p" in n and "blica" in n:
        return "información pública"
    if "pgou" in n or "planejament vigent" in n:
        return "PGOU"
    if "mapa" in n and "sòl" in n:
        return "mapa usos del suelo"
    return "urbanismo"


def _fecha_from_pub_date(pub: dict[str, Any] | None) -> str | None:
    if not isinstance(pub, dict):
        return None
    try:
        return datetime(
            int(pub["year"]),
            int(pub["month"]),
            int(pub["day"]),
        ).strftime("%Y-%m-%d")
    except (KeyError, TypeError, ValueError):
        return None


class ViladecansAyuntamientoAdapter(AyuntamientoAdapter):
    """Drupal web (planejament) + sede STA (catálogo/tablón) + AMB expedients GIS."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.tablon_url = str(self.config.get("tablon_url") or TABLON_URL)
        geom_cfg = self.config.get("geometry") or {}
        self.amb_exp_layer = str(geom_cfg.get("arcgis_expedients_layer") or AMB_EXP_LAYER)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._amb_cache: list[dict[str, Any]] | None = None
        self._amb_by_norm_name: dict[str, dict[str, Any]] | None = None
        self._ssl_ctx = ssl.create_default_context()
        if self.config.get("sede_insecure_ssl", True):
            self._ssl_ctx.check_hostname = False
            self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._sede_timeout = float(self.config.get("sede_timeout_s", 25))

    def _ua(self) -> str:
        return str(
            self.config.get("user_agent")
            or "Mozilla/5.0 (compatible; poc-bocm-viladecans/1.0; +https://github.com/PabloMoran23/homes-bocm)"
        )

    def _fetch(self, url: str, sede: bool = False) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self._ua(),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ca,es;q=0.9,en;q=0.8",
                "Referer": f"{self.web_base}/",
            },
        )
        timeout = self._sede_timeout if sede else 60
        ctx = self._ssl_ctx if sede or self.sede_base in url else None
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read())

    def _abs_web(self, href: str) -> str:
        return urllib.parse.urljoin(f"{self.web_base}/", href)

    @staticmethod
    def _extract_sta_dataset(html: str, dataset_name: str) -> list[dict[str, Any]]:
        needle = f"var dataset_{dataset_name} = "
        start = html.find(needle)
        if start < 0:
            return []
        start += len(needle)
        end = html.find("];", start) + 1
        try:
            data = json.loads(html[start:end])
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []

    def _tramite_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO&lang=CA"
        )

    def _tablon_detail_url(self, dboid: str) -> str:
        return (
            f"{self.sede_base}/sta/CarpetaPublic/doEvent?"
            f"APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON&lang=CA"
        )

    def _catalog_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url, sede=True)
        except (urllib.error.URLError, TimeoutError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "CATSERV"):
            dboid = str(item.get("dboid") or "")
            name = _clean_title(str(item.get("name") or ""))
            if not name or not dboid:
                continue
            rows.append(
                {
                    "titulo": name,
                    "dboid": dboid,
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_sta",
                }
            )
        return rows

    def _tablon_rows(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.tablon_url, sede=True)
        except (urllib.error.URLError, TimeoutError):
            return []
        rows: list[dict[str, Any]] = []
        for item in self._extract_sta_dataset(html, "PTS2_TABLON"):
            dboid = str(item.get("dboid") or "")
            titulo = _clean_title(str(item.get("descriptionProc") or item.get("externString") or ""))
            if not titulo or not dboid:
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": _fecha_from_pub_date(item.get("pubDateIni")),
                    "url": self._tablon_detail_url(dboid),
                    "origen": "tablon_sta",
                }
            )
        return rows

    def _parse_drupal_planejament(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_H2_BLOCK.finditer(html):
            title = _clean_title(m.group(1))
            body = m.group(2)
            if not title or len(title) < 8:
                continue
            if not RE_PROYECTO.search(title) and not RE_PROYECTO.search(_clean_title(body)):
                continue
            pdfs = [self._abs_web(u) for u in RE_PDF.findall(body)]
            fecha = _parse_fecha_dmy(body)
            rows.append(
                {
                    "titulo": title,
                    "fecha": fecha,
                    "url": page_url,
                    "pdf_url": pdfs[0] if pdfs else None,
                    "nota": _clean_title(body)[:400],
                    "origen": "drupal_h2",
                }
            )
        return rows

    def _parse_drupal_tramits(self, html: str, page_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for href, label in RE_DRUPAL_LINK.findall(html):
            titulo = _clean_title(label)
            if not RE_LICENCIA.search(titulo) and "llic" not in titulo.lower():
                continue
            url = self._abs_web(href) if not href.startswith("http") else href
            rows.append(
                {
                    "titulo": titulo,
                    "url": url or page_url,
                    "origen": "drupal_tramits",
                }
            )
        return rows

    def _collect_web_docs(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        got_page = False
        for page_url in self.seed_pages:
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            got_page = True
            if "planejament" in page_url:
                rows.extend(self._parse_drupal_planejament(html, page_url))
            if "tramits" in page_url:
                rows.extend(self._parse_drupal_tramits(html, page_url))
        if not got_page:
            for item in DEFAULT_PLANEJAMENT_FALLBACK:
                rows.append(dict(item))
        return rows

    def _load_amb_expedients(self) -> list[dict[str, Any]]:
        if self._amb_cache is not None:
            return self._amb_cache
        features: list[dict[str, Any]] = []
        offset = 0
        page_size = 100
        where = urllib.parse.quote(f"CODI_INE='{self.ine_mun}'")
        base_query = (
            f"{self.amb_exp_layer}/query?"
            f"where={where}"
            "&outFields=NOMEXP%2CDGU%2CCMB%2CURL%2CDAPRDEF%2CVIGENT%2CNOMMUNI"
            "&returnGeometry=true&outSR=4326&f=geojson"
        )
        while True:
            url = f"{base_query}&resultOffset={offset}&resultRecordCount={page_size}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
                break
            batch = data.get("features") or []
            if not batch:
                break
            features.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        self._amb_cache = features
        by_name: dict[str, dict[str, Any]] = {}
        for feat in features:
            props = feat.get("properties") or {}
            nom = str(props.get("NOMEXP") or "").strip()
            if nom:
                by_name[_norm_text(nom)] = feat
        self._amb_by_norm_name = by_name
        return features

    def _amb_hit_for_blob(self, blob: str) -> dict[str, Any] | None:
        self._load_amb_expedients()
        by_name = self._amb_by_norm_name or {}
        norm_blob = _norm_text(blob)
        for nom_norm, feat in by_name.items():
            if len(nom_norm) >= 8 and nom_norm in norm_blob:
                return feat
        best: dict[str, Any] | None = None
        best_score = 0
        for nom_norm, feat in by_name.items():
            nom_tokens = [t for t in re.split(r"[\s,;/|()]+", nom_norm) if len(t) >= 4]
            score = sum(1 for t in nom_tokens if t in norm_blob)
            if score > best_score and score >= 2:
                best_score = score
                best = feat
        return best

    def _apply_amb_geometry(self, rec: dict[str, Any], feat: dict[str, Any], query_url: str) -> None:
        geom = feat.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in {"Polygon", "MultiPolygon"}:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_axis_order"] = "xy"
        rec["geometry_source"] = "portal_visor_arcgis"
        rec["geometry_source_url"] = query_url
        rec["coord_source"] = "portal_geometry_centroid"
        cent = geometry_centroid(geom)
        if cent:
            rec["lat"], rec["lon"] = cent

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = f"{rec.get('titulo', '')} {rec.get('nota', '')} {rec.get('expte', '')}"
        feat = self._amb_hit_for_blob(blob)
        if feat:
            self._apply_amb_geometry(rec, feat, f"{self.amb_exp_layer}/query?where=CODI_INE%3D%27{self.ine_mun}%27")

    def _amb_to_proyecto(self, feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        nom = _clean_title(str(props.get("NOMEXP") or "Expediente urbanístico"))
        dgu = str(props.get("DGU") or "").strip()
        url = str(props.get("URL") or "").strip() or f"{self.web_base}/ca/planejament-en-tramitacio"
        key = dgu or nom
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"amb:{key}"),
            "municipio": MUNICIPIO,
            "titulo": nom,
            "fecha": _parse_fecha_dmy(str(props.get("DAPRDEF") or "")),
            "tipo": _proyecto_tipo(nom),
            "url": url,
            "source": "ayuntamiento",
            "origen": "amb_expedients_gis",
        }
        if dgu:
            rec["expte"] = dgu
        self._apply_amb_geometry(
            rec,
            feat,
            f"{self.amb_exp_layer}/query?where=CODI_INE%3D%27{self.ine_mun}%27",
        )
        return rec

    def _collect_amb_proyectos(self) -> list[dict[str, Any]]:
        return [self._amb_to_proyecto(f) for f in self._load_amb_expedients()]

    def _tramite_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        lower = titulo.lower()
        if not any(p in lower for p in LICENCIA_TRAMITE_PATTERNS) and not RE_LICENCIA.search(titulo):
            return None
        if RE_NOISE.search(titulo) and "llicen" not in lower and "licen" not in lower:
            return None
        lic_key = f"{row['url']}|{titulo}"
        return {
            "id": _stable_id("lic", lic_key),
            "fecha_concesion": row.get("fecha"),
            "tipo": row.get("tipo") or "trámite licencia",
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo,
            "url": row["url"],
            "source": "ayuntamiento",
            "nota": row.get("nota") or "Trámite catálogo sede STA o web tràmits",
            "origen": row.get("origen"),
        }

    def _row_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        titulo = row["titulo"]
        blob = f"{titulo} {row.get('nota', '')}"
        if RE_LICENCIA.search(blob) and not RE_PROYECTO.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        key = row.get("pdf_url") or row.get("url") or titulo
        rec: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": row.get("tipo") or _proyecto_tipo(blob),
            "url": row.get("pdf_url") or row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
        }
        if row.get("nota"):
            rec["nota"] = row["nota"]
        if row.get("pdf_url"):
            rec["pdf_url"] = row["pdf_url"]
        m = RE_EXPTE.search(blob)
        if m:
            rec["expte"] = m.group(1).strip()
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

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []
        for row in self._catalog_rows():
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._tablon_rows():
            if not RE_LICENCIA.search(row["titulo"]):
                continue
            rec = self._tramite_to_licencia({**row, "tipo": "licencia publicada", "nota": "Tablón STA"})
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for row in self._collect_web_docs():
            if "drupal_tramits" not in str(row.get("origen")):
                continue
            rec = self._tramite_to_licencia(row)
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        for item in DEFAULT_LICENCIA_TRAMITES:
            rec = self._tramite_to_licencia({**item, "origen": "tramits_web_fallback"})
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)
        return rows

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for row in self._collect_web_docs():
            if row.get("origen") == "drupal_tramits":
                continue
            add(self._row_to_proyecto(row))
        for row in self._tablon_rows():
            add(self._row_to_proyecto({**row, "nota": "Tablón edictes STA"}))
        for rec in self._collect_amb_proyectos():
            add(rec)
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencias()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "sede_sta_web"}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_proyectos()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "drupal_web_amb_gis"}

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_proyectos():
            if rec["id"] not in existing:
                existing[rec["id"]] = rec
                added += 1
        rows = list(existing.values())
        self._write_jsonl(out_jsonl, rows)
        state_path.write_text(
            json.dumps(
                {"last_run": datetime.now(timezone.utc).isoformat(), "count": len(rows), "added": added},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {"rows": len(rows), "added": added, "status": "ok"}
