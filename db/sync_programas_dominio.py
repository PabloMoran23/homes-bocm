#!/usr/bin/env python3
"""
Calcula programas SIGMA desde homes.proyecto, persiste sigma_programa* y rellena proyecto.programa_id.

Uso:
  python3 db/sync_programas_dominio.py [web/public/data/madrid-sigma-programas.json]
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

DB_DIR = Path(__file__).resolve().parent
POC_ROOT = DB_DIR.parent
sys.path.insert(0, str(DB_DIR))

from geo_utils import bbox_area_m2  # noqa: E402
from sigma_programa import (  # noqa: E402
    ExpedienteProgramaInput,
    anio_desde_referencia,
    compute_sigma_programas,
    programas_to_export,
)
from sync_madrid_public_to_supabase import pg_url  # noqa: E402

SCHEMA = "homes"
DEFAULT_OUT = POC_ROOT / "web/public/data/madrid-sigma-programas.json"


def log(msg: str) -> None:
    print(msg, flush=True)


def _visor_ficha(row: dict[str, Any]) -> dict[str, Any]:
    vf = row.get("visor_ficha")
    if isinstance(vf, dict):
        return vf
    if isinstance(vf, str):
        try:
            parsed = json.loads(vf)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _bbox_from_row(row: dict[str, Any]) -> tuple[float, float, float, float] | None:
    if row.get("bbox_min_lng") is None:
        return None
    return (
        float(row["bbox_min_lng"]),
        float(row["bbox_min_lat"]),
        float(row["bbox_max_lng"]),
        float(row["bbox_max_lat"]),
    )


def build_inputs_from_proyecto(cur) -> list[ExpedienteProgramaInput]:
    cur.execute(
        f"""
        SELECT
          expediente_grupo,
          exp_numero_original,
          denominacion,
          sigma_layer_kind,
          bbox_min_lng,
          bbox_min_lat,
          bbox_max_lng,
          bbox_max_lat,
          area_approx_m2,
          visor_ficha,
          sin_datos_visor,
          tipo_legal,
          tipo_obra,
          categoria_proyecto
        FROM {SCHEMA}.proyecto
        WHERE expediente_grupo IS NOT NULL
        """
    )
    inputs: list[ExpedienteProgramaInput] = []
    for row in cur.fetchall():
        grupo = str(row["expediente_grupo"])
        vf = _visor_ficha(row)
        bbox = _bbox_from_row(row)
        cl = row

        if row.get("sin_datos_visor") and not bbox and not row.get("categoria_proyecto"):
            continue

        area = row.get("area_approx_m2")
        if area is None and bbox:
            area = bbox_area_m2(bbox)

        exp = ExpedienteProgramaInput(
            expediente_grupo=grupo,
            exp_numero_original=str(
                vf.get("expedienteVisor") or row.get("exp_numero_original") or grupo
            ),
            denominacion=str(
                vf.get("denominacionVisor") or row.get("denominacion") or ""
            )
            or None,
            ambito_ordenacion=vf.get("ambitoOrdenacion"),
            distrito=vf.get("distrito"),
            bbox=bbox,
            area_m2=area,
            tipo_legal=row.get("tipo_legal"),
            tipo_obra=row.get("tipo_obra"),
            categoria_proyecto=row.get("categoria_proyecto"),
            sigma_layer_kind=str(row.get("sigma_layer_kind") or "") or None,
        )
        exp.anio = anio_desde_referencia(exp)
        if not exp.ambito_ordenacion and not exp.bbox and not row.get("categoria_proyecto"):
            continue
        inputs.append(exp)

    return inputs


def persist_programas_supabase(cur, programas) -> tuple[int, int]:
    cur.execute(f"DELETE FROM {SCHEMA}.sigma_programa_miembro")
    cur.execute(f"DELETE FROM {SCHEMA}.sigma_programa")

    now = datetime.now(UTC)
    prog_rows = []
    mem_rows = []
    for p in programas:
        prog_rows.append(
            (
                p.programa_id,
                p.titulo,
                p.ambito_ordenacion,
                p.distrito,
                p.anio_inicio,
                p.anio_fin,
                p.confianza,
                p.metodo_agrupacion,
                p.miembros_count,
                p.expediente_lider,
                now,
                1,
            )
        )
        for m in p.miembros:
            mem_rows.append(
                (m.expediente_grupo, p.programa_id, m.rol, m.orden_fase, m.overlap_ratio)
            )

    if prog_rows:
        execute_values(
            cur,
            f"""
            INSERT INTO {SCHEMA}.sigma_programa (
              programa_id, titulo, ambito_ordenacion, distrito,
              anio_inicio, anio_fin, confianza, metodo_agrupacion,
              miembros_count, expediente_lider, generated_at, version
            ) VALUES %s
            """,
            prog_rows,
            page_size=200,
        )

    if mem_rows:
        execute_values(
            cur,
            f"""
            INSERT INTO {SCHEMA}.sigma_programa_miembro (
              expediente_grupo, programa_id, rol, orden_fase, overlap_ratio
            ) VALUES %s
            """,
            mem_rows,
            page_size=500,
        )

    return len(prog_rows), len(mem_rows)


def update_proyecto_programa_ids(cur) -> int:
    cur.execute(
        f"""
        UPDATE {SCHEMA}.proyecto
        SET programa_id = NULL, updated_at = now()
        WHERE expediente_grupo IS NOT NULL
        """
    )
    cur.execute(
        f"""
        UPDATE {SCHEMA}.proyecto p
        SET programa_id = m.programa_id, updated_at = now()
        FROM {SCHEMA}.sigma_programa_miembro m
        WHERE p.expediente_grupo = m.expediente_grupo
        """
    )
    cur.execute(
        f"""
        SELECT COUNT(*)::int AS n FROM {SCHEMA}.proyecto WHERE programa_id IS NOT NULL
        """
    )
    row = cur.fetchone()
    return int(row["n"] if isinstance(row, dict) else row[0])


def sync_programas(cur, out_path: Path) -> dict[str, Any]:
    inputs = build_inputs_from_proyecto(cur)
    if not inputs:
        raise RuntimeError("sin expedientes SIGMA en proyecto para inferir programas")

    programas = compute_sigma_programas(inputs)
    export = programas_to_export(programas)
    n_prog, n_mem = persist_programas_supabase(cur, programas)
    n_linked = update_proyecto_programa_ids(cur)

    generated_at = datetime.now(UTC).isoformat()
    payload = {
        "generatedAt": generated_at,
        "source": "supabase-dominio",
        "count": len(programas),
        "expedientesInput": len(inputs),
        **export,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    return {
        "programas": n_prog,
        "miembros": n_mem,
        "proyecto_con_programa": n_linked,
        "out": str(out_path),
    }


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    with psycopg2.connect(pg_url()) as con:
        con.autocommit = False
        with con.cursor(cursor_factory=RealDictCursor) as cur:
            stats = sync_programas(cur, out_path)
            con.commit()
    log(
        f"OK: madrid-sigma-programas.json ({stats['programas']} programas, "
        f"{stats['miembros']} miembros, {stats['proyecto_con_programa']} proyectos con programa_id)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
