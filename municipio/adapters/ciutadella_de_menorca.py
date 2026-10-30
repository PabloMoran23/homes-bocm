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

WEB_BASE = "https://www.ajciutadella.org"
CARPETA_BASE = "https://www.carpetaciutadana.org/ciutadella"
MUNICIPIO = "Ciutadella de Menorca"
ID_PREFIX = "ciutadella-de-menorca"

EDICTES_URBAN = f"{WEB_BASE}/Tauler/edictesX.aspx?TIPO=02"
EDICTES_URBAN_HIST = f"{WEB_BASE}/Tauler/edictesX.aspx?TIPO=02&HISTORIC=1"
TRAMITS_URBAN = f"{WEB_BASE}/GesServeis/Tramits.aspx?IDSERVEI=22&TITULO=Urbanisme+i+Activitats"
PGOU_DOC = f"{WEB_BASE}/Contingut.aspx?IdPub=2318"
PGOU_EXPOSICIO = f"{WEB_BASE}/Contingut.aspx?IdPub=38043"

WFS_DEFAULT_URL = "https://ide.cime.es/geoserver/urbanisme/wfs"
WFS_DEFAULT_TYPE = "urbanisme:or015pod_gestio_zofs"

RE_GRID_ROW = re.compile(r"dxgvDataRow[^>]*>(.*?)</tr>", re.S | re.I)
RE_EDICT_LINK = re.compile(
    r'href="(/Tauler/ObrirEdicteExp\.aspx\?Ig=[^"]+)"[^>]*>(.*?)</a>',
    re.S | re.I,
)
RE_GESTION_LINK = re.compile(
    r'href="(/GesServeis/Gestion\.aspx\?IDGESTION=\d+)"[^>]*>([^<]+)',
    re.I,
)
RE_LICENCIA = re.compile(
    r"(?i)(llic[eè]ncia|licen|comunicaci[oó] pr[eè]via|declaraci[oó] responsable|"
    r"primera ocupaci[oó]|obra[s]?|clavegueram|urban[ií]stic|activitat|legalitz)",
)
RE_PROYECTO = re.compile(
    r"(?i)(urban|planej|pgou|pod|projecte|urbanitz|expedient|edicte|aprovaci[oó]|"
    r"informaci[oó] p[uú]blica|exposici[oó] p[uú]blica|consulta p[uú]blica|"
    r"conveni|modificaci[oó]|reparcel|unitat d.actuaci|\bua[\s-]?\d|clavegueram|"
    r"ordenan[cç]a|normativa urban|gesti[oó])",
)
RE_EDICT_NOISE = re.compile(
    r"(?i)(cobran[cç]a|\bibi\b|\biae\b|padr[oó] d.aigua|sequera|calendari fiscal|"
    r"m[oò]dul de preus|compte general|preu p[uú]blic n[uú]m\.|ban d.alcal)",
)
RE_FECHA_DMY = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")
RE_FECHA_DMY_DASH = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})")
RE_UA_CODE = re.compile(r"(?i)\b(ua[\s-]?\d+[a-z]?)\b")
RE_YEAR = re.compile(r"\b((?:19|20)\d{2})\b")

PROYECTO_SEEDS: list[dict[str, str]] = [
    {"titulo": "Documentació PGOU — consulta normativa i cartografia", "url": PGOU_DOC, "tipo": "PGOU"},
    {"titulo": "Documentació PGOU (exposició pública) — planimetria PDF", "url": PGOU_EXPOSICIO, "tipo": "información pública"},
    {"titulo": "Tauler d'edictes — urbanisme (TIPO=02)", "url": EDICTES_URBAN, "tipo": "tablón edictos"},
]


def _stable_id(kind: str, key: str) -> str:
    h = hashlib.sha256(key.encode("utf-8")).hexdigest()[:14]
    return f"{ID_PREFIX}-{kind}-{h}"


def _strip_html(text: str) -> str:
    t = re.sub(r"<[^>]+>", " ", text or "")
    return unescape(re.sub(r"\s+", " ", t)).strip()


def _parse_fecha_dmy(text: str) -> str | None:
    for pat in (RE_FECHA_DMY, RE_FECHA_DMY_DASH):
        m = pat.search(text or "")
        if m:
            try:
                return datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).strftime("%Y-%m-%d")
            except ValueError:
                pass
    years = [int(y.group(1)) for y in RE_YEAR.finditer(text or "") if 1980 <= int(y.group(1)) <= 2035]
    if years:
        return f"{max(years)}-01-01"
    return None


def _proyecto_tipo(blob: str) -> str:
    n = blob.lower()
    if "pgou" in n or "pod" in n:
        return "PGOU/POD"
    if "urbanitz" in n or "ua-" in n or re.search(r"\bua\s*\d", n):
        return "proyecto de urbanización"
    if "clavegueram" in n or "sanejament" in n:
        return "obra infraestructura"
    if "consulta p" in n and "blica" in n:
        return "consulta pública"
    if "aprovaci" in n and "inicial" in n:
        return "aprobación inicial"
    if "aprovaci" in n and "definitiva" in n:
        return "aprobación definitiva"
    if "exposici" in n and "p" in n and "blica" in n:
        return "exposición pública"
    if "conveni" in n:
        return "convenio"
    if "ordenan" in n:
        return "ordenanza urbanística"
    if "edicte" in n:
        return "edicto urbanístico"
    return "urbanismo"


def _licencia_tipo(text: str) -> str:
    n = (text or "").lower()
    if "comunicaci" in n and "pr" in n:
        return "comunicación previa"
    if "declaraci" in n and "respons" in n:
        return "declaración responsable"
    if "primera ocupaci" in n:
        return "licencia de primera ocupación"
    if "certificat" in n:
        return "certificado urbanístico"
    if "activitat" in n:
        return "licencia de actividad"
    if "clavegueram" in n or "obra" in n:
        return "licencia / obra"
    return "trámite urbanístico"


class CiutadellaDeMenorcaAyuntamientoAdapter(AyuntamientoAdapter):
    """Web ajciutadella.org (DevExpress tauler) + GesServeis + WFS IDE CIME Ciutadella."""

    def __init__(self, slug: str, config: dict[str, Any] | None = None, base_url: str = ""):
        super().__init__(slug, config, base_url or WEB_BASE)
        self.delay_s = float(self.config.get("request_delay_s", 0.35))
        self.web_base = str(self.config.get("web_base") or WEB_BASE).rstrip("/")
        self.carpeta_base = str(self.config.get("carpeta_base") or CARPETA_BASE).rstrip("/")
        geom = self.config.get("geometry") or {}
        self.wfs_url = str(geom.get("wfs_url") or WFS_DEFAULT_URL)
        self.wfs_type = str(geom.get("type_name") or WFS_DEFAULT_TYPE)
        self.wfs_max = int(geom.get("max_features") or 250)
        self._wfs_cache: list[dict[str, Any]] | None = None

    def _fetch(self, url: str, *, timeout: int = 90) -> str:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def _fetch_json(self, url: str, *, timeout: int = 120) -> Any:
        time.sleep(self.delay_s)
        req = urllib.request.Request(
            url,
            headers={"User-Agent": self.config.get("user_agent", f"poc-bocm-{ID_PREFIX}/1.0")},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def _abs_url(self, href: str) -> str:
        return urllib.parse.urljoin(self.web_base + "/", unescape(href))

    def _load_jsonl(self, path: Path) -> list[dict[str, Any]]:
        if not path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                rows.append(json.loads(line))
        return rows

    def _write_jsonl(self, path: Path, rows: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def _parse_edictes(self, html: str, *, origen: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row_html in RE_GRID_ROW.findall(html):
            m = RE_EDICT_LINK.search(row_html)
            if not m:
                continue
            href, title_html = m.group(1), m.group(2)
            titulo = _strip_html(title_html)[:500]
            url = self._abs_url(href)
            ig = re.search(r"Ig=([^&\"]+)", href, re.I)
            guid = ig.group(1) if ig else href
            dates = RE_FECHA_DMY.findall(row_html)
            if dates:
                d, m, y = dates[0]
                fecha = _parse_fecha_dmy(f"{d}/{m}/{y}")
            else:
                fecha = None
            out.append(
                {
                    "titulo": titulo,
                    "url": url,
                    "fecha": fecha,
                    "guid": guid,
                    "blob": titulo,
                    "origen": origen,
                }
            )
        return out

    def _collect_edictes(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for page_url, origen in (
            (EDICTES_URBAN, "tauler_urbanisme"),
            (EDICTES_URBAN_HIST, "tauler_urbanisme_historic"),
        ):
            try:
                html = self._fetch(page_url)
            except urllib.error.URLError:
                continue
            for row in self._parse_edictes(html, origen=origen):
                key = row.get("guid") or row.get("url") or ""
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        return rows

    def _collect_tramites(self) -> list[dict[str, Any]]:
        try:
            html = self._fetch(TRAMITS_URBAN)
        except urllib.error.URLError:
            return []
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()
        for href, title in RE_GESTION_LINK.findall(html):
            url = self._abs_url(href)
            if url in seen:
                continue
            seen.add(url)
            titulo = _strip_html(title)[:500]
            rows.append({"titulo": titulo, "url": url, "blob": titulo})
        return rows

    def _wfs_features(self) -> list[dict[str, Any]]:
        if self._wfs_cache is not None:
            return self._wfs_cache
        params = {
            "service": "WFS",
            "version": "1.1.0",
            "request": "GetFeature",
            "typeName": self.wfs_type,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "maxFeatures": str(self.wfs_max),
        }
        url = f"{self.wfs_url}?{urllib.parse.urlencode(params)}"
        try:
            data = self._fetch_json(url)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
            self._wfs_cache = []
            return self._wfs_cache
        feats = data.get("features") or []
        parsed: list[dict[str, Any]] = []
        for feat in feats:
            if not isinstance(feat, dict):
                continue
            props = feat.get("properties") or {}
            geom = feat.get("geometry")
            parsed.append(
                {
                    "nomfigura": str(props.get("nomfigura") or ""),
                    "dsfigura": str(props.get("dsfigura") or ""),
                    "idfigura": str(props.get("idfigura") or ""),
                    "geometry": geom,
                }
            )
        self._wfs_cache = parsed
        return parsed

    def _title_tokens(self, title: str) -> list[str]:
        tokens: list[str] = []
        t = title.lower()
        for m in RE_UA_CODE.finditer(title):
            tokens.append(re.sub(r"\s+", "-", m.group(1).lower()))
        for word in re.findall(r"[a-zà-ÿ]{5,}", t):
            if word not in ("edicte", "projecte", "aprovacio", "aprovació", "inicial", "definitiva", "ciutadella"):
                tokens.append(word)
        return tokens

    def _attach_geometry(self, rec: dict[str, Any], title: str) -> None:
        title_l = title.lower()
        best: dict[str, Any] | None = None
        best_score = 0
        for feat in self._wfs_features():
            nom = feat.get("nomfigura", "").lower()
            ds = feat.get("dsfigura", "").lower()
            score = 0
            for tok in self._title_tokens(title):
                if len(tok) < 4:
                    continue
                if tok in nom or tok in ds or tok in title_l and tok in nom:
                    score += 3
                if tok.replace("-", "") in nom.replace("-", "").replace(" ", ""):
                    score += 2
            if "ua-" in title_l or "ua " in title_l:
                m = RE_UA_CODE.search(title)
                if m and m.group(1).lower().replace(" ", "") in nom.replace(" ", ""):
                    score += 5
            if score > best_score and feat.get("geometry"):
                best_score = score
                best = feat
        if not best or best_score < 3:
            return
        geom = best.get("geometry")
        if not isinstance(geom, dict):
            return
        qurl = (
            f"{self.wfs_url}?service=WFS&version=1.1.0&request=GetFeature&typeName={self.wfs_type}"
            f"&outputFormat=application/json&srsName=EPSG:4326&maxFeatures=1"
            f"&CQL_FILTER=nomfigura='{best['nomfigura'].replace(chr(39), '')}'"
        )
        rec["geom_geojson"] = geom
        rec["geometry_source"] = "portal_wfs"
        rec["geometry_source_url"] = qurl
        rec["coord_source"] = "portal_geometry_centroid"
        cen = geometry_centroid(geom)
        if cen:
            rec["lat"], rec["lon"] = cen

    def _edict_to_proyecto(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or row.get("titulo") or ""
        if RE_EDICT_NOISE.search(blob):
            return None
        if not RE_PROYECTO.search(blob):
            return None
        titulo = row.get("titulo") or blob[:500]
        rec: dict[str, Any] = {
            "id": _stable_id("proy", row.get("guid") or row.get("url") or titulo),
            "municipio": MUNICIPIO,
            "titulo": titulo,
            "fecha": row.get("fecha"),
            "tipo": _proyecto_tipo(blob),
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen", "tauler"),
        }
        self._attach_geometry(rec, titulo)
        return rec

    def _edict_to_licencia(self, row: dict[str, Any]) -> dict[str, Any] | None:
        blob = row.get("blob") or ""
        if RE_EDICT_NOISE.search(blob):
            return None
        if not RE_LICENCIA.search(blob):
            return None
        titulo = row.get("titulo") or blob[:500]
        rec: dict[str, Any] = {
            "id": _stable_id("lic", row.get("guid") or titulo),
            "fecha_concesion": row.get("fecha"),
            "tipo": _licencia_tipo(titulo),
            "distrito": None,
            "lat": None,
            "lon": None,
            "titulo": titulo[:500],
            "url": row.get("url"),
            "source": "ayuntamiento",
            "origen": row.get("origen", "tauler"),
        }
        self._attach_geometry(rec, titulo)
        if record_geometry(rec):
            cen = geometry_centroid(record_geometry(rec) or {})
            if cen:
                rec["lat"], rec["lon"] = cen
        return rec

    def backfill_licencias(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for item in self._collect_tramites():
            titulo = item["titulo"]
            rec = {
                "id": _stable_id("lic", item["url"]),
                "fecha_concesion": None,
                "tipo": _licencia_tipo(titulo),
                "distrito": None,
                "lat": None,
                "lon": None,
                "titulo": titulo,
                "url": item["url"],
                "source": "ayuntamiento",
                "nota": "Trámite informativo GesServeis (carpeta ciutadana)",
                "origen": "ges_tramite",
            }
            if rec["id"] not in seen:
                seen.add(rec["id"])
                rows.append(rec)

        for ed in self._collect_edictes():
            lic = self._edict_to_licencia(ed)
            if lic and lic["id"] not in seen:
                seen.add(lic["id"])
                rows.append(lic)

        self._write_jsonl(out_jsonl, rows)
        return {"rows": len(rows), "status": "ok", "tramites": sum(1 for r in rows if r.get("origen") == "ges_tramite")}

    def update_licencias(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_licencias(out_jsonl)
        after = stats.get("rows", len(self._load_jsonl(out_jsonl)))
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
        return {**stats, "added": max(0, after - before)}

    def backfill_proyectos(self, out_jsonl: Path) -> dict[str, Any]:
        rows: list[dict[str, Any]] = []
        seen: set[str] = set()

        for seed in PROYECTO_SEEDS:
            rec = {
                "id": _stable_id("proy", seed["url"]),
                "municipio": MUNICIPIO,
                "titulo": seed["titulo"],
                "fecha": None,
                "tipo": seed["tipo"],
                "url": seed["url"],
                "source": "ayuntamiento",
                "origen": "web_seed",
            }
            seen.add(rec["id"])
            rows.append(rec)

        for ed in self._collect_edictes():
            proy = self._edict_to_proyecto(ed)
            if proy and proy["id"] not in seen:
                seen.add(proy["id"])
                rows.append(proy)

        self._write_jsonl(out_jsonl, rows)
        with_geom = sum(1 for r in rows if record_geometry(r))
        return {
            "rows": len(rows),
            "status": "ok",
            "with_geometry": with_geom,
            "edictos": sum(1 for r in rows if str(r.get("origen", "")).startswith("tauler")),
        }

    def update_proyectos(self, out_jsonl: Path, state_path: Path) -> dict[str, Any]:
        before = len(self._load_jsonl(out_jsonl))
        stats = self.backfill_proyectos(out_jsonl)
        after = stats.get("rows", len(self._load_jsonl(out_jsonl)))
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
        return {**stats, "added": max(0, after - before)}
