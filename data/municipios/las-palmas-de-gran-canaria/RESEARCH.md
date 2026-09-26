# Las Palmas de Gran Canaria — investigación portal ayuntamiento

Municipio: **Las Palmas de Gran Canaria** (`las-palmas-de-gran-canaria`) — Canarias, provincia Las Palmas (capital). Boletín: `boc_canarias` (3 avisos). INE: 35016.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal corporativo (SagaSuite) | https://www.laspalmasgc.es |
| Sede electrónica | https://www.laspalmasgc.es/es/online/sede-electronica/ |
| Tablón de anuncios (e-civilis) | http://sedeelectronica.laspalmasgc.es/tablonedictos/bulletinBoard/bulletins |
| Planificación urbanística | https://www.laspalmasgc.es/es/areas-tematicas/urbanismo-e-infraestructuras/planificacion-urbanistica/ |
| Información pública | https://www.laspalmasgc.es/es/areas-tematicas/urbanismo-e-infraestructuras/informacion-publica/ |
| Gestión del suelo | https://www.laspalmasgc.es/es/areas-tematicas/urbanismo-e-infraestructuras/gestion-del-suelo/ |
| Proyectos y obras | https://www.laspalmasgc.es/es/areas-tematicas/urbanismo-e-infraestructuras/proyectos-y-obras/ |
| Visores geográficos | https://www.laspalmasgc.es/es/areas-tematicas/innovacion/visores-geograficos-municipales/ |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-las-palmas-de-gran-canaria |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35016/ |
| IDECanarias | https://www.idecanarias.es/content/idecanarias |

## Cómo se listan expedientes / planeamiento

- **CMS SagaSuite:** secciones de urbanismo con acordeones de planes en vigor, tramitación e información pública; PDFs en galerías `/export/sites/laspalmasgc/.galleries/documentos-urbanismo/`.
- **Sede e-civilis:** tablón HTML paginado (`?s=1,6,11…`, 5 edictos/página); detalle en `showBulletin/{id}:1` con PDF adjunto; etiqueta `Urbanismo` (tagId=21) en formulario POST (filtro no fiable sin sesión).
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-las-palmas-de-gran-canaria` con ~127 recursos (~40 instrumentos únicos × enlaces SIPU/FIP/PDF/HTML/GEOBDP).
- **GEOBDP Grafcan:** 41 documentos con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- El tablón publica edictos genéricos (RRHH, notarías, limpieza); licencias urbanísticas aparecen esporádicamente bajo etiqueta Urbanismo.
- Trámites de licencia vía ventanilla virtual Cl@ve en sede electrónica; el adapter incluye páginas informativas (tablón + sede).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (~41 instrumentos)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - Visor urbanístico municipal (`laspalmasgc.es` → Visores geográficos) **no disponible** (en actualización, agosto 2026)
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio; emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP; PDFs del portal y edictos del tablón sin geometría enlazable; visor municipal caído; sede en HTTP (sin SSL).

## Limitaciones generales

- Sede electrónica (`sedeelectronica.laspalmasgc.es`) sirve en HTTP; `insecure_ssl: true` por compatibilidad.
- Tablón sin API JSON; paginación HTML hasta ~17 edictos visibles (histórico limitado).
- Sin listado abierto de licencias concedidas con coordenadas.
- Visor urbanístico propio en mantenimiento.
