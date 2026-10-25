from __future__ import annotations

import hashlib
import json
import re
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

BASE = "https://www.santfeliu.cat"
TAULER_URL = "https://tauler.seu.cat/inici.do?idens=821140003"
MUNICIPIO = "Sant Feliu de Llobregat"
ID_PREFIX = "sant-feliu-de-llobregat"
INE_MUN = "08211"

AMB_EXP_LAYER = (
    "https://geoportal.amb.cat/geoserveisapp/rest/services/"
    "Planejament/Expedients/MapServer/3"
)

NEWS_SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("22574", "planejament_en_tramit", "planeamiento en trámite"),
    ("22575", "planejament_vigent", "planeamiento vigente"),
    ("24146", "projectes_obres", "proyecto de obras"),
)

URBANISME_TRAMITS_HUB = f"{BASE}/go.faces?xmid=43497&caseid=sf:9799"

DEFAULT_LICENCIA_CASEIDS: tuple[str, ...] = (
    "sf:10433",
    "sf:121415",
    "sf:121417",
    "sf:121420",
    "sf:121429",
    "sf:121434",
    "sf:121441",
    "sf:121468",
)

RE_NEWS_ITEM = re.compile(
    r'href="(/go\.faces\?xmid=(\d+)(?:&amp;|&)newid=(\d+))"[^>]*class="headlineLink"[^>]*>'
    r'.*?class="headlineText">([^<]+)</span>',
    re.I | re.S,
)
RE_START_DAY = re.compile(r'<span class="startDay">(\d{2}/\d{2}/\d{4})</span>')
RE_REL_CASE = re.compile(
    r'href="[^"]*caseid=(sf:[^"&]+)[^"]*"[^>]*>\s*([^<]+?)\s*</a>',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licen[cs]ia|comunicaci[oó]n previa|declaraci[oó]n responsable|"
    r"obra (?:major|menor)|enderroc|autoritzaci[oó])",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _norm_text(text: str) -> str:
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", t).strip().lower()


def _clean(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str, section: str) -> str:
    n = blob.lower()
    if "projecte executiu" in n or "projecte d'obres" in n:
        return "proyecto ejecutivo"
    if "pla director" in n or "pdu" in n:
        return "plan director urbanización"
    if "modificaci" in n and "pgm" in n:
        return "modificación PGM"
    if "pla general metropolit" in n or "pgm" in n:
        return "planeamiento metropolitano"
    if "pmu" in n or "millora urbana" in n:
        return "plan mejora urbana"
    if "suspens" in n and "llic" in n:
        return "suspensión licencias"
    if section == "projectes_obres":
        return "proyecto de obras"
    if section == "planejament_vigent":
        return "planeamiento vigente"
    return "planeamiento en trámite"


class SantFeliuDeLlobregatAyuntamientoAdapter(AyuntamientoAdapter):
    """Seu JSF (noticies planejament/obres) + catàleg tràmits + AMB ArcGIS expedients."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        geom_cfg = self.config.get("geometry") or {}
        self.amb_exp_layer = str(geom_cfg.get("arcgis_expedients_layer") or AMB_EXP_LAYER)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._amb_cache: list[dict[str, Any]] | None = None
        self._amb_by_norm_name: dict[str, dict[str, Any]] | None = None

    def _ua(self) -> str:
        return str(self.config.get("user_agent") or "poc-bocm-sant-feliu-de-llobregat/1.0")

    def _fetch(self, url: str) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(url, headers={"User-Agent": self._ua()})
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str) -> Any:
        return json.loads(self._fetch(url))

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        with path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))
        return rows

    def _abs(self, href: str) -> str:
        return urllib.parse.urljoin(f"{BASE}/", href)

    def _parse_news_listing(self, html: str, xmid: str, section: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for m in RE_NEWS_ITEM.finditer(html):
            rel, mid, newid, title = m.group(1), m.group(2), m.group(3), _clean(m.group(4))
            url = self._abs(unescape(rel))
            rows.append(
                {
                    "titulo": title,
                    "url": url,
                    "newid": newid,
                    "xmid": mid or xmid,
                    "section": section,
                    "origen": "seu_noticies",
                }
            )
        return rows

    def _enrich_news_date(self, row: dict[str, Any]) -> None:
        try:
            html = self._fetch(row["url"])
        except urllib.error.URLError:
            return
        m = RE_START_DAY.search(html)
        if m:
            row["fecha"] = _parse_fecha_dmy(m.group(1))

    def _collect_portal_news(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for xmid, section, _label in NEWS_SECTIONS:
            url = f"{BASE}/go.faces?xmid={xmid}"
            try:
                html = self._fetch(url)
            except urllib.error.URLError:
                continue
            for row in self._parse_news_listing(html, xmid, section):
                self._enrich_news_date(row)
                rows.append(row)
        return rows

    def _news_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any]:
        titulo = row["titulo"]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row["url"]),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(titulo, row.get("section", "")),
            "url": row["url"],
            "source": "ayuntamiento",
            "origen": row.get("origen"),
            "seccion": row.get("section"),
        }
        if row.get("newid"):
            rec["portal_newid"] = row["newid"]
        self._enrich_geometry(rec)
        return rec

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

    def _apply_amb_geometry(self, rec: dict[str, Any], feat: dict[str, Any]) -> None:
        geom = feat.get("geometry")
        if not isinstance(geom, dict) or geom.get("type") not in {"Polygon", "MultiPolygon"}:
            return
        rec["geom_geojson"] = geom
        rec["geometry_crs"] = "EPSG:4326"
        rec["geometry_source"] = "portal_visor_arcgis"
        rec["geometry_source_url"] = f"{self.amb_exp_layer}/query"
        rec["coord_source"] = "portal_geometry_centroid"
        cent = geometry_centroid(geom)
        if cent:
            rec["lat"], rec["lon"] = cent

    def _enrich_geometry(self, rec: dict[str, Any]) -> None:
        if record_geometry(rec):
            return
        blob = f"{rec.get('titulo', '')} {rec.get('expte', '')}"
        feat = self._amb_hit_for_blob(blob)
        if feat:
            self._apply_amb_geometry(rec, feat)

    def _amb_to_proyecto(self, feat: dict[str, Any]) -> dict[str, Any]:
        props = feat.get("properties") or {}
        nom = _clean(str(props.get("NOMEXP") or "Expediente urbanístico"))
        dgu = str(props.get("DGU") or "").strip()
        url = str(props.get("URL") or "").strip() or f"{BASE}/go.faces?xmid=15761"
        rec: dict[str, Any] = {
            "id": _stable_id("proy", f"amb:{dgu or nom}"),
            "municipio": MUNICIPIO,
            "titulo": nom,
            "fecha": _parse_fecha_dmy(str(props.get("DAPRDEF") or "")),
            "tipo": _proyecto_tipo(nom, "amb_gis"),
            "url": url,
            "source": "ayuntamiento",
            "origen": "amb_expedients_gis",
        }
        if dgu:
            rec["expte"] = dgu
        self._apply_amb_geometry(rec, feat)
        return rec

    def _collect_licencia_tramites(self) -> list[dict[str, Any]]:
        caseids: set[str] = set(DEFAULT_LICENCIA_CASEIDS)
        try:
            html = self._fetch(URBANISME_TRAMITS_HUB)
            for m in RE_REL_CASE.finditer(html):
                cid, title = m.group(1), _clean(m.group(2))
                if RE_LICENCIA.search(title):
                    caseids.add(cid)
        except urllib.error.URLError:
            pass
        rows: list[dict[str, Any]] = []
        for cid in sorted(caseids):
            q = urllib.parse.urlencode({"xmid": "43497", "caseid": cid})
            url = f"{BASE}/go.faces?{q}"
            title = cid
            try:
                html = self._fetch(url)
                m = re.search(r'<h1 class="titol">([^<]+)</h1>', html, re.I)
                if m:
                    title = _clean(m.group(1))
            except urllib.error.URLError:
                pass
            if not RE_LICENCIA.search(title):
                continue
            rows.append(
                {
                    "id": _stable_id("lic", url),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": title,
                    "url": url,
                    "source": "ayuntamiento",
                    "origen": "catalogo_tramites",
                    "nota": (
                        "Trámite informativo sede JSF; concesiones en e-Tauler "
                        f"({TAULER_URL}) sin API pública scrapeable"
                    ),
                }
            )
        return rows

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows = self._collect_licencia_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "source": "catalogo_tramites"}

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
        by_id: dict[str, dict[str, Any]] = {}
        for row in self._collect_portal_news():
            rec = self._news_to_proyecto(row)
            by_id[rec["id"]] = rec
        for feat in self._load_amb_expedients():
            rec = self._amb_to_proyecto(feat)
            by_id[rec["id"]] = rec
        rows = list(by_id.values())
        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "portal_news": sum(1 for r in rows if r.get("origen") == "seu_noticies"),
            "amb_gis": sum(1 for r in rows if r.get("origen") == "amb_expedients_gis"),
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
