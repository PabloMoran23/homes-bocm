# Castrillo del Val — investigación portal ayuntamiento

**Municipio:** Castrillo del Val (`castrillo-del-val`)  
**Comunidad:** Castilla y León (`castilla-y-leon`)  
**Provincia:** Burgos (INE `09086`)  
**Boletín:** BOCYL (`bocyl`, 1 entrada histórica)

## URLs base y páginas semilla

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Web municipal | https://www.castrillodelval.es | Drupal Toools (Dip. Burgos) | Noticias, normativa |
| Noticias | https://www.castrillodelval.es/noticias | HTML | Sin anuncios urbanísticos recientes |
| Sede electrónica | https://castrillodelval.sedelectronica.es | espublico gestiona | Tablón, transparencia, trámites |
| Tablón anuncios | `/board` | HTML tabla + `preview-document` | Modificación NNSS 4/2026, ordenanza fiscal construcciones |
| Portal transparencia | `/transparency` | Wicket | Sección 7 Urbanismo con 0 documentos |
| PlanPublica CyL | `servicios.jcyl.es/PlanPublica` (prov=9, mun=086) | JSP | NNSS, planes parciales históricos |
| IDECyL WFS | `idecyl.jcyl.es/geoserver/urbanismo/ows` | GeoJSON WFS | Instrumentos, PP y sectores |

## Cómo se listan expedientes

- **Tablón `/board`:** tabla HTML con columnas documento, expediente, procedimiento, categoría, descripción, fecha. Enlaces `preview-document/{uuid}`.
- **PlanPublica:** listado JSP de instrumentos de planeamiento (NNSS, PP) aprobados y en información pública.
- **IDECyL WFS:** 1 instrumento (NNSS), 3 planes parciales, 7 sectores con geometría en EPSG:4326.

## Cómo se publican licencias

- No hay listado tabular dedicado de licencias concedidas.
- Ordenanza fiscal reguladora del impuesto sobre construcciones (exp. 136/2026) publicada en tablón.
- Trámites de licencia urbanística vía sede (`/info`, `/dossier`) sin catálogo accesible públicamente.
- Adapter incluye ordenanza fiscal como referencia de construcciones/obras.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (3), `plau_cyl_sectores` (7)
  - Filtro: `CQL_FILTER=c_mun='09086'` (`srsName=EPSG:4326`)
- **Estrategia:** ingestión directa de features WFS con `geom_geojson`; enriquecimiento heurístico de tablón por coincidencia de título.
- **Limitaciones:** WFS cubre planeamiento histórico (NNSS, PP Los Tomillares), no licencias puntuales ni expedientes de tablón sin sector asociado. Sin visor municipal ArcGIS. Transparencia urbanismo vacía.

## Limitaciones

- Transparencia sección 7 (Urbanismo) sin documentos publicados.
- Noticias Drupal sin contenido urbanístico reciente.
- Licencias solo vía trámites informativos en sede, no dataset tabular.
- Sede puede requerir `insecure_ssl` en algunos entornos.

## Referencia de implementación

Patrón espublico tablón + IDECyL WFS: `municipio/adapters/arcos_de_la_llana.py`  
Drupal Toools Burgos: app Mi Pueblo / Diputación de Burgos
