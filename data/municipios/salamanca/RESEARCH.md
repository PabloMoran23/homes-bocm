# Salamanca — investigación portal ayuntamiento

Municipio: **Salamanca** (`salamanca`) — Castilla y León / provincia Salamanca — boletín **BOCYL** (`bocyl`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa (Liferay DXP) | https://www.aytosalamanca.es |
| Sede electrónica (STA / T-Systems) | https://www.aytosalamanca.gob.es |
| Tablón de edictos | https://www.aytosalamanca.gob.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON_EDICTOS |
| Catálogo de trámites | https://www.aytosalamanca.gob.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |
| Urbanismo — planes en tramitación | https://www.aytosalamanca.es/urbanismo-vivienda-y-obras/planes-tramitacion |
| Archivo urbanístico | https://www.aytosalamanca.es/archivo-urban%C3%ADstico |
| Visor PGOU (iframe GeoVincles) | https://www.aytosalamanca.es/w/visor-pgou-1 → `https://gis.geovincles.com/clients/viewer/salamanca/visor.php` |

## Cómo se listan expedientes / proyectos

1. **Web Liferay (`aytosalamanca.es`)** — Páginas `/w/...` con anuncios de información pública, aprobaciones iniciales/definitivas, convenios urbanísticos, planes parciales y modificaciones PGOU. Índices en `/urbanismo-vivienda-y-obras/planes-tramitacion` y `/archivo-urbanístico`. Contenido HTML estático + enlaces a PDFs en `/documents/`.
2. **Tablón STA** — DataTables con metadatos embebidos en JS (`metadata_TABLON_EDICTOS_LISTADO.browse.data.rows`): fecha, descripción (link a detalle), categoría. ~89 filas en julio 2026 (histórico limitado en la página; poca actividad urbanística reciente).
3. **Catálogo STA** — Array JSON `dataset_CATSERV` (~221 trámites) con ficha por procedimiento (`DETALLE={dboid}`).

## Cómo se publican licencias

- **No hay dataset público de licencias concedidas** (listado tabular con coords).
- El tablón publica ocasionalmente solicitudes de licencia ambiental (actividad, no obra mayor).
- El catálogo STA expone trámites de licencias de obra (obra mayor, demolición, parcelación, primera ocupación, calicatas, prórrogas, vados).
- Estrategia del adapter: trámites informativos del catálogo + entradas del tablón que coincidan con patrón licencia/obra.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Visor PGOU GeoVincles (`gis.geovincles.com/clients/viewer/salamanca/visor.php`, stack vwgeo30 + Google Maps). Muestra capas del planeamiento municipal.
- **Estrategia:** El visor es iframe sin API ArcGIS/WFS pública accesible desde fuera (directorios y config devuelven 403/404). No hay campo de enlace expediente → polígono en tablón ni web.
- **Limitaciones:** Sin servicio REST/WFS descubierto; geometría no automatizable de forma fiable. El orquestador aplicará centroide municipal + jitter.

## Limitaciones

- Tablón STA con ventana temporal corta (~1 año visible).
- Licencias de obra no se publican como concesiones georreferenciadas.
- Visor PGOU cerrado a scraping programático (403 en rutas internas GeoVincles).
- Sede STA sin keyword `URB` en catálogo (filtrado por nombre de trámite).
