"""Ingesta de anuncios de tablón en homes.anuncio.

Lee ``output/municipios/<slug>/anuncios.jsonl`` (escrito por
``municipio.anuncios_runner``) y hace upsert. Independiente de la ingesta de
proyectos y licencias: no toca ``last_ingest_at``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from psycopg2.extras import Json, execute_values

from ingest import DB_DIR, SCHEMA, _owned_conn, available

COLUMNS = (
    "id", "municipio_slug", "fuente", "sede", "documento_id", "url", "titulo", "descripcion",
    "expediente", "procedimiento", "categoria", "fecha_publicacion", "fecha_fin",
    "clase", "subclase", "clase_regla", "clase_version", "raw",
)
# Campos que vienen del tablón; el resto del registro va a ``raw``.
_FIELDS = set(COLUMNS) - {"raw"}


def ensure_schema(cur) -> None:
    cur.execute((DB_DIR / "schema_anuncio.sql").read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _row(rec: dict[str, Any], slug: str) -> tuple:
    rec = {**rec, "municipio_slug": rec.get("municipio_slug") or slug}
    rec["titulo"] = (str(rec.get("titulo") or "").strip() or "(sin título)")[:1000]
    raw = {k: v for k, v in rec.items() if k not in _FIELDS}
    return tuple(Json(raw) if col == "raw" else rec.get(col) for col in COLUMNS)


def save_anuncios(slug: str, rows: list[dict[str, Any]], *, complete: bool, fuente: str = "gestiona",
                  conn=None) -> dict[str, int]:
    """Upsert de una lectura del tablón.

    ``complete`` indica que se leyó el tablón entero (sin truncar). Solo
    entonces se marcan como retirados los anuncios que ya no aparecen. No se
    pisa ``visible_radar`` ni una clase puesta a mano (``clase_regla='manual'``).
    """
    values = [_row(r, slug) for r in rows if r.get("id")]
    with _owned_conn(conn) as c, c.cursor() as cur:
        ensure_schema(cur)
        inserted = 0
        if values:
            cols = ", ".join(COLUMNS)
            updates = ", ".join(
                f"{col} = EXCLUDED.{col}" for col in COLUMNS
                if col not in ("id", "clase", "subclase", "clase_regla", "clase_version")
            )
            result = execute_values(
                cur,
                f"""INSERT INTO {SCHEMA}.anuncio ({cols}) VALUES %s
                    ON CONFLICT (id) DO UPDATE SET {updates},
                      clase = CASE WHEN {SCHEMA}.anuncio.clase_regla = 'manual' THEN {SCHEMA}.anuncio.clase ELSE EXCLUDED.clase END,
                      subclase = CASE WHEN {SCHEMA}.anuncio.clase_regla = 'manual' THEN {SCHEMA}.anuncio.subclase ELSE EXCLUDED.subclase END,
                      clase_version = CASE WHEN {SCHEMA}.anuncio.clase_regla = 'manual' THEN {SCHEMA}.anuncio.clase_version ELSE EXCLUDED.clase_version END,
                      clase_regla = CASE WHEN {SCHEMA}.anuncio.clase_regla = 'manual' THEN 'manual' ELSE EXCLUDED.clase_regla END,
                      last_seen_at = now(),
                      retirado_at = NULL,
                      updated_at = now()
                    RETURNING (xmax = 0)""",
                values,
                fetch=True,
            )
            inserted = sum(1 for (is_new,) in result if is_new)
        retired = 0
        if complete:
            cur.execute(
                f"""UPDATE {SCHEMA}.anuncio SET retirado_at = now(), updated_at = now()
                    WHERE municipio_slug = %s AND fuente = %s AND retirado_at IS NULL
                      AND NOT (id = ANY(%s))""",
                (slug, fuente, [v[0] for v in values]),
            )
            retired = cur.rowcount
    return {"anuncios": len(values), "nuevos": inserted, "retirados": retired}


def sync_municipio_anuncios(manifest, *, dry_run: bool = False, conn=None) -> dict[str, Any]:
    out_dir = manifest.output_dir
    rows = _read_jsonl(out_dir / "anuncios.jsonl")
    state_path = out_dir / "anuncios_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
    stats: dict[str, Any] = {"anuncios": len(rows)}
    if not rows and not state.get("complete"):
        return {**stats, "status": "skipped", "reason": "sin anuncios"}
    if dry_run:
        return {**stats, "status": "dry_run"}
    if not available():
        return {**stats, "status": "skipped", "reason": "sin SUPABASE_DB_URL"}
    stats.update(save_anuncios(manifest.slug, rows, complete=bool(state.get("complete")), conn=conn))
    stats["status"] = "ok"
    return stats
