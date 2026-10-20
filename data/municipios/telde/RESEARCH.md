# Telde — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.telde.es |
| Urbanismo | https://www.telde.es/areas/urbanismo/ |
| Información pública | https://www.telde.es/areas/urbanismo/informacion-publica/ |
| Transparencia (obras y urbanismo) | https://www.telde.es/transparencia/obras-publicas-y-urbanismo/ |
| Trámites presenciales urbanismo | https://www.telde.es/tramites-presenciales/urbanismo/ |
| Sede electrónica (espublico gestiona) | https://telde.sedelectronica.es |
| Tablón de anuncios | https://telde.sedelectronica.es/board |
| Catálogo trámites | https://telde.sedelectronica.es/dossier |
| SITCAN Open Data | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-telde |
| GeoBDP municipio (INE 35026) | https://geobdp.grafcan.es/core/municipios/35026/ |
| Visor IDECanarias (planeamiento) | https://visor.grafcan.es/visorweb/default.php?svc=svcPlaDef |

## Proyectos / expedientes

- **WordPress:** la sección de información pública enlaza PDFs históricos (`wp-content/uploads/...`) de exposiciones públicas, revisiones del PGO y proyectos sectoriales.
- **SITCAN CKAN:** API `package_show` del dataset `planeamiento-urbanistico-de-telde` — recursos HTML/PDF/SIPU por instrumento (modificaciones puntuales del PGO, etc.).
- **Tablón sede:** tabla HTML pública en `/board` con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces `preview-document/{uuid}` (Wicket/espublico). Filas con categoría **Urbanismo** o procedimiento de planeamiento.
- **Transparencia:** enlaces al PGO y revisiones parciales (documentos estáticos).

No hay listado público de expedientes urbanísticos individuales con login; la consulta de expedientes en sede requiere certificado (`/expedientes`).

## Licencias

- **Tablón:** anuncios de licencias de obra, comunicaciones previas y actuaciones urbanísticas cuando se publican en el tablón (categoría Urbanismo / procedimientos de licencia).
- **Catálogo `/dossier`:** páginas informativas de trámites (Licencia de Obra Mayor/Menor, Comunicación Previa de Ejecución de Obras, etc.) — no lista concesiones históricas con coordenadas.
- No hay dataset abierto de licencias concedidas con georreferencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GeoBDP GRAFCAN: `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos de ámbitos de instrumentos de planeamiento sistematizado (SIPU), embebidos en `App.Map.zoomToExtent` (EPSG:32628 UTM 28N → reproject WGS84 en adapter).
  - Índice por municipio: `https://geobdp.grafcan.es/core/municipios/35026/`
  - Visor regional IDECanarias `svcPlaDef` (capas clasificación/zonificación) — sin enlace directo a expediente municipal.
- **Estrategia:** emparejar título de recurso SITCAN/CKAN o enlace GeoBDP con documento en GeoBDP; extraer primer feature del GeoJSON embebido.
- **Limitaciones:** geometría solo para **instrumentos de planeamiento** (PGO, modificaciones puntuales), no para licencias de obra ni expedientes del tablón. Licencias sin GIS enlazable → centroide municipio + jitter en orquestador.

## Limitaciones técnicas

- Tablón paginado (Wicket); primera página scrapeada en backfill.
- `/dossier` puede tardar >30s en responder.
- PDFs en WordPress sin metadatos estructurados (solo nombre de fichero y contexto de página).
- Expedientes en sede requieren autenticación.
