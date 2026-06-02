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

Workflow `refresh-web-data.yml`: sync dominio → **después** `npm run build-data` (con `SUPABASE_DB_URL` lee dominio vía `db/export_web_data_from_supabase.py`; sin URL, fallback a `output/` + CSV).

## Tablas hijas

| Tabla | Contenido |
|-------|-----------|
| `proyecto_bocm_publicacion` | Artículos BOCM por proyecto |
| `proyecto_tramite` | Tramitación visor (normalizada) |
| `proyecto_documento` | NTI + URLs documentación |
| `proyecto_pdf_metric` | Métricas por PDF |

`link_licencia_sigma` / `licencia.proyecto_id`: job aparte, no en Actions.

## Paso 3 — RPCs y web

Migración `supabase/migrations/20250602160000_rpc_dominio.sql` (aplicada en remoto):

| RPC | Lee de |
|-----|--------|
| `get_sigma_ficha`, `get_sigma_clasificacion` | `proyecto`, `proyecto_bocm_publicacion` |
| `get_ubicacion_ficha` | `inmueble`, `licencia`, `proyecto` (link + ST_Contains en `geom_geojson`) |
| `boletin_area` | `inmueble`, `licencia`, `proyecto` (centroides) |
| `get_proyecto_portal` | `proyecto` (fila BOCM → `load-project.ts`) |
| `list_proyectos_madrid`, `list_sigma_clasificacion` | API `/api/dominio/*` (opcional frente a JSON estático) |

Web: `load-project.ts`, fichas SIGMA/ubicación y clasificación vía RPC; exploradores Madrid (`ExploreMadridApp`, `MadridSigmaExplorer`, `MadridBocmExplorer`) usan `/api/dominio/*` con fallback JSON. GeoJSON de capas SIGMA y métricas del mapa siguen en `public/data` (generados por `build-data`).

## Programas SIGMA (`programa_id`)

- Columna `homes.proyecto.programa_id` → `homes.sigma_programa.programa_id` (cluster inferido).
- Tras export/sync: `db/sync_programas_dominio.py` (también al final de `export_web_data_from_supabase.py`).
- Metadatos del programa (título, miembros, roles) en `sigma_programa` + `sigma_programa_miembro`; la web sigue usando `madrid-sigma-programas.json` generado desde Supabase.
