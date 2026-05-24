# Supabase · Homes / BOCM

## Proyecto

- **Supabase:** `hungry-db` (`ocfeayxxhtymwybcezyj`, eu-west-3)
- **Esquema:** `homes` (separado de `public.products`, etc.)
- **URL API:** https://ocfeayxxhtymwybcezyj.supabase.co

> Si prefieres un proyecto solo para Homes, crea uno nuevo en Supabase y vuelve a aplicar las migraciones de `supabase/migrations/`.

## 1. Exponer el esquema `homes` en la API

Dashboard → **Project Settings** → **API** → **Exposed schemas** → añade `homes`.

Sin esto, el cliente JS (`@supabase/supabase-js`) solo ve `public`.

## 2. Variables de entorno

Copia `.env.example` → `.env` en la raíz del POC (no lo subas a Git):

```bash
cp .env.example .env
# Edita SUPABASE_DB_URL con la contraseña de postgres
```

Para la web, en `web/.env.local`:

```bash
NEXT_PUBLIC_SUPABASE_URL=https://ocfeayxxhtymwybcezyj.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=<anon key del dashboard>
```

## 3. Subir datos desde SQLite

```bash
cd poc-bocm
pip install -r db/requirements-supabase.txt
export SUPABASE_DB_URL='postgresql://...'

# Primera carga completa (~5–15 min según red)
python3 db/sync_sqlite_to_supabase.py --truncate

# Solo Madrid / ubicaciones + visor SIGMA
python3 db/sync_sqlite_to_supabase.py --only sigma,visor,ambito,inmueble,licencias,links
python3 db/sync_madrid_public_to_supabase.py --skip-licencias
```

Volúmenes locales (referencia):

| Tabla | Filas |
|-------|------:|
| project_boletin | 16k |
| sigma_catalog + ámbitos | 3.9k |
| sigma_visor_expediente | según `output/madrid_viso_expedientes.json` |
| inmueble | 64k |
| actuacion_edificacion | 160k |
| link_licencia_sigma | 866k |

## 4. Migraciones

Las SQL están en `supabase/migrations/`. Ya aplicadas vía MCP:

- `homes_initial_schema`
- `homes_rls` (lectura pública anon en tablas `homes.*`)

Para otro proyecto: pega el SQL en el SQL Editor o usa `supabase db push`.

## 5. Siguiente paso (web + Vercel)

- Sustituir lecturas SQLite en `/api/boletin-area` y fichas ubicación por consultas a `homes.*`
- Mantener `public/data/*.geojson` para mapas estáticos o generarlos desde Supabase en build
- En Vercel: variables `NEXT_PUBLIC_SUPABASE_*` + `SUPABASE_SERVICE_ROLE_KEY` (solo server)
