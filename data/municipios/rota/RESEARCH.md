# Rota — investigación portal ayuntamiento

Municipio: **Rota** (`rota`)  
Provincia: Cádiz | CCAA: Andalucía | INE: 11032 | Boletín: BOJA

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Joomla/YOOtheme) | https://www.aytorota.es |
| Delegación Urbanismo | https://www.aytorota.es/ayuntamiento/delegaciones/urbanismo.html |
| PEPCH (Plan Especial Protección Conjunto Histórico) | https://www.aytorota.es/ayuntamiento/delegaciones/urbanismo/pepch.html |
| Transparencia municipal (web) | https://www.aytorota.es/ayuntamiento/transparencia.html |
| Sede electrónica (espublico gestiona) | https://aytorota.sedelectronica.es |
| Tablón de anuncios | https://aytorota.sedelectronica.es/board |
| Transparencia urbanismo (sede) | https://aytorota.sedelectronica.es/transparency/61577592-b9a7-4b56-bb0f-6d4d2c92c036/ |
| Catálogo de trámites | https://aytorota.sedelectronica.es/dossier |
| Consulta expedientes (Cl@ve) | https://aytorota.sedelectronica.es/expedientes |
| SITUA (Junta de Andalucía, INE 11032) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=11032 |

## Cómo se listan expedientes / proyectos

- **Web municipal**: Joomla 5 + YOOtheme. La sección PEPCH publica decenas de PDFs bajo `/images/espacio_ciudadano/delegaciones/urbanismo/1_instrumentos/pepch/` (planos de información, ordenación, catálogo, normas). La ruta `/urbanismo` en la web devuelve error 500 (BD); el contenido útil está en delegaciones/urbanismo.
- **Sede espublico — tablón**: tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom` y enlaces `/preview-document/{uuid}`.
- **Sede — transparencia**: sección «05. URBANISMO» con carpetas Wicket (instrumentos de planeamiento ~158 docs, convenios, gestión urbanística, proyectos de actuación). Los documentos requieren navegación AJAX; el adapter indexa los títulos de carpeta como metadatos de planeamiento.
- **SITUA**: visor autonómico de instrumentos de planeamiento digitalizado; no hay enlace directo expediente municipal → polígono.
- **Sitemap**: `sitemap.xml` responde HTTP 500; no usado.

## Cómo se publican licencias

- No hay dataset histórico de concesiones con coordenadas.
- Edictos y notificaciones en el tablón sede (filtrado por procedimiento/categoría urbanística).
- Trámites de licencia de obra/actividad vía catálogo `/dossier` (informativo, sin listado de concesiones).
- Consulta de expedientes en `/expedientes` requiere identificación electrónica.

## Geometría / visor

- **geometry_status**: `unavailable`
- **Fuentes**: no hay visor urbanístico municipal (ArcGIS REST, WFS ni GeoJSON por expediente). SITUA ofrece consulta de planeamiento a escala autonómica (raster/capas generales) sin API enlazable al código de expediente del tablón.
- **Estrategia**: el adapter no implementa `_fetch_geometry`; el orquestador aplicará centroide municipal (`manifest.centroid`) + jitter.
- **Limitaciones**: documentación en PDF; transparencia sede con documentos tras login AJAX; sin ref. catastral en anuncios del tablón.

## Limitaciones generales

- Página `/urbanismo` de la web con error 500.
- Transparencia sede: carpetas con contadores altos pero descarga vía Wicket (no scrapeable masivamente sin sesión).
- Tablón mezcla anuncios de personal, estadística y urbanismo; filtrado por regex en el adapter.
