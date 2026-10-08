# Web · Homes Urbanismo (Madrid)

Portal Next.js: mapa unificado (SIGMA + licencias + BOCM), boletín por zona, fichas y
estadísticas. Datos estáticos en `public/data/`; Supabase para RPC dinámicos.

## Requisitos

- Node 20+
- Para regenerar datos: CSV/artefactos en `poc-bocm/output/` (ver README raíz).
- `web/.env.local` con `NEXT_PUBLIC_SUPABASE_*` (copiar de `.env.local.example`).

## Comandos

```bash
npm install
npm run dev:public      # MVP Madrid (como producción)
npm run dev             # edición full (todas las rutas de desarrollo)
npm run build-data      # regenera public/data (scope según BUILD_DATA_SCOPE)
npm run build:public    # build producción con datos madrid-public
npm run verify:production   # comprueba datos + build public
```

En Vercel no se ejecuta `build-data` (`SKIP_BUILD_DATA=1`); los JSON deben estar en git.
Ver `../docs/production-web.md`.

## Rutas (edición `public`)

| Ruta | Descripción |
|------|-------------|
| `/` | Landing |
| `/explore` | Mapa unificado Madrid |
| `/boletin` | Qué ocurre en tu zona |
| `/madrid/estadisticas` | Panel SIGMA + licencias |
| `/proyecto/[id]`, `/ubicacion/[ndp]` | Fichas |

Rutas `/madrid/bocm`, `/planes`, etc. están en desarrollo (redirigen a `/en-desarrollo`).

## Stack

Next.js 16 (App Router), Tailwind CSS v4, react-leaflet, Chart.js, Supabase.

## Miniaturas del directorio de provincias

`/proyectos` sirve imágenes WebP locales de `public/maps/provinces/`; no inicializa
MapLibre ni descarga teselas en el navegador para las tarjetas. Los mapas de las
páginas de provincia y municipio siguen siendo interactivos.

Al cambiar la cobertura de `data/project-directory.json`, regenerar y guardar las
miniaturas junto con los datos:

```bash
npm run build:province-previews  # requiere red; usa teselas de OpenFreeMap
npm run check:province-previews # verifica cobertura y dimensiones sin red
```

La generación se ejecuta explícitamente, no durante una visita ni en el build de
Vercel. Mantener los créditos de OpenStreetMap y OpenMapTiles del directorio.
