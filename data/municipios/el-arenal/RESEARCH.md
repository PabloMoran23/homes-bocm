# El Arenal — investigación portal ayuntamiento

**Municipio:** El Arenal (Castilla y León, Ávila)  
**Fecha:** 2026-08-06

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress Kadence) | https://elarenal.es | Portal activo |
| Urbanismo | https://elarenal.es/urbanismo/ | Licencias urbanísticas por año (2016–2022) + modificación puntual NNSS; ~17 PDFs |
| Ordenanzas | https://elarenal.es/el-ayuntamiento/ordenanzas/ | Ordenanzas fiscales y de servicios (filtrar urbanismo en adapter) |
| Sede electrónica (espublico gestiona) | https://elarenal.sedelectronica.es/board | Tablón de anuncios (vacío en agosto 2026) |
| Trámites sede | https://elarenal.sedelectronica.es/dossier | Catálogo de trámites (licencia urbanística, declaración responsable, etc.) |
| WP REST API | https://elarenal.es/wp-json/wp/v2 | pages + posts |

## Cómo se listan expedientes

- **WordPress:** página `/urbanismo/` con secciones por año y enlaces directos a PDF en `/wp-content/uploads/`. Sin visor de expedientes ni API JSON de listado.
- **Tablón sede:** HTML tabla espublico con `preview-document` (actualmente sin filas publicadas).
- **Sin visor municipal** de expedientes urbanísticos enlazado a geometría.
- **BOCYL:** boletín regional (`boletin_source_id: bocyl`, 7 entradas en CSV).

## Cómo se publican licencias

- Licencias individuales publicadas como PDF en la web (`/urbanismo/`), no como dataset tabular.
- Ejemplos: vivienda unifamiliar Pol.7 Par.377 (2020), casetas de aperos (2018–2019), autorizaciones urbanísticas Venancio Palomo.
- Tablón sede vacío; no hay listado histórico scrapeable en sede.
- Trámites online en sede (solicitud licencia, declaración responsable) sin listado de concesiones.
- Estrategia adapter: PDFs urbanismo + páginas informativas de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'El Arenal'`
  - Resultados: 1 instrumento (NNSS municipales) + 1 sector (SAU «Suelo Apto para Urbanizar»); 0 planes parciales
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP/tablón por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra publicadas solo como PDF sin coords.
  - Tablón sede vacío (sin anuncios recientes scrapeables).
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Sede `/info` responde lento; tablón `/board` accesible pero vacío.
- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio pequeño (~1.100 hab.); volumen bajo de publicaciones urbanísticas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 7 entradas en CSV).
