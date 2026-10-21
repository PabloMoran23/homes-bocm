"""Conservative export rules for reviewed municipal onboarding adapters."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from municipio.entity_policy import classify


def reviewed_records(path: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kind = 'licencia' if 'licencias' in path.name else 'proyecto'
    result = []
    for row in rows:
        decision = classify(row, kind=kind)
        if kind == 'licencia':
            # A public form or dated notice does not establish a granted permit.
            if not (decision['activity_eligible'] and decision['grant_evidenced']):
                continue
        elif decision['entity_type'] in {'fuera_dominio', 'tramite_reutilizable'}:
            continue
        if row.get('origen') in {'referencia_portal', 'referencia_visor', 'static_ref'}:
            continue
        result.append(row)
    return result
