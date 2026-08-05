# Collado Mediano — investigación portal ayuntamiento

## Resumen

Municipio de la Comunidad de Madrid (Sierra de Guadarrama). Web corporativa en **Joomla**
(`https://www.aytocolladomediano.es`) y **sede electrónica eHome/espublico**
(`https://aytocolladomediano.sedelectronica.es`).

Dominio alternativo `www.colladomediano.es` presenta **certificado SSL inválido**
(hostname mismatch); se usa `aytocolladomediano.es` como base oficial.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa | https://www.aytocolladomediano.es |
| Urbanismo | https://www.aytocolladomediano.es/areas-municipales/urbanismo-obras-y-vivienda |
| PGOU | https://www.aytocolladomediano.es/areas-municipales/urbanismo-obras-y-vivienda/pgou |
| Licencias de obra | https://www.aytocolladomediano.es/areas-municipales/urbanismo-obras-y-vivienda/licencias/licencias-de-obra |
| Licencias de actividad | https://www.aytocolladomediano.es/areas-municipales/urbanismo-obras-y-vivienda/licencias/licencias-de-actividad |
| Consultas urbanismo | https://www.aytocolladomediano.es/tramites/consultas-urbanismo |
| Tablón sede | https://aytocolladomediano.sedelectronica.es/board |
| Transparencia sede | https://aytocolladomediano.sedelectronica.es/transparency/ |

## Proyectos / expedientes

- **PGOU:** ~90 PDFs en la sección PGOU (textos, anexos, certificados). Se filtran planos
  técnicos repetitivos (clasificación, infraestructuras) y se conservan memorias, normas,
  resúmenes ejecutivos, anexos ambientales y certificados.
- **Tablón sede:** HTML con filas `data-label` + enlaces `preview-document/{uuid}`.
  ~10 anuncios visibles sin paginación. Pocos relacionados con urbanismo en el momento
  de la investigación (p. ej. exposición pública plan de residuos, anuncios BOCM).
- **Búsqueda Joomla:** endpoint `com_search` devuelve HTTP 500; no usable.
- No hay visor urbanístico propio del ayuntamiento ni listado de expedientes IP en la web.

## Licencias

- No hay dataset público de concesiones con coordenadas.
- Páginas de trámites con **modelos PDF** (solicitud, declaración responsable, hojas de
  características de actividad).
- Tablón sede puede publicar licencias puntuales bajo categoría/procedimiento urbanístico.
- Se incluyen páginas informativas de referencia (como Pozuelo/Guadarrama).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `sitcm:VPLA_V_AMBITO`
  - Endpoint: `https://idem.comunidad.madrid/geoserver3/ows`
  - Filtro: `DS_MUNICIPIO='COLLADO MEDIANO'`
  - 13 ámbitos SAU (p. ej. `SAU-1 CERRO CASTILLO 1`, `SAU-12 INDUSTRIAL`, `SAU-7 LA DEHESILLA 1`)
- **Estrategia:** Tras extraer metadatos, `_fetch_geometry()` consulta SITCM por códigos
  en el título y por mapa de palabras clave → ámbito (`AMBITO_KEYWORDS`). GeoJSON WGS84
  en `geom_geojson` con `geometry_source: portal_wfs`.
- **Limitaciones:**
  - Sin visor ArcGIS/WFS propio del ayuntamiento enlazado a expedientes.
  - PDFs del PGOU no llevan georreferencia directa; geometría solo cuando el título
    menciona un ámbito SAU reconocible.
  - Fotovoltaicas u obras puntuales sin código de ámbito → sin polígono (centroide+jitter).

## Limitaciones generales

- Tablón sede sin paginación (~10 filas).
- `www.colladomediano.es` con certificado SSL incorrecto (no usado).
- Búsqueda interna Joomla inoperativa (500).
- Sin datos abiertos de licencias con coordenadas.
