#!/usr/bin/env python3
"""Exporta clasificación SIGMA (5 ejes + categoría) → web/public/data/madrid-sigma-clasificacion.json"""
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

POC_ROOT = Path(__file__).resolve().parents[1]
DB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_DIR))

from migrate_sqlite import expediente_grupo_from_num  # noqa: E402
from sigma_classification import classify_sigma_project  # noqa: E402
from visor_resumen import resumen_contenido_from_visor_ficha  # noqa: E402

VISOR_CANDIDATES = [
    POC_ROOT / "output/madrid_viso_expedientes.json",
    POC_ROOT / "web/public/data/madrid-sigma-visor-slim.json",
]
SIGMA_CATALOG = POC_ROOT / "web/public/data/madrid-sigma.json"
METRICS = POC_ROOT / "web/public/data/madrid-sigma-metrics.json"
DEFAULT_OUT = POC_ROOT / "web/public/data/madrid-sigma-clasificacion.json"


def _load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _catalog_context() -> dict[str, dict]:
    raw = _load_json(SIGMA_CATALOG)
    if not raw:
        return {}
    out: dict[str, dict] = {}
    for e in raw.get("expedientes") or []:
        num = e.get("EXP_TX_NUMERO")
        if not num:
            continue
        grupo = expediente_grupo_from_num(str(num))
        out[grupo] = {
            "fase": e.get("FAS_TX_DENOM"),
            "tipo_figura": e.get("TFIG_TX_ABREV"),
            "sigma_layer_kind": e.get("sigma_layer_kind"),
            "source": e.get("source"),
        }
    return out


def _metrics_context() -> tuple[dict[str, float], dict[str, int]]:
    raw = _load_json(METRICS)
    if not raw:
        return {}, {}
    area: dict[str, float] = {}
    viviendas: dict[str, int] = {}
    for grupo, row in (raw.get("byExpediente") or {}).items():
        if not isinstance(row, dict):
            continue
        sup = row.get("sup_total_m2")
        if isinstance(sup, (int, float)) and sup > 0:
            area[str(grupo)] = float(sup)
        nv = row.get("num_viviendas_max")
        if isinstance(nv, int) and nv > 0:
            viviendas[str(grupo)] = nv
    return area, viviendas


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_OUT
    visor_raw = None
    visor_path = None
    for candidate in VISOR_CANDIDATES:
        visor_raw = _load_json(candidate)
        if visor_raw:
            visor_path = candidate
            break
    if not visor_raw:
        print("no visor json found", file=sys.stderr)
        return 1

    catalog_by_grupo = _catalog_context()
    area_by_grupo, viviendas_by_grupo = _metrics_context()
    by_grupo: dict[str, dict] = {}

    for grupo, rec_raw in (visor_raw.get("byGrupoExpediente") or {}).items():
        if not grupo or not isinstance(rec_raw, dict):
            continue
        rec = dict(rec_raw)
        if rec.get("sinDatosVisor"):
            continue
        visor_ficha = rec.get("visorFicha") if isinstance(rec.get("visorFicha"), dict) else None
        resumen_contenido = resumen_contenido_from_visor_ficha(visor_ficha)
        catalog = catalog_by_grupo.get(grupo) or {}
        layer_kind = str(rec.get("sigmaLayerKind") or catalog.get("sigma_layer_kind") or catalog.get("source") or "")
        classification = classify_sigma_project(
            visor_ficha=visor_ficha,
            resumen_contenido=resumen_contenido,
            sigma_layer_kind=layer_kind or None,
            catalog=catalog,
            area_approx_m2=area_by_grupo.get(grupo),
            num_viviendas_max=viviendas_by_grupo.get(grupo),
        )
        by_grupo[str(grupo)] = {
            "tipoLegal": classification["tipo_legal"],
            "escala": classification["escala"],
            "contenidoPrincipal": classification["contenido_principal"],
            "faseNormalizada": classification["fase_normalizada"],
            "categoriaProyecto": classification["categoria_proyecto"],
            "tipoObra": classification["tipo_obra"],
            "confianza": classification["clasificacion_confianza"],
        }

    payload = {
        "generatedAt": datetime.now(UTC).isoformat(),
        "sourceVisor": str(visor_path.relative_to(POC_ROOT)) if visor_path else None,
        "count": len(by_grupo),
        "byExpediente": by_grupo,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    print(f"OK: {out_path} ({len(by_grupo)} expedientes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
