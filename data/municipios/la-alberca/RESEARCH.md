# La Alberca — investigación portal ayuntamiento

**Municipio:** La Alberca (Castilla y León, Salamanca)  
**Fecha:** 2026-09-19  
**INE:** 37010 | **BOCYL:** 1 entrada en CSV regional

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress) | https://laalberca.com | Portal turístico (tema propio); sin sección `/urbanismo/` |
| Servicios municipales | https://laalberca.com/servicios-municipales/ | Contacto y trámites generales |
| Descargas | https://laalberca.com/descargas/ | Callejero, folletos turísticos, PMBD conjunto histórico |
| Sede electrónica (espublico gestiona) | https://laalberca.sedelectronica.es/board | Tablón de anuncios (~10 filas visibles) |
| Catálogo trámites | https://laalberca.sedelectronica.es/dossier | Trámites sede (sin histórico licencias) |
| Consulta expedientes | https://laalberca.sedelectronica.es/expedientes | Consulta individual (requiere identificación) |
| Junta CYL — archivo PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=37&municipio=010 | 12 documentos aprobados |
| Junta CYL — info pública PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=37&municipio=010 | Expedientes en información pública |
| Diputación Salamanca | http://www.lasalina.es (codMunicipio=10) | Ficha municipal; enlace sede y «Información Urbanística Municipal» |
| WP REST API | https://laalberca.com/wp-json/wp/v2 | 43 páginas + 11 posts (BitNinja 403 sin User-Agent navegador) |

## Cómo se listan expedientes

- **IDECyL WFS PLAU CyL:** capas GeoServer con filtro `n_mun = 'La Alberca'` (`c_mun = 37010`):
  - `urbanismo:plau_cyl_instrumentos_ambito` — 1 NUM (Normas Urbanísticas Municipales, BOCYL 12/02/2025 mod. conjunto histórico)
  - `urbanismo:plau_cyl_planes_parciales` — 3 planes (UR-D-9 «Eras», UR-D-5R, «Dehesa 51»)
  - `urbanismo:plau_cyl_sectores` — 44 sectores con polígono
- **Junta CYL PlanPublica:** índice documental HTML con 12 `cDocId` (NUM, revisiones, planes parciales).
- **Tablón sede:** tabla HTML espublico (`preview-document`). Contenido actual: empleo público, cobranza tributaria, licencias de ocupación (puestos fijos), Red Natura 2000.
- **Sin visor municipal** de expedientes ni API JSON de listado histórico en sede.

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra con coordenadas.
- Tablón con anuncio de «Licencias de Ocupación» (puestos fijos 2026), no licencias de construcción.
- Estrategia adapter: páginas informativas de trámites (tablón, dossier, servicios municipales) + tablón si aparece licencia/obra.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `n_mun = 'La Alberca'`
  - Resultados: 1 instrumento + 3 planes parciales + 44 sectores con `MultiPolygon`/`Polygon` en EPSG:4326
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect`, `n_instrum`, `d_estado`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas tablón/semillas por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Web municipal orientada a turismo; planeamiento solo en IDECyL/Junta CYL.
  - Licencias de obra sin georreferencia pública.
  - Tablón sede solo muestra anuncios recientes (mayoría no urbanismo).
  - WP REST API bloqueada por BitNinja sin User-Agent de navegador.

## Limitaciones generales

- Certificado sede válido; no requiere `insecure_ssl`.
- Municipio turístico (~1.070 hab.); volumen bajo de publicaciones urbanísticas en web propia.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`).
- Diputación: planeamiento declarado como NUM (Normas Urbanísticas Municipales).
