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

SEDE_BASE = "https://tramits.vilafranca.cat"
URBANISME_WEB = "https://urbanisme.vilafranca.cat"
EIXDIARI_BASE = "https://www.eixdiari.cat"
MUNICIPIO = "Vilafranca del Penedès"
ID_PREFIX = "vilafranca-del-penedes"
INE_MUN = "08305"

CATALOGO_URL = (
    f"{SEDE_BASE}/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=CA"
)
EIXDIARI_LIST_URL = f"{EIXDIARI_BASE}/serveis/anuncis-oficials/vilafranca-del-penedes/"

WFS_BASE = "https://sig.gencat.cat/ows/PLANEJAMENT/wfs"
WFS_TYPE_SECTOR = "PLANEJAMENT:MUC_PDERIVAT_SECTOR"

DEFAULT_STATIC_PROYECTOS: list[dict[str, str]] = [
    {
        "url": f"{URBANISME_WEB}/planejament-i-llicencies/poum",
        "titulo": "POUM vigent — Pla d'Ordenació Urbanística Municipal",
        "tipo": "POUM",
        "fecha": "2004-01-26",
    },
    {
        "url": f"{URBANISME_WEB}/planejament-i-llicencies/planejament-derivat",
        "titulo": "Planejament derivat (PAU, plans parcials, SUD)",
        "tipo": "planejament derivat",
        "fecha": "",
    },
    {
        "url": f"{URBANISME_WEB}/planejament-i-llicencies/visor-del-portal-urbanistic",
        "titulo": "Visor del portal urbanístic i geoportal municipal",
        "tipo": "visor urbanístic",
        "fecha": "",
    },
]

RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|obra|ocupaci[oó]n|parcel|grua|horitzont|primera ocupaci|"
    r"comunicaci[oó]n previa|declaraci[oó]n responsable|canvi d'ús|assabentat)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|pau|poum|pgou|peeu|millora urb|plan (?:parcial|especial)|"
    r"conveni urban|exposici[oó]n|informaci[oó]n p[uú]blica|expedient|edict|"
    r"reparcel|sector|modificaci[oó]|habitatge social|demanial|rehabilit)",
)
RE_NOISE = re.compile(
    r"(?i)(mercat|jurats?|subvenci[oó]n|ordenan[cç]a fiscal|llars? d'infants|"
    r"rebuts?|aig[uü]es de vilafranca|mostra d'entitats|sorteig)",
)
RE_FECHA_EXPO = re.compile(r"Exposici[oó]\s*(\d{2})-(\d{2})-(\d{4})", re.I)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

PLANNING_TRAMITE_NAMES = (
    "plans parcials",
    "plans especials",
    "plans de millora urbana",
    "projectes d'urbanització",
    "projectes de reparcel·lació",
    "constitució i dissolució",
)


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _clean_title(text: str) -> str:
    return unescape(re.sub(r"\s+", " ", text or "")).strip()[:500]


def _parse_fecha_dmy(text: str) -> str | None:
    m = RE_FECHA_DMY.search(text or "")
    if not m:
        return None
    try:
        return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _fecha_from_blob(text: str) -> str | None:
    m = RE_FECHA_EXPO.search(text or "")
    if m:
        try:
            return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
        except ValueError:
            pass
    dmy = _parse_fecha_dmy(text)
    if dmy:
        return dmy
    years = [int(x.group(1)) for x in RE_YEAR.finditer(text or "") if 1980 <= int(x.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _fecha_from_wfs(pub: str | None, expedient: str | None) -> str:
    if expedient:
        m = re.search(r"/(\d{4})", expedient)
        if m:
            return f"{m.group(1)}-01-01"
    if pub and len(pub) >= 4:
        y = pub[:4]
        if y.isdigit() and 1980 <= int(y) <= 2035:
            return f"{y}-01-01"
    return ""


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pau" in n or "millora urb" in n:
        return "PAU / millora urbana"
    if "plan parcial" in n or "pla parcial" in n:
        return "plan parcial"
    if "plan especial" in n or "pla especial" in n:
        return "plan especial"
    if "reparcel" in n:
        return "reparcelación"
    if "urbaniz" in n:
        return "urbanización"
    if "poum" in n or "pgou" in n:
        return "POUM"
    if "conveni" in n:
        return "convenio urbanístico"
    if "informaci" in n or "exposici" in n or "edict" in n:
        return "información pública"
    if "llic" in n or "obra" in n:
        return "licencia / obra"
    return "planeamiento"


class VilafrancaDelPenedesAyuntamientoAdapter(AyuntamientoAdapter):
    """STA tramits.vilafranca.cat + anuncis eixdiari + planejament WFS Generalitat (MUC)."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or SEDE_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.sede_base = str(self.config.get("sede_base") or SEDE_BASE).rstrip("/")
        self.catalogo_url = str(self.config.get("catalogo_url") or CATALOGO_URL)
        self.eixdiari_url = str(self.config.get("eixdiari_url") or EIXDIARI_LIST_URL)
        self.static_proyectos = list(self.config.get("static_proyectos") or DEFAULT_STATIC_PROYECTOS)
        geom_cfg = self.config.get("geometry") or {}
        self.wfs_base = str(geom_cfg.get("wfs_url") or WFS_BASE).rstrip("/")
        self.wfs_type = str(geom_cfg.get("type_name") or WFS_TYPE_SECTOR)
        self.ine_mun = str(geom_cfg.get("cod_ine_mun") or INE_MUN)
        self._wfs_browser_ua = str(
            geom_cfg.get("user_agent")
            or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self._sector_features: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, user_agent: str | None = None) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": user_agent
                or self.config.get("user_agent", "poc-bocm-vilafranca-del-penedes/1.0")
            },
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.read().decode(charset, errors="replace")

    def _fetch_json(self, url: str, *, user_agent: str | None = None) -> dict[str, Any]:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": user_agent
                or self._wfs_browser_ua,
            },
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

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

    def _catalog_items(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.catalogo_url)
        except urllib.error.URLError:
            return []
        return self._extract_sta_dataset(html, "CATSERV")

    def _is_urbanisme_tramite(self, item: dict[str, Any]) -> bool:
        family = str(item.get("nameFamily") or "")
        return family == "Urbanisme"

    def _is_licencia_tramite(self, item: dict[str, Any]) -> bool:
        if not self._is_urbanisme_tramite(item):
            return False
        name = str(item.get("name") or "")
        return bool(RE_LICENCIA.search(name))

    def _is_planning_tramite(self, item: dict[str, Any]) -> bool:
        if not self._is_urbanisme_tramite(item):
            return False
        name = str(item.get("name") or "").lower()
        if self._is_licencia_tramite(item):
            return False
        return any(tok in name for tok in PLANNING_TRAMITE_NAMES) or "projecte" in name

    def _sector_wfs_url(self) -> str:
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": self.wfs_type,
            "CQL_FILTER": f"CODI_INE='{self.ine_mun}'",
            "srsName": "EPSG:4326",
            "outputFormat": "application/json",
            "count": 200,
        }
        return f"{self.wfs_base}?{urllib.parse.urlencode(params)}"

    def _load_sector_features(self) -> list[dict[str, Any]]:
        if self._sector_features is not None:
            return self._sector_features
        try:
            data = self._fetch_json(self._sector_wfs_url())
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._sector_features = []
            return self._sector_features
        feats = data.get("features") or []
        self._sector_features = [f for f in feats if isinstance(f, dict)]
        return self._sector_features

    def _attach_geometry(self, rec: dict[str, Any], title: str) -> None:
        title_l = title.lower()
        best: dict[str, Any] | None = None
        best_score = 0
        for feat in self._load_sector_features():
            props = feat.get("properties") or {}
            nom = str(props.get("NOM_PLA") or "")
            if not nom:
                continue
            nom_l = nom.lower()
            score = 0
            if nom_l in title_l or title_l in nom_l:
                score += 10
            for token in re.findall(r"pau[\s\-]?\d+|sud[\s\-]?\d+|pp\d+", title_l):
                if token.replace(" ", "") in nom_l.replace(" ", ""):
                    score += 8
            if score > best_score:
                best_score = score
                best = feat
        if not best or best_score < 8:
            return
        geom = best.get("geometry")
        if not isinstance(geom, dict):
            return
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = self._sector_wfs_url()
        rec["geometry_crs"] = "EPSG:4326"
        cen = geometry_centroid(geom)
        if cen:
            rec["lat"], rec["lon"] = cen
            rec["coord_source"] = "portal_geometry_centroid"

    def _collect_wfs_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for feat in self._load_sector_features():
            props = feat.get("properties") or {}
            titulo = _clean_title(str(props.get("NOM_PLA") or ""))
            if not titulo:
                continue
            expedient = str(props.get("EXPEDIENT") or "")
            geom = feat.get("geometry")
            rec: dict[str, Any] = {
                "titulo": titulo,
                "fecha": _fecha_from_wfs(str(props.get("PUB_DOGC") or ""), expedient),
                "tipo": _proyecto_tipo(titulo),
                "url": f"{URBANISME_WEB}/planejament-i-llicencies/planejament-derivat",
                "expediente": expedient,
                "estado": str(props.get("ESTAT_PLANEJAMENT") or ""),
                "origen": "wfs_muc_sector",
            }
            if isinstance(geom, dict) and geom.get("type"):
                rec["geom_geojson"] = geom
                rec["geometry_source"] = "portal_wfs"
                rec["geometry_source_url"] = self._sector_wfs_url()
                rec["geometry_crs"] = "EPSG:4326"
                cen = geometry_centroid(geom)
                if cen:
                    rec["lat"], rec["lon"] = cen
                    rec["coord_source"] = "portal_geometry_centroid"
            rows.append(rec)
        return rows

    def _collect_eixdiari(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(self.eixdiari_url)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        for m in re.finditer(
            r'href="(/serveis/anuncis-oficials/edicte/\d+\.html)"[^>]*>([^<]+)</a>',
            html,
        ):
            link = m.group(1)
            titulo = _clean_title(m.group(2))
            if not titulo or RE_NOISE.search(titulo):
                continue
            if not RE_PROYECTO.search(titulo):
                continue
            tail = html[m.end() : m.end() + 700]
            fecha = _fecha_from_blob(tail) or ""
            rec = {
                "titulo": titulo,
                "fecha": fecha,
                "tipo": _proyecto_tipo(titulo),
                "url": f"{EIXDIARI_BASE}{link}",
                "origen": "eixdiari",
            }
            self._attach_geometry(rec, titulo)
            rows.append(rec)
        return rows

    def _collect_static_proyectos(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self.static_proyectos:
            titulo = _clean_title(item.get("titulo") or "")
            if not titulo:
                continue
            rows.append(
                {
                    "titulo": titulo,
                    "fecha": item.get("fecha") or "",
                    "tipo": item.get("tipo") or "planeamiento",
                    "url": item.get("url") or URBANISME_WEB,
                    "origen": "static_portal",
                }
            )
        return rows

    def _collect_planning_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._catalog_items():
            if not self._is_planning_tramite(item):
                continue
            name = _clean_title(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or name)
            rows.append(
                {
                    "titulo": name,
                    "fecha": "",
                    "tipo": "trámite planeamiento",
                    "url": self._tramite_url(dboid),
                    "origen": "catalogo_sta",
                }
            )
        return rows

    def _collect_licencias_tramites(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in self._catalog_items():
            if not self._is_licencia_tramite(item):
                continue
            name = _clean_title(str(item.get("name") or ""))
            dboid = str(item.get("dboid") or "")
            code = str(item.get("code") or dboid)
            rows.append(
                {
                    "id": _stable_id("lic", code),
                    "fecha_concesion": None,
                    "tipo": "trámite licencia",
                    "distrito": None,
                    "lat": None,
                    "lon": None,
                    "titulo": name,
                    "url": self._tramite_url(dboid),
                    "source": "ayuntamiento",
                    "nota": "Catálogo STA; sin histórico de concesiones publicado",
                    "tramite_code": code,
                }
            )
        return rows

    def _to_proyecto(self, rec: dict[str, Any]) -> dict[str, Any]:
        titulo = rec.get("titulo") or ""
        key = f"{rec.get('origen')}:{rec.get('url')}:{titulo}"
        out: dict[str, Any] = {
            "id": _stable_id("proy", key),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": rec.get("fecha") or "",
            "tipo": rec.get("tipo") or _proyecto_tipo(titulo),
            "url": rec.get("url") or self.catalogo_url,
            "source": "ayuntamiento",
        }
        for field in (
            "lat",
            "lon",
            "coord_source",
            "geom_geojson",
            "geometry_source",
            "geometry_source_url",
            "geometry_crs",
            "expediente",
            "estado",
            "origen",
        ):
            if rec.get(field) is not None:
                out[field] = rec[field]
        if record_geometry(out) and not out.get("coord_source"):
            cen = geometry_centroid(record_geometry(out) or {})
            if cen:
                out["lat"], out["lon"] = cen
                out["coord_source"] = "portal_geometry_centroid"
        return out

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
        rows = self._collect_licencias_tramites()
        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tramites_urbanisme": len(rows)}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
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
        seen: set[str] = set()
        rows: list[dict[str, Any]] = []

        def add(rec: dict[str, Any]) -> None:
            proy = self._to_proyecto(rec)
            if proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)

        for rec in self._collect_wfs_proyectos():
            add(rec)
        for rec in self._collect_eixdiari():
            add(rec)
        for rec in self._collect_static_proyectos():
            add(rec)
        for rec in self._collect_planning_tramites():
            add(rec)

        self._write_jsonl(out_jsonl, rows)
        wfs_n = len(self._load_sector_features())
        return {
            "rows": len(rows),
            "status": "ok",
            "wfs_sectors": wfs_n,
            "eixdiari": len(self._collect_eixdiari()),
            "static": len(self._collect_static_proyectos()),
            "tramites_planeamiento": len(self._collect_planning_tramites()),
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
