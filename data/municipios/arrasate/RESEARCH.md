# Arrasate / Mondragón — portal municipal

## URLs base y semillas

- Web corporativa (Plone 6): https://www.arrasate.eus (es | eu)
- Transparencia → documentación en exposición pública (carpeta con expedientes/títulos y PDFs):
  - https://www.arrasate.eus/es/ayuntamiento/transparencia/decisiones-normativa-y-documentacion/documentacion-en-exposicion-publica
- Tablón de anuncios (sede Gipuzkoa, entidad 55): enlace desde el ayuntamiento a `uzt.gipuzkoa.eus` — listado ASP.NET con filtros por tipo y año
- GeoArrasate (mapas y accesos a visores): https://www.arrasate.eus/es/municipio/geoarrasate
  - Enlaces a Web AppBuilder (`gis.arrasate.eus/portal/apps/webappviewer/...`), p. ej. «Usos globales del Planeamiento»

## Cómo se listan expedientes / proyectos

- **Exposición pública:** HTML Plone; cada ítem es una URL hija con `documentFirstHeading` (título en MAYÚSCULAS) y enlaces a PDF (p. ej. botón «Publicación GAO» con nombre `gaoko-iragarkia_YYYY_MM_DD.pdf` para inferir fecha).
- No hay API JSON pública en esa carpeta; el adapter parsea enlaces hijos y títulos.
- **Planeamiento:** ArcGIS REST MapServer municipal bajo `https://gis.arrasate.eus/server/rest/services/Arrasate_planeamendua/...` con capas de usos del suelo (p. ej. carpeta `LURZORU HIRITARREZINEKO EREMU BANAKETA`, subcapa **21** «LURZO HIRITARREZINA», polígonos con atributo `A01_KATEGORIA`).

## Licencias de obra

- No hay listado dedicado en el tablón municipal indexado de forma sencilla desde el mismo dominio; las **solicitudes de licencia** aparecen como entradas en exposición pública (p. ej. códigos tipo `2026HURB…`, «Solicitud de licencia…»).
- El adapter extrae filas que en el título contienen «licencia» u otros patrones desde la misma carpeta de transparencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** ArcGIS REST `MapServer/21` (polígonos PGOU / uso del suelo urbanizable), `outSR=4326`, `f=geojson`. Visor web: apps en `gis.arrasate.eus`.
- **Estrategia:** `query` paginada (`resultOffset` / `resultRecordCount`) sobre la capa 21; cada polígono se guarda como `geom_geojson` (WGS84). No enlaza a expediente concreto: son **parcels de planeamiento**, no límites por expediente.
- **Limitaciones:** la exposición pública es HTML+PDF sin geometría embebida; el tablón de la sede es grado 7 y no se usó como fuente principal en esta integración; categorías de capa en euskera (`A01_KATEGORIA`).

## Limitaciones generales

- Fechas de proyectos en exposición pública: a veces solo año en el título o fecha en nombre de PDF GAO.
- Búsqueda Plone global puede devolver muchas noticias; el listado directo de la carpeta es más estable.

## Verificación pipeline (local)

- `municipio run --step all`: proyectos **18** filas (7 exposición pública + 11 muestra ArcGIS PGOU), licencias **1** (carpeta transparencia).
- Parity `proyectos.jsonl`: `with_geometry` **11** / 18 (`parity-report.json` tras `geocode`).
