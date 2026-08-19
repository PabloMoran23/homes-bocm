# Espinosa de los Monteros — investigación portal ayuntamiento

**Municipio:** Espinosa de los Monteros (Castilla y León, Burgos)  
**Fecha:** 2026-08-08

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress TownPress) | https://espinosadelosmonteros.es | Portal activo |
| Normativa urbanística (NUM) | https://espinosadelosmonteros.es/normas-urbanisticas-de-espinosa-de-los-monteros/ | Enlace a PLAU CyL + noticias NUM |
| Normas urbanísticas (alias) | https://espinosadelosmonteros.es/normas-urbanisticas/ | Redirige a sección urbanística |
| Ordenanzas municipales | https://espinosadelosmonteros.es/ordenanzas-municipales/ | Ordenanza tasa licencias urbanísticas (PDF) |
| Trámites y gestiones | https://espinosadelosmonteros.es/tramites-y-gestiones/ | Enlace sede electrónica |
| Sede electrónica (espublico gestiona) | https://espinosadelosmonteros.sedelectronica.es/board | Tablón de anuncios (~9 filas; sin urbanismo actual) |
| PLAU CyL (documentación oficial) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=09&municipio=124 | Archivo planeamiento JCyL |
| WP REST API | https://espinosadelosmonteros.es/wp-json/wp/v2 | posts + pages |

## Cómo se listan expedientes

- **WordPress:** noticias con anuncios de información pública, aprobación inicial/definitiva de NUM y modificaciones puntuales (2021–2026). REST API `wp/v2/posts` filtrable por términos urbanísticos.
- **PLAU CyL:** portal JCyL con documentación oficial del planeamiento (PDFs, fechas BOCYL).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Actualmente empleo público, fiestas y cobranza IAE; sin filas de categoría Urbanismo.
- **Sin visor municipal** de expedientes ni API JSON de listado histórico en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra en web ni tablón.
- Ordenanza fiscal de tasa por licencias urbanísticas en `/ordenanzas-municipales/`.
- Trámites presenciales/sede electrónica sin listado público de concesiones.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 feature NUM), `urbanismo:plau_cyl_sectores` (13 sectores), `urbanismo:plau_cyl_planes_parciales` (0)
  - Filtro: `n_mun = 'Espinosa de los Monteros'`
  - Campo sector: `n_sector`; instrumento: `n_titulo`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP/tablón por coincidencia de nombre de sector (UA-12, AA-18, etc.) en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede sin anuncios urbanísticos recientes.
  - PDFs de modificaciones puntuales en `/wp-content/uploads/` sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Tablón sede con pocos anuncios y sin archivo histórico scrapeable.
- WP mezcla noticias urbanísticas con actualidad general (filtros por regex).
- BOCyL ya parseado en pipeline regional (`bocyl`, 6 entradas).
