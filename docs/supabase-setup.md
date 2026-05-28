# Supabase · Homes / BOCM

## Proyecto (producción)

- **Supabase:** Homes BOCM (`rjwcmbllrzqvsbgaajmp`, eu-central-1)
- **Esquema:** `homes` (separado de `public`, etc.)
- **URL API:** https://rjwcmbllrzqvsbgaajmp.supabase.co
- **Pooler (sync / CI):** `aws-1-eu-central-1.pooler.supabase.com:6543`

> Documentación antigua citaba otro proyecto (`ocfeayxxhtymwybcezyj`). Usar solo el ref anterior salvo migración explícita.

## 1. Exponer el esquema `homes` en la API

Dashboard → **Project Settings** → **API** → **Exposed schemas** → añade `homes`.

Sin esto, el cliente JS (`@supabase/supabase-js`) solo ve `public`.

## 2. Variables de entorno

Raíz del POC (`.env`, no commitear):

```bash
cp .env.example .env
# SUPABASE_DB_URL con pooler 6543 (codifica # en contraseña como %23)
```

Web (`web/.env.local`):

```bash
NEXT_PUBLIC_SUPABASE_URL=https://rjwcmbllrzqvsbgaajmp.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key del dashboard>
```

Vercel (Production): las mismas `NEXT_PUBLIC_*`. El service role **no** va al cliente;
solo en servidor local o scripts de sync (`SUPABASE_SERVICE_ROLE_KEY` en `.env` raíz).

## 3. Carga y refresco de datos

```bash
cd poc-bocm
pip install -r db/requirements-supabase.txt
export SUPABASE_DB_URL='postgresql://postgres.rjwcmbllrzqvsbgaajmp:...@aws-1-eu-central-1.pooler.supabase.com:6543/postgres'

# Primera carga desde SQLite local (desarrollo)
python3 db/sync_sqlite_to_supabase.py --truncate

# Madrid público (producción / CI)
python3 db/sync_madrid_public_to_supabase.py --skip-licencias
python3 db/sync_madrid_public_to_supabase.py --licencias-years "2025,2026"
```

El workflow semanal `.github/workflows/refresh-web-data.yml` ejecuta sync + `build-data`
y commitea `web/public/data/`. Ver `docs/production-web.md`.

## 4. Migraciones

SQL en `supabase/migrations/`:

- `homes_initial_schema`
- `homes_rls` (lectura anon en tablas `homes.*`)

En otro proyecto: SQL Editor o `supabase db push`.

## 5. Uso en la web

| Funcionalidad | Fuente |
| --- | --- |
| Mapa `/explore`, estadísticas | JSON/GeoJSON en `web/public/data/` |
| `/api/boletin-area`, fichas ubicación/SIGMA | RPC Supabase `homes.*` |
| Admin / sync | Service role (solo local / CI) |

Si Supabase no está configurado en Vercel, el mapa y estadísticas siguen funcionando;
boletín por zona y fichas dinámicas degradan o fallan según la ruta.
