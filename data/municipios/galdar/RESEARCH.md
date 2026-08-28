# Gáldar — investigación portal ayuntamiento

Municipio: **Gáldar** (`galdar`) — Canarias, provincia Las Palmas (Gran Canaria). Boletín: `boc_canarias` (2 avisos). INE: 38009.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal WordPress | https://www.galdar.es |
| Urbanismo | https://www.galdar.es/urbanismo/ |
| Plan General de Ordenación (PGO) | https://www.galdar.es/pgo/ |
| Sede electrónica (espublico gestiona) | https://galdar.sedelectronica.es |
| Tablón de anuncios | https://galdar.sedelectronica.es/board |
| Portal transparencia sede | https://galdar.sedelectronica.es/transparency |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-galdar |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38009/ |

## Cómo se listan expedientes / planeamiento

- **CMS WordPress:** sitio oficial con secciones `/urbanismo/` (competencias, trámites) y `/pgo/` (PGO con decenas de PDFs de ordenanzas, planos operativos, modificaciones puntuales). REST API en `/wp-json/`.
- **Sede espublico gestiona:** tablón `/board` con tabla HTML (`data-label` por columna: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha). ~10 anuncios recientes; actualmente publica modificación menor del PGO (exp. 18699/2018).
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-galdar` con 87 recursos (~29 instrumentos únicos × enlaces GEOBDP/IDECanarias/ZIP).
- **GEOBDP Grafcan:** 4 documentos con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- La página `/urbanismo/` lista tipos de licencias (obra mayor/menor, segregación, etc.) como trámites, no como concesiones publicadas.
- El tablón sede publica anuncios de planeamiento; licencias urbanísticas aparecen esporádicamente.
- El adapter incluye páginas informativas (tablón + urbanismo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (4 instrumentos: estudio de detalle, texto refundido PGO, modificación puntual SUSO ZOR1)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
- **Estrategia:** indexar documentos GEOBDP del municipio; emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (4/4 con polígono); PDFs del portal WordPress (/pgo/) y tablón sin geometría enlazable; sin listado abierto de licencias con coords.

## Limitaciones generales

- Tablón sede sin histórico completo ni filtro server-side por categoría.
- Sin listado abierto de licencias concedidas.
- PGO publica muchos PDFs históricos sin metadatos estructurados (solo enlaces HTML).
