"""Completitud de scrapers municipales: cuánta info trae cada proyecto."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from municipio.geometry import has_area_geometry

MAX_SCAN_ROWS = 4000

# Pesos sobre 100: lo que diferencia un anuncio vacío de una ficha usable.
FIELD_WEIGHTS: dict[str, int] = {
    "titulo": 8,
    "fecha": 8,
    "url": 8,
    "coords": 16,
    "geometry": 18,
    "pdf": 14,
    "expediente": 10,
    "tipo": 6,
    "resumen": 8,
    "metrics": 2,
    "visor": 2,
}

STALE_AFTER_DAYS = 18
GEOM_STATUS_RE = re.compile(
    r"geometry_status:\s*`?(available|partial|unavailable)`?",
    re.I,
)


def _filled(val: Any) -> bool:
    if val is None or val is False:
        return False
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return True
    if isinstance(val, list):
        return any(_filled(x) for x in val[:30])
    if isinstance(val, dict):
        return bool(val)
    return bool(str(val).strip())


def _text(val: Any) -> str:
    return str(val or "").strip()


def row_flags(rec: dict[str, Any]) -> dict[str, bool]:
    titulo = _text(rec.get("titulo") or rec.get("denominacion"))
    resumen = _text(
        rec.get("resumen")
        or rec.get("resumen_contenido")
        or rec.get("descripcion")
        or rec.get("contenido_principal")
    )
    lat = rec.get("lat")
    lon = rec.get("lon") if rec.get("lon") is not None else rec.get("lng")
    docs = rec.get("pdf_urls") if isinstance(rec.get("pdf_urls"), list) else []
    doc_urls = rec.get("documentacion_urls") if isinstance(rec.get("documentacion_urls"), list) else []
    tramites = rec.get("tramitacion") if isinstance(rec.get("tramitacion"), list) else []
    nti_n = rec.get("nti_documentos_total")
    resumen_propio = bool(resumen) and resumen != titulo and len(resumen) >= 40
    return {
        "titulo": bool(titulo),
        "fecha": _filled(rec.get("fecha") or rec.get("fecha_aprob") or rec.get("fecha_concesion")),
        "url": _filled(rec.get("url") or rec.get("enlace") or rec.get("visor_url")),
        "coords": lat is not None and lon is not None,
        "geometry": has_area_geometry(rec),
        "pdf": _filled(rec.get("pdf_url")) or _filled(docs) or _filled(doc_urls),
        "expediente": _filled(
            rec.get("expte")
            or rec.get("expediente")
            or rec.get("expediente_grupo")
            or rec.get("exp_numero_original")
        ),
        "tipo": _filled(rec.get("tipo") or rec.get("tipo_figura") or rec.get("tipo_legal")),
        "resumen": resumen_propio,
        "metrics": _filled(rec.get("num_viviendas") or rec.get("num_viviendas_max") or rec.get("sup_total_m2")),
        "visor": _filled(rec.get("visor_fetched_at"))
        or _filled(rec.get("visor_ficha"))
        or (isinstance(nti_n, int) and nti_n > 0)
        or _filled(tramites),
    }


def score_from_fill(fill: dict[str, float]) -> int:
    total = 0.0
    weight_sum = sum(FIELD_WEIGHTS.values()) or 1
    for key, weight in FIELD_WEIGHTS.items():
        total += float(fill.get(key) or 0.0) * weight
    return int(round(100 * total / weight_sum))


def band_for(score: int, *, n: int) -> str:
    if n <= 0:
        return "sin_datos"
    if score >= 65:
        return "rico"
    if score >= 40:
        return "medio"
    if score >= 20:
        return "basico"
    return "fino"


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    counts = {k: 0 for k in FIELD_WEIGHTS}
    for rec in rows:
        flags = row_flags(rec)
        for key in counts:
            if flags.get(key):
                counts[key] += 1
    fill = {k: round((counts[k] / n) if n else 0.0, 4) for k in FIELD_WEIGHTS}
    score = score_from_fill(fill)
    return {
        "rows": n,
        "fill": fill,
        "with_coords": counts["coords"],
        "with_geometry": counts["geometry"],
        "with_pdf": counts["pdf"],
        "with_expediente": counts["expediente"],
        "score": score,
        "band": band_for(score, n=n),
    }


def scan_jsonl(path: Path, *, max_rows: int = MAX_SCAN_ROWS) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            if len(rows) >= max_rows:
                break
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    out = summarize_rows(rows)
    out["source"] = "jsonl"
    out["updated_at"] = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC).isoformat()
    return out


def geometry_status_from_research(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    m = GEOM_STATUS_RE.search(text)
    return m.group(1).lower() if m else None


def merge_fill(primary: dict[str, float] | None, fallback: dict[str, float] | None) -> dict[str, float]:
    out = {k: 0.0 for k in FIELD_WEIGHTS}
    for key in FIELD_WEIGHTS:
        a = (primary or {}).get(key)
        b = (fallback or {}).get(key)
        if isinstance(a, (int, float)):
            out[key] = float(a)
        elif isinstance(b, (int, float)):
            out[key] = float(b)
    return out


def freshness(
    *,
    last_ingest_at: str | None,
    last_output_at: str | None,
    status: str | None,
    has_adapter: bool,
    now: datetime | None = None,
    stale_after_days: int = STALE_AFTER_DAYS,
) -> tuple[str, float | None]:
    if status == "failed":
        return "error", None
    now = now or datetime.now(UTC)
    raw = last_ingest_at or last_output_at
    if not raw:
        return ("never" if has_adapter else "unknown"), None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return "unknown", None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    age = (now - ts).total_seconds() / 86400.0
    if age <= stale_after_days:
        return "fresh", round(age, 2)
    return "due", round(age, 2)
