"""Conservative export rules for reviewed municipal onboarding adapters."""
from __future__ import annotations
from pathlib import Path
import re
from typing import Any
from municipio.entity_policy import classify, norm


def reviewed_records(path: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kind = 'licencia' if 'licencias' in path.name else 'proyecto'
    result = []
    for row in rows:
        origin = norm(row.get('origen')).replace('-', '_')
        # These adapters explicitly identify navigation links and reusable
        # procedures. A stable scraper ID does not make them project records.
        if (re.search(r'tramit|formular|impreso|(?:^|_)form(?:_|$)', origin)
                or origin in {'catalogo', 'catalog', 'catalog_stub', 'catalogo_stub',
                              'static_ref', 'static_portal', 'info_portal',
                              'pagina_informativa', 'visor_ref', 'geoportal_link',
                              'geoportal_catalog', 'geobdp_catalog',
                              'opendata_catalog_fallback', 'portal_semilla',
                              'gmu_requisitos'}
                or origin.startswith('referencia_')):
            continue
        decision = classify(row, kind=kind)
        if kind == 'licencia':
            # A public form or dated notice does not establish a granted permit.
            if not (decision['activity_eligible'] and decision['grant_evidenced']):
                continue
        elif decision['entity_type'] in {'fuera_dominio', 'tramite_reutilizable'}:
            continue
        if row.get('origen') in {'referencia_portal', 'referencia_visor', 'static_ref'}:
            continue
        if row.get('coord_source') in {'municipio_centroid', 'municipio_centroid_jitter',
                                        'municipal_centroid', 'centroid_fallback'}:
            row = dict(row)
            for key in ('lat', 'lon', 'lng', 'latitude', 'longitude',
                        'coord_source', 'coordinates_crs', 'coordinates_axis_order'):
                row.pop(key, None)
        result.append(row)
    return result
