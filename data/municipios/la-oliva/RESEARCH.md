# La Oliva — investigación portal ayuntamiento

Municipio: **La Oliva** (`la-oliva`) — Canarias, provincia Las Palmas (Fuerteventura). Sin entradas BOCM en el índice actual. INE: **35018**.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal municipal | https://laoliva.es |
| Área Urbanismo (CMS) | https://laoliva.es/ayuntamiento/42 |
| Índice ayuntamiento | https://laoliva.es/ayuntamiento |
| Sede electrónica (espublico gestiona) | https://laoliva.sedelectronica.es |
| Tablón de anuncios | https://laoliva.sedelectronica.es/board |
| Portal transparencia sede | https://laoliva.sedelectronica.es/transparency |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-la-oliva |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35018/ |

## Cómo se listan expedientes / planeamiento

- **CMS laoliva.es:** secciones bajo `/ayuntamiento/{id}`; el área **Urbanismo** (`/ayuntamiento/42`) publica PDFs en `/descargas/archivos/*.pdf` (normas subsidiarias, informes, formularios). No hay API JSON ni listado de expedientes estructurado.
- **Sede espublico gestiona:** tablón `/board` con tabla HTML (`data-label`: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha). ~10 anuncios por página; mezcla administración general y urbanismo esporádico.
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-la-oliva` con ~45 recursos (modificaciones/revisiones de normas subsidiarias, enlaces a GEOBDP e IDECanarias).
- **GEOBDP Grafcan:** documentos con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N). El índice municipal incluye instrumentos de planeamiento (p. ej. documentos 1017–1019).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Urbanismo publica trámites y formularios PDF; no hay registro abierto de concesiones.
- El tablón sede puede publicar anuncios urbanísticos de forma puntual.
- El adapter incluye páginas informativas (tablón + área urbanismo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (~15 instrumentos enlazados desde SITCAN)
  - SITCAN enlaza cada instrumento de planeamiento a GEOBDP
- **Estrategia:** indexar documentos GEOBDP del municipio; emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84 en el adapter.
- **Limitaciones:** PDFs del portal CMS y anuncios del tablón sin geometría enlazable; sin visor ArcGIS municipal unificado; licencias sin georreferencia.

## Limitaciones generales

- Tablón sede sin histórico completo accesible por scraping (paginación Wicket/AJAX).
- CMS sin metadatos estructurados en PDFs (solo enlaces de descarga).
- Sin listado abierto de licencias concedidas.
