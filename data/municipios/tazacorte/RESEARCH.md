# Tazacorte — investigación portal ayuntamiento

Municipio: **Tazacorte** (`tazacorte`) — Canarias, provincia Santa Cruz de Tenerife (La Palma). Boletín: `boc_canarias` (2 avisos). INE: 38045.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal corporativo (WordPress Divi) | https://tazacorte.es/web |
| Ordenanzas y reglamentos | https://tazacorte.es/web/ordenanzas-y-reglamentos |
| Obras e infraestructuras | https://tazacorte.es/web/obras-e-infraestructuras |
| Sede electrónica (espublico gestiona) | https://tazacorte.sedelectronica.es |
| Tablón de anuncios | https://tazacorte.sedelectronica.es/board |
| Portal transparencia sede | https://tazacorte.sedelectronica.es/transparency |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-tazacorte |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38045/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/Taza/ |

## Cómo se listan expedientes / planeamiento

- **CMS corporativo:** WordPress Divi en `tazacorte.es/web` con páginas de áreas municipales (obras, ordenanzas). Sin sección urbanismo dedicada en el menú; delegación urbanística en órganos de gobierno.
- **Sede espublico gestiona:** tablón `/board` con tabla HTML (`data-label` por columna: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha). ~10 anuncios recientes (padrón, empleo, edictos); sin urbanismo en el tablón actual.
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-tazacorte` con 15 recursos (5 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP).
- **GEOBDP Grafcan:** 5 documentos con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Trámites sede `/dossier`:** timeout en CI; no usado en el adapter.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- El tablón sede publica anuncios genéricos (padrón, empleo, edictos); licencias urbanísticas aparecen esporádicamente.
- Trámites de licencia vía sede electrónica; el adapter incluye páginas informativas (tablón + ordenanzas + obras).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (5 instrumentos: PGO, PP Hoyo Verdugo, PP El Hornito, sentencia Los Tarajales, OMU erupción volcánica)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio; emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (5/5 con polígono); PDFs del portal WordPress y tablón sin geometría enlazable; `/dossier` inaccesible por timeout.

## Limitaciones generales

- Tablón sede sin histórico completo ni filtro server-side por categoría.
- Sin listado abierto de licencias concedidas.
- Web corporativa sin sección urbanismo explícita; planeamiento principalmente en SITCAN/GEOBDP regional.
