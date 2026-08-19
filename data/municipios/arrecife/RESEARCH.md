# Arrecife — investigación portal ayuntamiento

Municipio: **Arrecife** (`arrecife`) — Canarias, provincia Las Palmas (capital de Lanzarote). Boletín: `boc_canarias` (3 avisos). INE: 35004.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal corporativo | https://www.arrecife.es |
| Transparencia — ordenación del territorio | https://www.arrecife.es/node/199 |
| Portal transparencia índice | https://www.arrecife.es/transparencia |
| Sede electrónica (espublico gestiona) | https://arrecife.sedelectronica.es |
| Tablón de anuncios | https://arrecife.sedelectronica.es/board |
| Portal transparencia sede (legacy) | https://arrecife.sedelectronica.es/transparency |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-arrecife |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35004/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LZ/Arre/ |

## Cómo se listan expedientes / planeamiento

- **CMS corporativo:** sitio propio (Metronic/Bootstrap) con sección transparencia; `/node/199` publica PGOU 2004, planos OR-06, modificaciones de planeamiento y enlaces a SITCAN (28 PDFs).
- **Sede espublico gestiona:** tablón `/board` con tabla HTML (`data-label` por columna: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha). Solo ~10 anuncios recientes visibles sin paginación AJAX accesible.
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-arrecife` con 27 recursos (7 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP/ZIP).
- **GEOBDP Grafcan:** 7 documentos con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Trámites sede `/dossier`:** redirección a URL `.0` provoca bucle en CI; no usado en el adapter.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- El tablón sede publica anuncios genéricos (padrón, empleo, subvenciones); licencias urbanísticas aparecen esporádicamente.
- Trámites de licencia vía sede electrónica (`/dossier`); el adapter incluye páginas informativas (tablón + transparencia ordenación).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (7 instrumentos)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio; emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (7/7 con polígono); PDFs del portal corporativo y tablón sin geometría enlazable; `/dossier` inaccesible por redirect loop; certificado SSL inválido en `www.arrecife.es`.

## Limitaciones generales

- Certificado SSL de `www.arrecife.es` inválido — requiere `insecure_ssl: true`.
- Tablón sede sin histórico completo ni filtro server-side por categoría.
- Sin listado abierto de licencias concedidas.
