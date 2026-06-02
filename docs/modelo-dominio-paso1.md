# Modelo de dominio — paso 1

Tablas funcionales nuevas (las legacy siguen activas hasta el backfill):

| Tabla | Sustituye conceptualmente |
|-------|---------------------------|
| `homes.proyecto` | `sigma_catalog_expediente`, `sigma_ambito_geom`, `sigma_expediente_metric`, `sigma_visor_expediente`, `link_project_sigma`, campos principales de `project_boletin` |
| `homes.licencia` | `actuacion_edificacion`, `link_licencia_sigma` |
| `homes.inmueble` | Sin cambios (ubicación; paso futuro: renombrar a `ubicacion`) |

## Qué queda fuera de estas dos tablas (por diseño)

- **Filas repetibles**: `sigma_vis_tramite`, `sigma_nti_document`, `sigma_pdf_metric`, `sigma_boletin_sibling` → muchas filas por expediente; paso posterior o JSON agregado.
- **Programas**: `sigma_programa` / `sigma_programa_miembro` → agrupación N:1 de proyectos.
- **Ingestión**: `source`, metadatos de pipeline.

## Mapeo de columnas → `proyecto`

| Origen | Columnas en `proyecto` |
|--------|------------------------|
| `sigma_catalog_expediente` | `expediente_grupo`, `exp_numero_original`, `sigma_layer_kind`, `denominacion`, `fase`, … |
| `sigma_ambito_geom` | `geom_geojson`, `bbox_*`, `centroid_*`, `area_approx_m2`, `geom_synced_at` |
| `sigma_expediente_metric` | `metric_fase`, `familia_expediente`, `metrics_json`, … |
| `sigma_visor_expediente` | `visor_*`, `tramitacion`, `nti_*`, clasificación, `resumen_contenido` |
| `project_boletin` | Prefijo `bocm_*` + `bocm_primary_id` |
| `link_project_sigma` | `bocm_sigma_match_*`, `sigma_enlace_snapshot` |
| Consolidado | `num_viviendas_max`, `sup_*`, `municipio`, `lat`/`lng` |

## Mapeo → `licencia`

| Origen | Columnas en `licencia` |
|--------|------------------------|
| `actuacion_edificacion` | Todas las columnas de negocio + `inmueble_id` |
| `link_licencia_sigma` | `proyecto_id`, `proyecto_match_*` |

## Archivos

- Supabase: `supabase/migrations/20250602120000_proyecto_licencia.sql`
- Referencia PG: `db/schema_dominio.sql`
- SQLite local: `db/schema_dominio.sqlite.sql` (migración v4 en `migrate_sqlite.py`)

## Sync CI / backfill

```bash
# Desde output/ (recomendado, tras madrid_ayto_sync)
python3 db/sync_dominio_to_supabase.py
python3 db/sync_dominio_to_supabase.py --skip-licencias
python3 db/sync_dominio_to_supabase.py --licencias-years "2025,2026"

# Desde tablas legacy en Supabase (solo si no hay output/)
python3 db/backfill_dominio_from_legacy.py
```

Workflow `refresh-web-data.yml`: sync dominio → **después** `npm run build-data`.

## Tablas hijas

| Tabla | Contenido |
|-------|-----------|
| `proyecto_bocm_publicacion` | Artículos BOCM por proyecto |
| `proyecto_tramite` | Tramitación visor (normalizada) |
| `proyecto_documento` | NTI + URLs documentación |
| `proyecto_pdf_metric` | Métricas por PDF |

`link_licencia_sigma` / `licencia.proyecto_id`: job aparte, no en Actions.
