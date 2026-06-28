from __future__ import annotations

import json
import re
import unicodedata
import urllib.parse
import urllib.request
from functools import lru_cache
from typing import Any

WFS_BASE = "https://idem.comunidad.madrid/geoserver3/ows"
TYPE_NAME = "sitcm:VPLA_V_AMBITO"
USER_AGENT = "poc-bocm-municipio-geometry/1.0 (+https://www.comunidad.madrid)"

# Códigos de ámbito frecuentes en títulos de expedientes CM.
CODE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.I)
    for p in (
        r"\bAA[\.\-\s]*0?\d+\b",
        r"\bSR[\.\-\s]*\d+\b",
        r"\bSUZ[\.\-\s]*[IVX\d\.\-]+",
        r"\bUE[\.\-\s]*\d+\b",
        r"\bPAU[\.\-\s]*[\w\d\-]+",
        r"\bSector\s+[\w\d\-]+",
        r"\bUnidad\s+de\s+Ejecuci[oó]n\s+[\w\d\-]+",
    )
)


def _nfc_upper(s: str) -> str:
    return unicodedata.normalize("NFC", s.strip()).upper()


def _strip_accents(s: str) -> str:
    t = unicodedata.normalize("NFD", s)
    return t.encode("ascii", "ignore").decode("ascii")


def _sql_escape(s: str) -> str:
    return s.replace("'", "''")


def _http_get_json(url: str, timeout: float = 45.0) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


_wfs_cache: dict[str, list[dict[str, Any]]] = {}


def _wfs_query(cql: str, *, count: int = 25) -> list[dict[str, Any]]:
    cache_key = f"{count}:{cql}"
    if cache_key in _wfs_cache:
        return _wfs_cache[cache_key]

    params = urllib.parse.urlencode(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeName": TYPE_NAME,
            "outputFormat": "application/json",
            "srsName": "EPSG:4326",
            "count": str(count),
            "CQL_FILTER": cql,
        }
    )
    url = f"{WFS_BASE}?{params}"
    try:
        data = _http_get_json(url)
    except Exception:
        _wfs_cache[cache_key] = []
        return []

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        _wfs_cache[cache_key] = []
        return []
    feats = data.get("features") or []
    out = [f for f in feats if isinstance(f, dict)]
    _wfs_cache[cache_key] = out
    return out


@lru_cache(maxsize=256)
def resolve_municipio_wfs(nombre: str) -> str | None:
    """Resuelve DS_MUNICIPIO en la capa SITCM a partir del nombre del manifest."""
    candidates = [
        _nfc_upper(nombre),
        _nfc_upper(_strip_accents(nombre)),
    ]
    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        cql = f"DS_MUNICIPIO='{_sql_escape(cand)}'"
        if _wfs_query(cql, count=1):
            return cand

    # Búsqueda por tokens significativos (p. ej. «POZUELO DE ALARCÓN»).
    tokens = [t for t in re.split(r"[\s\-]+", _strip_accents(nombre)) if len(t) >= 4]
    if tokens:
        pattern = "%" + "%".join(_sql_escape(t) for t in tokens[:3]) + "%"
        cql = f"DS_MUNICIPIO ILIKE '{pattern}'"
        feats = _wfs_query(cql, count=5)
        if feats:
            names = sorted(
                {str(f.get("properties", {}).get("DS_MUNICIPIO") or "") for f in feats},
                key=len,
            )
            for name in names:
                if name:
                    return name
    return None


def sitcm_municipio_available(nombre: str) -> bool:
    return resolve_municipio_wfs(nombre) is not None


def extract_ambito_codes(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for pat in CODE_PATTERNS:
        for m in pat.finditer(text or ""):
            raw = re.sub(r"\s+", " ", m.group(0).strip())
            key = raw.lower()
            if key not in seen:
                seen.add(key)
                found.append(raw)
    return found


def _sector_ilike_parts(sector_raw: str) -> list[str]:
    s = sector_raw.strip().lower()
    for marker in (" del pgou", " pgou", " del municipio", " (", "\n"):
        if marker in s:
            s = s.split(marker, 1)[0]
            break
    s = s.strip(" ,.;:|/")
    parts = [p for p in re.split(r"[\s,;/|]+", s) if p]
    out: list[str] = []
    for p in parts:
        for sub in re.split(r"[-–—]+", p):
            sub = sub.strip()
            if sub and len(sub) > 1:
                out.append(sub)
    seen: set[str] = set()
    uniq: list[str] = []
    for p in out:
        k = p.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq[:12]


def _build_ilike_pattern(parts: list[str]) -> str:
    if not parts:
        return "%"
    return "%" + "%".join(_sql_escape(p) for p in parts) + "%"


def _merge_geometries(features: list[dict[str, Any]]) -> dict[str, Any] | None:
    polys: list[Any] = []
    for f in features:
        g = f.get("geometry")
        if not isinstance(g, dict):
            continue
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


def _score_feature(title: str, feat: dict[str, Any]) -> float:
    props = feat.get("properties") or {}
    name = str(props.get("DS_NOMB_AMB") or "")
    if not name:
        return -1.0
    title_fold = title.lower().replace("–", "-")
    name_fold = name.lower().replace("–", "-")
    score = 0.0
    if name_fold in title_fold or title_fold in name_fold:
        score += 50.0
    for code in extract_ambito_codes(title):
        norm = re.sub(r"[\.\s]+", "", code.lower())
        if norm and norm in re.sub(r"[\.\s]+", "", name_fold):
            score += 30.0
    for part in _sector_ilike_parts(title):
        if part.lower() in name_fold:
            score += 5.0
    return score


def _sector_query_tokens(code: str) -> list[str]:
    tokens = [code]
    compact = re.sub(r"[\.\s]+", "", code)
    if compact:
        tokens.append(compact)
    m = re.search(r"sector\s+([\w\d\-]+)", code, re.I)
    if m:
        sector = m.group(1)
        tokens.append(sector)
        tokens.append(sector.replace("-", ""))
        sm = re.match(r"(\d+)\s*[-–]?\s*([A-Z])", sector, re.I)
        if sm:
            tokens.append(f"S-{sm.group(1)}{sm.group(2).upper()}")
            tokens.append(f"{sm.group(1)}{sm.group(2).upper()}")
    return list(dict.fromkeys(t for t in tokens if len(t) >= 2))


def query_ambito_features(municipio_wfs: str, title: str) -> list[dict[str, Any]]:
    """Consulta SITCM por códigos explícitos y, si falla, por tokens del título."""
    muni = _sql_escape(municipio_wfs)
    codes = extract_ambito_codes(title)
    queries: list[str] = []

    for code in codes:
        for token in _sector_query_tokens(code):
            if len(token) >= 2:
                queries.append(
                    f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '%{_sql_escape(token)}%'"
                )

    parts = _sector_ilike_parts(title)
    has_hint = bool(codes) or bool(
        re.search(r"\b(sector|ámbito|ambito|unidad de ejecuci|aa[\.\-\s]|sr[\.\-\s]|suz|ue[\.\-\s]|pau)\b", title, re.I)
    )
    if has_hint and len(parts) >= 3:
        pattern = _build_ilike_pattern(parts[:4])
        queries.append(f"DS_MUNICIPIO='{muni}' AND DS_NOMB_AMB ILIKE '{pattern}'")

    if not queries:
        return []

    seen_urls: set[str] = set()
    all_feats: list[dict[str, Any]] = []
    for cql in queries[:5]:
        if cql in seen_urls:
            continue
        seen_urls.add(cql)
        all_feats.extend(_wfs_query(cql, count=15))

    if not all_feats:
        return []

    by_name: dict[str, list[dict[str, Any]]] = {}
    for f in all_feats:
        name = str((f.get("properties") or {}).get("DS_NOMB_AMB") or "")
        if name:
            by_name.setdefault(name, []).append(f)

    best_name: str | None = None
    best_score = -1.0
    for name, feats in by_name.items():
        score = max(_score_feature(title, f) for f in feats)
        if score > best_score:
            best_score = score
            best_name = name

    if best_name is None or best_score < 5.0:
        return []
    return by_name[best_name]


def resolve_ambito_geometry(municipio_wfs: str, title: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Devuelve (geom_geojson, meta) o (None, meta con motivo)."""
    meta: dict[str, Any] = {"source": "sitcm_vpla_ambito", "municipio_wfs": municipio_wfs}
    feats = query_ambito_features(municipio_wfs, title)
    if not feats:
        meta["reason"] = "no_match"
        return None, meta

    geom = _merge_geometries(feats)
    if not geom:
        meta["reason"] = "no_polygon"
        return None, meta

    name = str((feats[0].get("properties") or {}).get("DS_NOMB_AMB") or "")
    meta["ambito_name"] = name
    meta["feature_count"] = len(feats)
    return geom, meta
