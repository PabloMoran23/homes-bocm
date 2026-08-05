# Candeleda — investigación portal ayuntamiento

**Municipio:** Candeleda (Castilla y León, Ávila)  
**Fecha:** 2026-08-02

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://ayuntamientocandeleda.es | Portal activo (tema Woodmart + Elementor) |
| Urbanismo | https://ayuntamientocandeleda.es/urbanismo/ | Sección urbanismo, enlaces a normas y licencias |
| Normas urbanísticas / PGOU | https://ayuntamientocandeleda.es/normas-urbanisticas/ | ~15 PDFs revisión NNSS (memoria, planos, normativa, BOCYL) |
| Revisión NNSS (info pública) | https://ayuntamientocandeleda.es/revision-de-las-normas-urbanisticas-municipales-e-informe-de-sostenibilidad-ambiental/ | Anuncio información pública 2019 |
| Información pública | https://ayuntamientocandeleda.es/informacion-publica/ | Índice de publicaciones |
| Cartel licencias | https://ayuntamientocandeleda.es/cartel-licencias-urbanisticas/ | Modelo cartel informativo obras (oct 2025) |
| Modelo licencia nave agrícola | https://ayuntamientocandeleda.es/modelo-normalizado-de-licencia-para-construccion-de-nave-agricola/ | Formulario licencia |
| Descargas PDF | https://ayuntamientocandeleda.es/descargas-de-modelos-e-impresos-normalizados-en-pdf-2/ | Impresos normalizados (sin título en enlaces) |
| Bandos | https://ayuntamientocandeleda.es/bandos/ | Bandos municipales |
| Sede electrónica (espublico gestiona) | https://ayuntamientocandeleda.sedelectronica.es/board | Tablón de anuncios (~10 filas visibles) |
| WP REST API | https://ayuntamientocandeleda.es/wp-json/wp/v2 | pages + posts |

## Cómo se listan expedientes

- **WordPress:** páginas estáticas con PDFs de planeamiento en `/wp-content/uploads/`. REST API `wp/v2/pages` y `wp/v2/posts` (noticias con licitaciones urbanísticas, pliegos, etc.).
- **Tablón sede:** HTML tabla espublico con `preview-document`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Categoría `Urbanismo` / procedimiento `Actuaciones Urbanísticas`.
- **Sin visor de expedientes** ni API JSON de listado histórico completo en sede.
- **BOCYL:** publicaciones referenciadas en tablón (p. ej. `BOCYL-D-09072026-131-26`).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Tablón actual muestra principalmente información pública y actuaciones urbanísticas (no concesiones individuales).
- Formularios/modelos en web: cartel licencias, licencia nave agrícola, descargas PDF.
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Candeleda'`
  - Campo sector: `n_sector` (41 sectores con polígono); instrumento: `n_titulo` (1 revisión NNSS)
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP/tablón por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo muestra anuncios recientes (sin archivo scrapeable).
  - PDFs PGOU sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Sede `/info` responde lento; tablón `/board` accesible.
- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio pequeño (~5.000 hab.); volumen bajo de publicaciones urbanísticas activas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 12 entradas en CSV).
