# Candelario — investigación portal ayuntamiento

**Municipio:** Candelario (Castilla y León, Salamanca)  
**Fecha:** 2026-08-08

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress Enfold) | https://www.candelario.es | Portal activo (tema Candelario/Enfold) |
| Urbanismo | https://www.candelario.es/urbanismo/ | Noticias de obras, urbanización, normas; enlace PDF licencia |
| Documentación administrativa | https://www.candelario.es/ayuntamiento/documentacion-administrativa/ | Formularios y trámites |
| Información municipal | https://www.candelario.es/ayuntamiento/informacion-municipal/ | Datos generales |
| Solicitud licencia (PDF) | https://www.candelario.es/wp-content/uploads/2024/03/Solicitud-de-Licencia-o-Autorizacion-Urbanistica.pdf | Modelo solicitud licencia/autorización urbanística |
| Sede electrónica (espublico gestiona) | https://candelario.sedelectronica.es/board | Tablón de anuncios (~7 filas visibles) |
| Consulta expedientes | https://candelario.sedelectronica.es/expedientes | Consulta individual (sin listado histórico) |
| WP REST API | https://www.candelario.es/wp-json/wp/v2 | posts (categoría urbanismo id=59, 113 entradas) + pages |

## Cómo se listan expedientes

- **WordPress:** categoría `Urbanismo` (id 59) con noticias de obras, aprobaciones, normas urbanísticas, proyectos de abastecimiento, etc. REST API `wp/v2/posts?categories=59`.
- **Tablón sede:** HTML tabla espublico con `preview-document`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Contenido actual: bandos municipales (caza, agua, desbroce), no urbanismo activo.
- **Sin visor de expedientes** ni API JSON de listado histórico completo en sede.
- **BOCYL:** boletín regional (`boletin_source_id: bocyl`, 6 entradas en CSV).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Tablón actual sin licencias individuales publicadas.
- Formulario PDF en página urbanismo: «Solicitud de licencia de obras».
- Estrategia adapter: páginas informativas de trámites + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Candelario'`
  - Resultados: 1 instrumento de ámbito + 10 sectores SAU (Suelo Apto para Urbanizar) con polígono
  - Campo sector: `n_sector`, `n_num_sect` (SAU-1 … SAU-9)
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP/tablón por coincidencia de nombre de sector (SAU) en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo muestra anuncios recientes (bandos, no urbanismo).
  - Noticias WP de obras sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL (sectores/instrumentos), no para licencias individuales.

## Limitaciones generales

- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio pequeño (~900 hab.); volumen moderado de publicaciones urbanísticas en WP.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`).
