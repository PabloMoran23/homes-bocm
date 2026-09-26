# El Rosario — investigación portal ayuntamiento

Municipio: **El Rosario** (`el-rosario`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (2 avisos BOCM). INE: 38028.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress) | https://www.ayuntamientoelrosario.org |
| Planeamiento / normativa | https://www.ayuntamientoelrosario.org/index.php/planeamiento/ |
| Sede electrónica (espublico gestiona) | https://elrosario.sedelectronica.es |
| Tablón de anuncios | https://elrosario.sedelectronica.es/board |
| Catálogo trámites | https://elrosario.sedelectronica.es/dossier |
| Transparencia sede | https://elrosario.sedelectronica.es/transparency |
| IVO (informes urbanísticos) | https://www.ayuntamientoelrosario.org/index.php/informacion-orientacion-y-valoracion-ivo/ |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-el-rosario |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38028/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Rosa/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress (`ayuntamientoelrosario.org`) con página `/planeamiento/` estructurada en secciones `<h3>` (NNSS, estudios de detalle, PAMU, modificaciones, PERI Radazul, etc.) y enlaces a PDFs en `wp-content/uploads/`.
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-el-rosario` con **47 recursos** (~16 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP).
- **GEOBDP:** documentos con visor OpenLayers; geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Sede espublico gestiona:** tablón `/board` con tabla HTML (clases `class_name`, `class_folderCode`, etc.) y enlaces `preview-document/{uuid}`; sin API REST pública.
- **Plan General:** declarado nulo por Sentencia TS 11-nov-2014; vigentes las Normas Subsidiarias.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Tablón sede con anuncios administrativos (vados, obras infraestructura); pocas licencias urbanísticas publicadas.
- Trámites vía sede electrónica (`/dossier`); el adapter incluye páginas informativas (tablón + catálogo + IVO).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es/ServicioWMS/Planeamiento`) sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio (INE 38028); para cada recurso SITCAN emparejar por título normalizado y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP; estudios de detalle recientes (PDFs WP) sin geometría vectorial enlazable; licencias sin coords.

## Limitaciones generales

- Sin listado histórico de licencias concedidas en abierto.
- Tablón sede mezcla anuncios administrativos (padrón, personal) con urbanismo — filtro por keywords.
- Sin re-parse BOCM; 2 entradas en `boc_canarias` ya en `projects.json`.
