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

Las imágenes encuadran el contorno provincial del IGN y no muestran puntos de proyectos.
Los límites simplificados se guardan en `data/province-boundaries.json`.

Al añadir provincias a `data/project-directory.json`, regenerar y guardar las
miniaturas junto con los datos:

```bash
npm run build:province-boundaries # opcional: actualiza límites desde el IGN
npm run build:province-previews  # requiere red; usa teselas de OpenFreeMap
npm run check:province-previews # verifica cobertura y dimensiones sin red
```

La generación se ejecuta explícitamente, no durante una visita ni en el build de
Vercel. Mantener los créditos de OpenStreetMap, OpenMapTiles e IGN del directorio.


### Contrato de alcance de las estadísticas

`summary.json.statisticsScope` (versión 1) se genera en ambos exportadores en cada
build: no se mantiene a mano. Declara ámbito, fuentes y territorios incluidos,
periodo observado, fecha de comprobación y denominador de todos los anuncios
publicados. `full` significa conjunto de fuentes incluidas, con cobertura nacional
**parcial**; no prueba exhaustividad ni homogeneidad territorial o temporal.
`madrid-public` nunca es elegible para el panel España.

`npm run build-data` y `npm run build` validan el contrato, incluso cuando
`SKIP_BUILD_DATA=1`. Un manifest ausente, un ámbito desconocido o una divergencia
de los totales aborta el build con `statistics-scope`. Después de actualizar código
que introduce este contrato, hay que regenerar los datos con el exportador habitual
antes de publicar; los snapshots antiguos sin manifest se rechazan. La página
valida de nuevo cada lectura, registra una advertencia y muestra indisponibilidad
nacional ante datos incompatibles. No sustituye esa indisponibilidad con cifras
regionales ni infiere cobertura completa a partir de la presencia de registros.

Pruebas del contrato, adaptador y HTML: `node scripts/test-statistics-scope.mjs`.
Comprobación del artefacto publicado (HTTP/JSON/contrato fallan con salida no cero):
`node scripts/assert-statistics-scope.mjs https://TU_HOST/data/summary.json`.
El intervalo del manifest describe años observados, no años cerrados ni una prueba
de completitud de la ingesta. Las fuentes originales se conservan; cambiar fuentes
o reglas exige regenerar el resumen por el mismo proceso.
