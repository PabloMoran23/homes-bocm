# Agüimes — investigación portal ayuntamiento

Municipio: **Agüimes** (`aguimes`) — Canarias, provincia Las Palmas (Gran Canaria). Boletín: `boc_canarias` (1 aviso). INE: 35002.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal corporativo | https://aguimes.es |
| Urbanismo | https://aguimes.es/urbanismo/ |
| Transparencia — PMO / PGOU | https://aguimes.es/transparencia-informacion-del-plan-municipal-de-ordenacion/ |
| Transparencia — planes y proyectos de desarrollo | https://aguimes.es/transparencia-informacion-de-los-planes-y-proyectos-de-desarrollo-del-plan-municipal-de-ordenacion/ |
| Modificación menor nº1 PGO | https://aguimes.es/modificacion-menor-no1-pgo/ |
| Plan especial Puerto de Arinaga | https://aguimes.es/plan-especial-de-ordenacion-de-la-zona-de-servicio-del-puerto-de-arinaga/ |
| Ordenanza sector P3 Norte Arinaga | https://aguimes.es/ordenanza-provisional-para-ordenacion-de-parcela-en-el-sector-p3-norte-del-poligono-industrial-arinaga/ |
| Sede electrónica (espublico gestiona) | https://aguimes.sedelectronica.es |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-aguimes |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35002/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/Agui/ |

## Cómo se listan expedientes / planeamiento

- **CMS corporativo:** WordPress (X Theme / Cornerstone) con sección `/urbanismo/` enlazando a transparencia del PGOU, modificaciones y planes especiales. La página de transparencia PMO publica decenas de PDFs (memoria, planeamiento vigente, sectores Arinaga, Temisas, etc.).
- **Sede espublico gestiona:** `aguimes.sedelectronica.es` redirige con token de sesión; el tablón `/board` devuelve «Sede Electrónica Indeterminada» sin selección de municipio — no scrapeable en CI.
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-aguimes` con 5 instrumentos de planeamiento (15 recursos: CKAN, IDECanarias, GEOBDP).
- **GEOBDP Grafcan:** 5 documentos con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Trámites vía sede electrónica y página `/tramites/`; el adapter incluye páginas informativas (sede, urbanismo, trámites).
- Noticias municipales sobre licencias/urbanismo se descubren vía sitemap WP cuando contienen palabras clave.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (5 instrumentos: 655, 1161, 1182, 1257, 1349)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio; emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (5/5 con polígono en SITCAN); PDFs del portal WordPress sin geometría enlazable; tablón sede inaccesible; licencias sin georreferencia.

## Limitaciones generales

- Tablón sede espublico no accesible programáticamente (página «Sede Electrónica Indeterminada»).
- Sin listado abierto de licencias concedidas con coordenadas.
- Muchas noticias WP con «arinaga»/«urban» son ruido (eventos, deportes) — filtradas por regex de planeamiento.
