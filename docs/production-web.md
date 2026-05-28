# Producción web

La web se despliega desde `web/` como proyecto Next.js en Vercel. El build de
producción usa `web/vercel.json` (`NEXT_PUBLIC_EDITION=public`, `SKIP_BUILD_DATA=1`);
Vercel sirve los artefactos ya generados en `web/public/data/` (no regenera en build).

## Estado actual (revisión 2026-05-28)

| Componente | Estado | Notas |
| --- | --- | --- |
| Repo GitHub | OK | `PabloMoran23/homes-bocm`, rama `main` |
| Vercel proyecto | OK | `homes-bocm`, root `web/` |
| URL producción | OK | https://homes-bocm.vercel.app |
| Env Vercel (Production) | OK | `NEXT_PUBLIC_SUPABASE_*`, `NEXT_PUBLIC_EDITION`, `SKIP_BUILD_DATA` |
| `NEXT_PUBLIC_SITE_URL` | OK | `https://homes-bocm.vercel.app` (cambiar al dominio propio) |
| GitHub `SUPABASE_DB_URL` | OK | Workflow refresh |
| Release baseline datos | OK | Tag `web-data-baseline` → `poc-bocm-web-baseline.tgz` |
| Workflow refresh | OK | Último éxito 2026-05-25; lunes 03:17 UTC |
| Build local `build:public` | OK | `npm run verify:production` en `web/` |

### Rutas públicas (edición `public`)

| Ruta | Uso |
| --- | --- |
| `/` | Landing |
| `/explore` | Mapa unificado Madrid |
| `/boletin` | Tu zona |
| `/madrid/estadisticas`, `/estadisticas` | Panel estadísticas |
| `/proyecto/[id]`, `/ubicacion/[ndp]` | Fichas |
| `/madrid` | Redirige a `/explore` |
| `/madrid/bocm`, `/madrid/sigma`, `/madrid/licencias` | Bloqueadas → «en desarrollo» (vistas legacy) |
| `/planes`, `/fuentes`, `/admin` | Bloqueadas → «en desarrollo» |

APIs en público: `/api/boletin-area`, `/api/geocode-address`, `/api/nti-asset`.

## Despliegue

1. Repo conectado en Vercel, **Root Directory** = `web`.
2. Variables en Vercel (Production):
   - `NEXT_PUBLIC_SUPABASE_URL` → proyecto `rjwcmbllrzqvsbgaajmp`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - Opcional al tener dominio: `NEXT_PUBLIC_SITE_URL=https://tu-dominio.es`
3. Deploy automático en cada push a `main`.

`vercel.json` fija edición pública y omite `build-data` en Vercel; los JSON/GeoJSON
deben estar commiteados en `web/public/data/`.

### Dominio propio (cuando lo elijas)

1. Añade el dominio en Vercel → proyecto `homes-bocm`.
2. Configura DNS (CNAME o registros que indique Vercel).
3. En Vercel → Environment Variables → Production:
   ```bash
   NEXT_PUBLIC_SITE_URL=https://tu-dominio.es
   ```
4. Redeploy de producción (o push vacío a `main`).
5. Comprueba `https://tu-dominio.es/sitemap.xml` y `robots.txt`.

Sin `NEXT_PUBLIC_SITE_URL`, OG y sitemap usan `VERCEL_URL` (subdominio `*.vercel.app`).

## Verificación antes de publicar cambios

```bash
cd web
npm run verify:production   # datos + build public
```

Solo build rápido:

```bash
cd web
NEXT_PUBLIC_EDITION=public SKIP_BUILD_DATA=1 npm run build
```

## Refresco programado de datos

Workflow `.github/workflows/refresh-web-data.yml`: cada **lunes** `03:17 UTC`
(~05:17 CEST en verano); también manual (`workflow_dispatch`).

Versión operativa actual: no descarga BOCM nuevos con LLM ni recalcula
`link_licencia_sigma` en cada run.

### Frecuencia por dataset

| Dataset | Frecuencia | Qué hace |
| --- | --- | --- |
| SIGMA (Ayto. Madrid) | Semanal (lunes) | Descarga + upsert catálogo y geometrías |
| Licencias urbanísticas | Mensual (día 1 UTC) o manual | Años actual y anterior → JSONL → Supabase |
| `web/public/data` | Semanal | `npm run build-data` scope `madrid-public` |

En lunes que no son día 1: solo SIGMA (`--skip-licencias`). Día 1 o run manual con
`refresh_licencias=true`: descarga `YEAR-1,YEAR` y sync incremental.

Recarga completa de licencias (solo manual):

```bash
python3 -m sector_geometry.madrid_licencias_download
python3 db/sync_madrid_public_to_supabase.py --licencias-full
```

Flujo del job:

1. Restaura cache `output/` (o release `web-data-baseline`).
2. Refresca SIGMA; licencias si toca.
3. Sync a Supabase (`SUPABASE_DB_URL`).
4. `npm run build-data` en `web/`.
5. Verifica `madrid-dashboard-stats.json` y `npm run build` (public).
6. Commit `web/public/data/` → push → deploy Vercel.

`/madrid/estadisticas` lee JSON estático; no requiere Supabase en runtime.

## Secretos GitHub

| Secreto / variable | Obligatorio | Uso |
| --- | --- | --- |
| `SUPABASE_DB_URL` | Sí | Sync Postgres en refresh |
| `DATA_SNAPSHOT_URL` | No | Bootstrap inicial `output/` |
| `DATA_SNAPSHOT_RELEASE_TAG` | No | Default `web-data-baseline` |

## Bootstrap inicial

Si cache de Actions vacía y no hay snapshot, el job falla (evita dataset vacío).

1. Subir `.tar.gz` con carpeta `output/` (incl. `history_parsed_incremental.csv`).
2. Publicar como release `web-data-baseline` **o** `DATA_SNAPSHOT_URL` temporal.
3. Lanzar workflow manual; retirar URL si no la necesitáis.

## Supabase

Proyecto de producción: ver `docs/supabase-setup.md` y `.env.example` (ref
`rjwcmbllrzqvsbgaajmp`). Esquema `homes` expuesto en API; RPC para fichas y boletín.
