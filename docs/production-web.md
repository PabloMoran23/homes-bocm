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
no descarga ni parsea boletines BOCM nuevos con LLM y no recalcula el cruce
caro `link_licencia_sigma`.

El flujo es:

1. Restaura la cache de datos generados (`output/`).
2. Refresca datasets publicos de Madrid: SIGMA y licencias.
3. Sincroniza esos datasets directamente a Supabase, sin SQLite intermedio.
4. Regenera `web/public/data/`.
5. Ejecuta `npm run build`.
6. Hace commit de `web/public/data/` si hay cambios. Ese commit dispara Vercel.

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
