#!/usr/bin/env python3
"""Calcula programas SIGMA, persiste en SQLite y exporta madrid-sigma-programas.json."""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR))

from geo_utils import bbox_area_m2, geom_bbox  # noqa: E402
from migrate_sqlite import expediente_grupo_from_num  # noqa: E402
from sigma_programa import (  # noqa: E402
    ExpedienteProgramaInput,
    anio_desde_referencia,
    compute_sigma_programas,
    programas_to_export,
)

DEFAULT_DB = DB_DIR / "poc_local.sqlite"
VISOR_CANDIDATES = [
    POC_ROOT / "output/madrid_viso_expedientes.json",
    POC_ROOT / "web/public/data/madrid-sigma-visor-slim.json",
]
CLASIFICACION = POC_ROOT / "web/public/data/madrid-sigma-clasificacion.json"
AMBITOS_GEO = POC_ROOT / "web/public/data/madrid-sigma-ambitos.geojson"
DEFAULT_OUT = POC_ROOT / "web/public/data/madrid-sigma-programas.json"


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _visor_by_grupo() -> dict[str, dict]:
    for candidate in VISOR_CANDIDATES:
        raw = _load_json(candidate)
        if raw:
            return {
                str(k): v
                for k, v in (raw.get("byGrupoExpediente") or {}).items()
                if isinstance(v, dict)
            }
    return {}


def _clasificacion_by_grupo() -> dict[str, dict]:
    raw = _load_json(CLASIFICACION)
    if not raw:
        return {}
    return {str(k): v for k, v in (raw.get("byExpediente") or {}).items() if isinstance(v, dict)}


def _geom_from_sqlite(con: sqlite3.Connection) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in con.execute(
        """
        SELECT g.expediente_grupo, g.geom_geojson, g.area_approx_m2,
               c.exp_numero_original, c.denominacion, c.sigma_layer_kind
        FROM sigma_ambito_geom g
        JOIN sigma_catalog_expediente c ON c.expediente_grupo = g.expediente_grupo
        """
    ):
        try:
            geom = json.loads(row["geom_geojson"])
        except (TypeError, json.JSONDecodeError):
            continue
        bbox = geom_bbox(geom)
        if not bbox:
            continue
        out[row["expediente_grupo"]] = {
            "bbox": bbox,
            "area_m2": row["area_approx_m2"],
            "exp_numero_original": row["exp_numero_original"],
            "denominacion": row["denominacion"],
            "sigma_layer_kind": row["sigma_layer_kind"],
        }
    return out


def _geom_from_geojson() -> dict[str, dict]:
    raw = _load_json(AMBITOS_GEO)
    if not raw:
        return {}
    out: dict[str, dict] = {}
    for feat in raw.get("features") or []:
        if not isinstance(feat, dict):
            continue
        props = feat.get("properties") or {}
        geom = feat.get("geometry")
        if not isinstance(geom, dict):
            continue
        num = props.get("EXP_TX_NUMERO")
        if not num:
            continue
        grupo = expediente_grupo_from_num(str(num))
        if not grupo:
            continue
        bbox = geom_bbox(geom)
        if not bbox:
            continue
        out[grupo] = {
            "bbox": bbox,
            "area_m2": None,
            "exp_numero_original": str(num),
            "denominacion": props.get("EXP_TX_DENOM"),
            "sigma_layer_kind": props.get("sigma_layer_kind"),
        }
    return out


def build_inputs(con: sqlite3.Connection | None) -> list[ExpedienteProgramaInput]:
    visor = _visor_by_grupo()
    clasif = _clasificacion_by_grupo()
    geom_ctx = _geom_from_sqlite(con) if con else {}
    if not geom_ctx:
        geom_ctx = _geom_from_geojson()

    grupos: set[str] = set(visor.keys()) | set(clasif.keys()) | set(geom_ctx.keys())
    inputs: list[ExpedienteProgramaInput] = []

    for grupo in grupos:
        vrec = visor.get(grupo) or {}
        vf = vrec.get("visorFicha") if isinstance(vrec.get("visorFicha"), dict) else {}
        cl = clasif.get(grupo) or {}
        geo = geom_ctx.get(grupo) or {}
        if vrec.get("sinDatosVisor") and not geo and not cl:
            continue

        exp = ExpedienteProgramaInput(
            expediente_grupo=grupo,
            exp_numero_original=str(
                vf.get("expedienteVisor") or geo.get("exp_numero_original") or grupo
            ),
            denominacion=str(
                vf.get("denominacionVisor") or geo.get("denominacion") or cl.get("denominacion") or ""
            )
            or None,
            ambito_ordenacion=vf.get("ambitoOrdenacion"),
            distrito=vf.get("distrito"),
            bbox=geo.get("bbox"),
            area_m2=geo.get("area_m2") or (bbox_area_m2(geo["bbox"]) if geo.get("bbox") else None),
            tipo_legal=cl.get("tipoLegal"),
            tipo_obra=cl.get("tipoObra"),
            categoria_proyecto=cl.get("categoriaProyecto"),
            sigma_layer_kind=str(
                vrec.get("sigmaLayerKind") or geo.get("sigma_layer_kind") or cl.get("source") or ""
            )
            or None,
        )
        exp.anio = anio_desde_referencia(exp)
        if not exp.ambito_ordenacion and not exp.bbox and not cl:
            continue
        inputs.append(exp)

    return inputs


def persist_sqlite(con: sqlite3.Connection, programas) -> tuple[int, int]:
    con.execute("DELETE FROM sigma_programa_miembro")
    con.execute("DELETE FROM sigma_programa")
    now = datetime.now(UTC).isoformat()
    n_prog = 0
    n_mem = 0
    for p in programas:
        con.execute(
            """
            INSERT INTO sigma_programa (
              programa_id, titulo, ambito_ordenacion, distrito,
              anio_inicio, anio_fin, confianza, metodo_agrupacion,
              miembros_count, expediente_lider, generated_at, version
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)
            """,
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
            ),
        )
        n_prog += 1
        for m in p.miembros:
            con.execute(
                """
                INSERT INTO sigma_programa_miembro (
                  expediente_grupo, programa_id, rol, orden_fase, overlap_ratio
                ) VALUES (?,?,?,?,?)
                """,
                (m.expediente_grupo, p.programa_id, m.rol, m.orden_fase, m.overlap_ratio),
            )
            n_mem += 1
    con.commit()
    return n_prog, n_mem


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    db_path = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_DB

    con: sqlite3.Connection | None = None
    if db_path.is_file():
        con = sqlite3.connect(db_path)
        con.row_factory = sqlite3.Row

    inputs = build_inputs(con)
    if not inputs:
        print("no inputs for sigma programas", file=sys.stderr)
        return 1

    programas = compute_sigma_programas(inputs)
    export = programas_to_export(programas)
    payload = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "count": len(programas),
        "expedientesInput": len(inputs),
        **export,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    if con:
        try:
            n_prog, n_mem = persist_sqlite(con, programas)
            print(f"OK: sqlite {n_prog} programas, {n_mem} miembros")
        except sqlite3.OperationalError as exc:
            print(f"aviso: no se persistió en sqlite ({exc})", file=sys.stderr)
        con.close()

    print(f"OK: {out_path} ({len(programas)} programas, {len(export['byExpediente'])} expedientes agrupados)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
