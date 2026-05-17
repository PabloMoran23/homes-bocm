# Web · BOCM Urbanismo (Madrid)

Portal estático para explorar y agregar anuncios de urbanismo ya parseados en `../output/history_parsed_incremental.csv`.

## Requisitos

- Node 20+
- CSV e índice de coordenadas en `poc-bocm/output/` (como en el resto del POC).

## Comandos

```bash
npm install
npm run build-data   # genera public/data/projects.json y summary.json
npm run dev          # http://localhost:3000
```

`npm run build` ejecuta `build-data` antes de `next build` (script `prebuild`).

## Rutas

| Ruta | Descripción |
|------|-------------|
| `/` | Inicio y cifras del resumen |
| `/explore` | Mapa (Leaflet/OSM), filtros y tabla |
| `/estadisticas` | Barras por municipio, tipo y año |
| `/planes` | Descripción de tiers y simulación de plan |

## Planes (tiers)

El selector **Plan** en la cabecera guarda el nivel en `localStorage` y en la cookie `bocm-tier` (`free` \| `particular` \| `empresa`). Afecta a límites de tabla, exportación CSV, vista de estadísticas y longitud del resumen en la ficha (MVP sin pago real).

## Stack

Next.js (App Router), Tailwind CSS v4, react-leaflet.
