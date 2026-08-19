# Arcos de la Llana — investigación portal ayuntamiento

**Municipio:** Arcos de la Llana (`arcos-de-la-llana`)  
**Comunidad:** Castilla y León (`castilla-y-leon`)  
**Provincia:** Burgos (INE `09023`)  
**Boletín:** BOCYL (`bocyl`, 3 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Web municipal | https://www.arcosdelallana.es | Drupal 10 | Noticias de expedientes/licencias |
| Noticias | https://www.arcosdelallana.es/noticias | HTML | Anuncios urbanismo y licencias (enlaces a transparencia) |
| Sede electrónica | https://arcosdelallana.sedelectronica.es | espublico gestiona | Tablón, transparencia, trámites |
| Tablón anuncios | `/board` | HTML tabla + `preview-document` | Planeamiento, actuaciones urbanísticas |
| Portal transparencia | `/transparency` | Wicket + carpetas UUID | Documentos urbanismo (15 en sección 7) |
| Trámites | `/dossier` | espublico catálogo | **Timeout** (>60s) — no usado |
| PlanPublica CyL | `servicios.jcyl.es/PlanPublica` | JSP | Enlace en web; sin resultados con `cMunicipio=09023` |

## Cómo se listan expedientes

- **Tablón `/board`:** tabla HTML con columnas documento, expediente, procedimiento, categoría, descripción, fecha. Enlaces `preview-document/{uuid}`.
- **Transparencia:** carpetas anidadas bajo `/transparency/{uuid}/` con tabla de PDFs (p. ej. modificación puntual NUM 307/2026).
- **Noticias Drupal:** artículos con título, fecha y enlaces a carpetas de transparencia (licencias fibra óptica, modificación NUM).
- **IDECyL WFS:** instrumentos, planes parciales y sectores del municipio (`c_mun=09023`, nombre corto `Arcos`).

## Cómo se publican licencias

- No hay listado tabular dedicado de licencias concedidas.
- Licencias urbanísticas publicadas como **noticias** (Expdte. 287/2025 LIC. URB. 11/25, 333/2025 LIC. URB. 12/25) con documentación en transparencia.
- Tablón actual sin filas de licencia explícita; adapter incluye noticias y documentos transparencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (2), `plau_cyl_sectores` (15)
  - Filtro: `CQL_FILTER=c_mun='09023'` (`srsName=EPSG:4326`)
- **Estrategia:** ingestión directa de features WFS con `geom_geojson`; enriquecimiento heurístico de tablón/noticias por coincidencia de título.
- **Limitaciones:** WFS cubre planeamiento histórico (PP 2007), no licencias puntuales ni expedientes de tablón sin sector asociado. Sin visor municipal ArcGIS. `/dossier` no responde en CI.

## Limitaciones

- Catálogo de trámites `/dossier` inaccesible (timeout repetido).
- Transparencia sección 7 requiere navegación por UUID; no hay API JSON.
- Licencias solo vía noticias + PDFs transparencia, no dataset tabular.
- Sede requiere `insecure_ssl` en algunos entornos.

## Referencia de implementación

Patrón espublico tablón: `municipio/adapters/pelabravo.py`  
IDECyL WFS: `municipio/adapters/candeleda.py`, `laguna_de_duero.py`
