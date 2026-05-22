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

El workflow `.github/workflows/refresh-web-data.yml` corre cada dia a las
`03:17 UTC` y tambien se puede lanzar manualmente. Esta es la version barata:
no descarga ni parsea boletines BOCM nuevos con LLM.

El flujo es:

1. Restaura la cache de datos generados (`output/`, `db/poc_local.sqlite`).
2. Refresca datasets publicos de Madrid: SIGMA, licencias, SQLite y Supabase
   cuando haya secreto.
3. Regenera `web/public/data/`.
4. Ejecuta `npm run build`.
5. Hace commit de `web/public/data/` si hay cambios. Ese commit dispara Vercel.

## Secretos necesarios

En GitHub, configura:

- `SUPABASE_DB_URL`: opcional, para sincronizar SQLite con Supabase.
- `DATA_SNAPSHOT_URL`: opcional, solo para bootstrap. Debe apuntar a un
  `.tar.gz` con `output/` y opcionalmente `db/poc_local.sqlite`.

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
db/poc_local.sqlite
```

Despues configura `DATA_SNAPSHOT_URL` temporalmente, lanza el workflow manual y
retira el secreto si no quieres mantenerlo.
