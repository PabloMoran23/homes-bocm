from __future__ import annotations

from municipio.onboarding_snapshot import reviewed_records

import hashlib
import json
import re
import time
import unicodedata
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

WEB_BASE = "https://svh.cat"
MUNICIPIO = "Sant Vicenç dels Horts"
ID_PREFIX = "sant-vicenc-dels-horts"
INE_MUN = "08263"

SEU_INSTANCIA = "https://seu-e.cat/tramits/826340003/instancia-generica"
URBANISME_GOT = f"{WEB_BASE}/govern-obert-transparencia/accio-de-govern-i-normativa/urbanisme-got/"
URBANISME_HUB = f"{WEB_BASE}/municipi/per-temes/territori-i-mobilitat/urbanisme/"
RPUC_MUNICI = (
    "https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do"
    f"?reqCode=cerca&municipiSel={INE_MUN}"
)
MUC_VISOR = f"https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi={INE_MUN}&set-locale=ca"
AMB_GEOPORTAL = "https://geoportalplanejament.amb.cat/AppGeoportalPlanejament2/index.html"
AMB_EXP_PDF = f"https://geoportalplanejament.amb.cat/Informacio/Llistats_expedients/b/{INE_MUN}_b.pdf"

AMB_EXP_LAYER = (
    "https://geoportal.amb.cat/geoserveisapp/rest/services/"
    "Planejament/Expedients/MapServer/3"
)

DEFAULT_SEED_PAGES: list[str] = [
    URBANISME_GOT,
    URBANISME_HUB,
    f"{WEB_BASE}/pla-urbanistic/",
    f"{WEB_BASE}/actualitat/noticies/materia/territori-urbanisme/",
    RPUC_MUNICI,
    MUC_VISOR,
    AMB_GEOPORTAL,
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licencia|comunicaci[oó] pr[eè]via|declaraci[oó] responsable|"
    r"primera ocupaci[oó]|obra|ocupaci[oó] de la via|gual|parcellaci[oó]|"
    r"certificat d.?aprofitament urban)",
)
RE_LICENCIA_SKIP = re.compile(
    r"(?i)(targeta rosa|bus urba|passi metropolita|carnet|zona pacificada|"
    r"exempci[oó] de residus|familia monoparental|familia nombrosa|artificis pirot)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|planeam|pgm|pgou|peu\b|modificaci[oó]|reparcel|"
    r"expedient|projecte d.?urban|aprovaci[oó]|informaci[oó] p[uú]blica|"
    r"sector|àmbit|ambit|rpuc|muc|geoportal|normativa urban|agenda urbana)",
)
RE_NOISE = re.compile(
    r"(?i)(setmana europea de la mobilitat|skate-park|pump-track|mobiliari|"
    r"audiovisual|llar d.?infants|memoria valorada d.?obres de reforma|"
    r"zona d.?um|estacionament regulat|coordinaci[oó].*semafor)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")
RE_SITEMAP_LOC = re.compile(r"<loc>([^<]+)</loc>")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str, lastmod: str | None = None) -> str | None:
    d = _parse_fecha_dmy(text)
    if d:
        return d
    if lastmod and re.match(r"\d{4}-\d{2}-\d{2}", lastmod):
        return lastmod[:10]
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1985 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgm" in n or "pla general metropolit" in n:
        return "modificación PGM"
    if "peu" in n or "pla especial" in n:
        return "plan especial"
    if "reparcel" in n:
        return "reparcelación"
    if "projecte d'urban" in n or "projecte d'urban" in n or "urbanitz" in n:
        return "proyecto de urbanización"
    if "agenda urbana" in n:
        return "agenda urbana"
    if "informaci" in n or "aprovaci" in n:
        return "información pública / trámite"
    if "rpuc" in n or "muc" in n or "geoportal" in n:
        return "planeamiento / visor"
    return "urbanismo"


class SantVicencDelsHortsAyuntamientoAdapter(AyuntamientoAdapter):
    """WordPress svh.cat + Geoportal AMB ArcGIS (expedients) + RPUC/MUC (Gencat)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.seed_pages = [str(u) for u in (self.config.get("seed_pages") or DEFAULT_SEED_PAGES)]
        geom_cfg = self.config.get("geometry") or {}
        self.amb_exp_layer = str(geom_cfg.get("arcgis_expedients_layer") or AMB_EXP_LAYER)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._amb_cache: list[dict[str, Any]] | None = None
        self._amb_by_norm_name: dict[str, dict[str, Any]] | None = None

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-sant-vicenc-dels-horts/1.0")

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"{self._ua()} Mozilla/5.0 (X11; Linux x86_64)",
                "Accept": "text/html,application/xhtml+xml,application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    def _sitemap_urls(self, sitemap_path: str, url_filter: re.Pattern[str] | None = None) -> list[str]:
        try:
            xml = self._fetch(f"{self.web_base}/{sitemap_path.lstrip('/')}")
        except urllib.error.URLError:
            return []
        urls = RE_SITEMAP_LOC.findall(xml)
        out: list[str] = []
        for u in urls:
            if not u.startswith(self.web_base):
                continue
            if url_filter and not url_filter.search(u):
                continue
            out.append(u.split("#")[0])
        return list(dict.fromkeys(out))

    def _page_title(self, html: str, fallback: str = "") -> str:
        for pat in (r"<h1[^>]*>([^<]+)", r"<title>([^<]+)"):
            m = re.search(pat, html, re.I)
            if m:
                t = _clean_title(m.group(1))
                t = re.sub(r"\s*[-|].*Sant Vicen.*$", "", t, flags=re.I).strip()
                if len(t) > 3:
                    return t[:500]
        return fallback[:500]

    def _load_amb_expedients(self) -> list[dict[str, Any]]:
        if self._amb_cache is not None:
            return self._amb_cache
        features: list[dict[str, Any]] = []
        offset = 0
        page_size = 100
        base_query = (
            f"{self.amb_exp_layer}/query?"
            f"where=CODI_INE%3D%27{self.ine_mun}%27"
            "&outFields=NOMEXP%2CDGU%2CCMB%2CURL%2CDAPRDEF%2CVIGENT"
            "&returnGeometry=true&outSR=4326&f=geojson"
        )
        while True:
            url = f"{base_query}&resultOffset={offset}&resultRecordCount={page_size}"
            try:
                data = self._fetch_json(url)
            except (urllib.error.URLError, json.JSONDecodeError):
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

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = f"{rec.get('titulo', '')} {rec.get('nota', '')}"
        feat = self._amb_hit_for_blob(blob)
        if feat:
            self._apply_amb_geometry(rec, feat, f"{self.amb_exp_layer}/query")

    def _amb_to_proyecto(self, feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        nom = _clean_title(str(props.get("NOMEXP") or "Expediente urbanístico"))
        dgu = str(props.get("DGU") or "").strip()
        url = str(props.get("URL") or "").strip() or AMB_GEOPORTAL
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"amb:{dgu or nom}"),
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
        vigent = props.get("VIGENT")
        if vigent is not None:
            rec["estado"] = "vigente" if str(vigent) == "1" else "histórico"
        self._apply_amb_geometry(rec, feat, f"{self.amb_exp_layer}/query")
        return rec

    def _build_wp_proyecto(self, url: str) -> dict[str, Any] | None:
        if RE_NOISE.search(url):
            return None
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            slug = url.rstrip("/").split("/")[-1].replace("-", " ")
            titulo = slug[:500]
            rec: dict[str, Any] = {
                "id": _stable_id("proy", url),
                "municipio": MUNICIPIO,
                "titulo": titulo,
                "fecha": _fecha_from_blob(slug, None),
                "tipo": _proyecto_tipo(titulo),
                "url": url,
                "source": "ayuntamiento",
                "origen": "svh_sitemap",
            }
            return rec if RE_PROYECTO.search(titulo) else None

        titulo = self._page_title(html, fallback=url.split("/")[-1].replace("-", " "))
        blob = _strip_html(html)[:5000]
        if not RE_PROYECTO.search(f"{titulo} {blob} {url}") and "urbanisme" not in url:
            return None
        return {
            "id": _stable_id("proy", url),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": _fecha_from_blob(f"{titulo} {blob}", None),
            "tipo": _proyecto_tipo(f"{titulo} {blob}"),
            "url": url,
            "source": "ayuntamiento",
            "origen": "svh_wordpress",
            "nota": blob[:350],
        }

    def _collect_proyectos(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any] | None) -> None:
            if rec and rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for feat in self._load_amb_expedients():
            add(self._amb_to_proyecto(feat))

        wp_filter = re.compile(
            r"(?i)(/projecte-d|/pla-especial|/pla-urbanistic|reparcel|modificacio-puntual|"
            r"/urbanisme/[^/]+$|aprovacio-inicial-projecte)",
        )
        for url in self._sitemap_urls("page-sitemap.xml", wp_filter):
            add(self._build_wp_proyecto(url))

        for seed in (URBANISME_GOT, URBANISME_HUB, f"{self.web_base}/pla-urbanistic/"):
            add(self._build_wp_proyecto(seed))

        return rows

    def _tramit_page_title(self, url: str) -> str:
        try:
            html = self._fetch(url)
        except urllib.error.URLError:
            return url.rstrip("/").split("/")[-1].replace("-", " ")[:250]
        return self._page_title(html, fallback=url.split("/")[-1].replace("-", " "))

    def _collect_licencias(self) -> list[dict[str, Any]]:
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for url in self._sitemap_urls("tramits-sitemap.xml", RE_LICENCIA):
            if RE_LICENCIA_SKIP.search(url):
                continue
            titulo = self._tramit_page_title(url)
            add(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite urbanismo (WordPress)",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Ficha trámite svh.cat; presentación telemática vía instancia genérica",
                }
            )

        static_lic = [
            (SEU_INSTANCIA, "Instància genèrica — seu-e.cat (826340003)"),
            (
                f"{WEB_BASE}/tramita/tramits/llicencia-urbanistica-dobres/",
                "Llicència urbanística d'obres",
            ),
            (
                "https://carpeta.svh.cat",
                "Carpeta ciutadana — consulta expedients (certificat digital)",
            ),
        ]
        for url, titulo in static_lic:
            add(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia / sede",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": titulo,
                    "url": url,
                    "source": "ayuntamiento",
                    "nota": "Sin tablón público de licencias concedidas",
                }
            )
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        rows = reviewed_records(path, rows)
        path.parent.mkdir(parents=True, exist_ok=True)
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
        raw = self._collect_licencias()
        self._write_jsonl(out_jsonl, raw)
        kept = self._load_jsonl(out_jsonl)
        return {"rows": len(kept), "status": "ok", "source": "svh_tramits_seu_e", "candidates": len(raw)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        existing = {r["id"]: r for r in self._load_jsonl(out_jsonl)}
        added = 0
        for rec in self._collect_licencias():
            if rec["id"] not in existing:
                added += 1
            existing[rec["id"]] = rec
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
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "with_geometry": with_geom,
            "status": "ok",
            "source": "amb_gis_svh_wordpress",
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
                    "with_geometry": stats.get("with_geometry", 0),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return {
            "rows": after,
            "added": max(0, after - before),
            "with_geometry": stats.get("with_geometry", 0),
            "status": "ok",
        }
