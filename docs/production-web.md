# Produccion web

La web se despliega desde `web/` como proyecto Next.js en Vercel. El build de
produccion usa `web/vercel.json`, que deja `NEXT_PUBLIC_EDITION=public` y
`SKIP_BUILD_DATA=1`; por tanto Vercel sirve los artefactos ya generados en
`web/public/data/`.

## Despliegue

1. Conecta el repo en Vercel con root directory `web`.
2. Configura las variables de entorno de la web:
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
3. Activa el deploy automatico de la rama de produccion (`main`).

No hace falta token de Vercel en GitHub Actions si se usa la integracion Git de
Vercel: cada commit a `main` dispara un nuevo deploy.

## Refresco programado de datos

El workflow `.github/workflows/refresh-web-data.yml` corre cada **lunes** a las
`03:17 UTC` (~05:17 CEST en verano) y tambien se puede lanzar manualmente. Esta
es la version barata: no descarga ni parsea boletines BOCM nuevos con LLM y no
recalcula el cruce caro `link_licencia_sigma`.

### Frecuencia por dataset

| Dataset | Frecuencia | Que hace |
| --- | --- | --- |
| SIGMA (Ayto. Madrid) | Semanal (cada lunes) | Descarga + upsert catalogo y geometrias |
| Licencias urbanisticas | Mensual (dia 1 UTC) | Descarga anos actual y anterior, merge en JSONL, upsert incremental en Supabase |
| `web/public/data` | Semanal | `npm run build-data` con scope `madrid-public` |

En los lunes que no caen en dia 1, el job omite licencias (`--skip-licencias`) y
solo refresca SIGMA. El dia 1 de cada mes (o un run manual con
`refresh_licencias=true`) descarga `YEAR-1,YEAR`, fusiona en
`output/madrid_licencias.jsonl` y sincroniza esos anos sin truncar tablas.

Recarga completa de licencias (solo operacion manual):

```bash
python3 -m sector_geometry.madrid_licencias_download
python3 db/sync_madrid_public_to_supabase.py --licencias-full
```

El flujo semanal es:

1. Restaura la cache de datos generados (`output/`).
2. Refresca SIGMA; licencias solo si toca (dia 1 o dispatch).
3. Sincroniza a Supabase, sin SQLite intermedio.
4. Regenera `web/public/data/`.
5. Ejecuta `npm run build`.
6. Verifica que exista `web/public/data/madrid-dashboard-stats.json` (dashboard de estadísticas).
7. Hace commit de `web/public/data/` (incl. `madrid-dashboard-stats.json`) si hay cambios. Ese commit dispara Vercel.

La página `/madrid/estadisticas` lee ese JSON estático (no Supabase). No hace falta ejecutar `build-data` a mano salvo en local.

## Secretos necesarios

En GitHub, configura:

- `SUPABASE_DB_URL`: connection string Postgres de Supabase para el sync directo.
- `DATA_SNAPSHOT_URL`: opcional, solo para bootstrap. Debe apuntar a un
  `.tar.gz` con `output/`.

Si no existe `DATA_SNAPSHOT_URL`, el workflow intenta descargar el release asset
`poc-bocm-web-baseline.tgz` desde el tag `web-data-baseline`. El tag se puede
cambiar con la variable `DATA_SNAPSHOT_RELEASE_TAG`.

## Bootstrap inicial

El primer run necesita una linea base de datos generados. Si la cache de Actions
esta vacia y no existe snapshot por URL ni release asset, el job falla antes de
tocar `web/public/data/` para evitar publicar un dataset vacio.

Para inicializarlo, sube un snapshot privado con esta estructura:

```text
output/
```

Despues configura `DATA_SNAPSHOT_URL` temporalmente, lanza el workflow manual y
retira el secreto si no quieres mantenerlo.
