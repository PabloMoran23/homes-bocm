# Los Llanos de Aridane — investigación portal ayuntamiento

Municipio: **Los Llanos de Aridane** (`los-llanos-de-aridane`)  
Provincia: Los Llanos de Aridane, La Palma · CCAA: Canarias  
Código INE municipio (Grafcan): `38024`

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (no operativa) | https://www.losllanosdearidane.com | Dominio parking GoDaddy; sin contenido municipal |
| Sede electrónica (espublico) | https://losllanosdearidane.sedelectronica.es/ | Página «Sede Electrónica Indeterminada»; `/board` y `/transparency` sin tablón real |
| SITCAN Open Data | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-los-llanos-de-aridane | 73 recursos de planeamiento (SIPU/PDF/HTML) |
| GEOBDP Grafcan | https://geobdp.grafcan.es/core/municipios/38024/ | Visor BDP con 22 instrumentos y polígonos |
| IDE Canarias | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/LlAr/ | PDFs e índices de planeamiento (LlAr) |

## Cómo se listan expedientes / proyectos

- **SITCAN / IDE Canarias:** catálogo CKAN con 73 recursos de planeamiento (PGO 1988, modificaciones puntuales, planes parciales, estudios de detalle, sentencia TS 2015, ordenanzas post-erupción volcánica 2022). Metadatos vía API `package_show`; enlaces HTML a `geobdp.grafcan.es` e `idecanarias.es`.
- **GEOBDP:** cada documento de planeamiento incluye capas «ámbito de ordenación» con GeoJSON embebido en `App.Map.zoomToExtent` (EPSG:32628).
- **Web municipal:** no accesible; no hay WordPress/Drupal ni visor de expedientes en curso.
- **Sede espublico:** sin tablón de anuncios ni dataset JSON de expedientes urbanísticos.

## Cómo se publican licencias

- **No hay** listado público de licencias de obra concedidas (decretos, tablón con coords).
- Sede electrónica indeterminada; no catálogo de trámites scrapeable.
- El adapter devuelve filas informativas de sede, SITCAN y GEOBDP; licencias reales publicadas = 0.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP: `https://geobdp.grafcan.es/core/documentos/<id>/` — GeoJSON MultiPolygon en JS (`EPSG:32628`)
  - IDE Canarias WMS planeamiento vigente: `https://idecan2.grafcan.es/ServicioWMS/Planeamiento`
  - Visor Grafcan: `https://visor.grafcan.es/visorweb/`
- **Estrategia:** para recursos SITCAN con enlace GEOBDP (23 de 73), el adapter descarga la página del documento, extrae `App.Map.zoomToExtent`, reproyecta a WGS84 y rellena `geom_geojson`. Catálogo GEOBDP municipal como respaldo (22 documentos).
- **Limitaciones:** sin WFS público consultable por código de expediente; geometría solo a nivel de instrumento de planeamiento (ámbito PGO/PP/ED), no licencias ni expedientes administrativos individuales. Web municipal y sede inaccesibles para scrape adicional.

## Limitaciones generales

- Dominios `.com`/`.es` del ayuntamiento en parking; sin portal corporativo operativo.
- Sede espublico genérica sin contenido urbanístico.
- Sin re-parse BOC Canarias; 1 entrada en `boc_canarias` ya en `projects.json`.
- Post-erupción volcánica La Palma 2021: ordenanzas municipales de urbanización viviendas afectadas (2022) en SITCAN/GEOBDP.
