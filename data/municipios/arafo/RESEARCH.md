# Arafo — investigación portal ayuntamiento

Municipio: **Arafo** (`arafo`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (1 aviso). INE: 38004.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal corporativo (WebSite X5) | https://www.arafo.es |
| Urbanismo, Obras y Vías Públicas | https://www.arafo.es/urbanismo,-obras-y-vias-publicas.html |
| Tablón electrónico de edictos (web) | https://www.arafo.es/tablon-electronico-de-edictos.html |
| Portal de transparencia (web) | https://www.arafo.es/portal-de-transparencia.html |
| Sede electrónica (espublico gestiona) | https://arafo.sedelectronica.es |
| Tablón de anuncios sede | https://arafo.sedelectronica.es/board/ |
| Transparencia sede | https://arafo.sedelectronica.es/transparency |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-arafo |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38004/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Araf/ |

## Cómo se listan expedientes / planeamiento

- **CMS corporativo:** Incomedia WebSite X5; la sección urbanismo describe funciones de la Oficina Técnica (licencias, planeamiento, PIC) sin listado de expedientes abiertos.
- **Sede espublico gestiona:** tablón `/board/` con tabla HTML (`data-label`: Expediente, Procedimiento, Descripción, Fecha de Publicación). Anuncios recientes (~10 filas visibles).
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-arafo` con 32 recursos (8 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP/ZIP).
- **GEOBDP Grafcan:** 10 documentos de planeamiento con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Trámites sede `/dossier`:** catálogo lento en CI; no usado directamente en el adapter.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- El tablón sede publica anuncios genéricos (JGL, subvenciones, etc.); licencias urbanísticas aparecen esporádicamente.
- Trámites de licencia vía sede electrónica; el adapter incluye páginas informativas (tablón + urbanismo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (10 instrumentos, todos con geometría)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio (INE 38004); emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP; tablón sede y web corporativa sin geometría enlazable por expediente; licencias sin georreferencia.

## Limitaciones generales

- Tablón sede sin histórico completo ni filtro server-side por categoría.
- Web corporativa estática (WebSite X5) sin visor urbanístico propio.
- Sin listado abierto de licencias concedidas.
