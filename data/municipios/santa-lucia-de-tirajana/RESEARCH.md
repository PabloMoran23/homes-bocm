# Santa Lucía de Tirajana — investigación portal ayuntamiento

Municipio: **Santa Lucía de Tirajana** (`santa-lucia-de-tirajana`) — Canarias, provincia Las Palmas (Gran Canaria). Boletín: `boc_canarias` (1 aviso BOCM). INE: 35022.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Sede electrónica (espublico gestiona) | https://santaluciadetirajana.sedelectronica.es |
| Tablón de anuncios | https://santaluciadetirajana.sedelectronica.es/board |
| Portal transparencia sede | https://santaluciadetirajana.sedelectronica.es/transparency |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-santa-lucia-de-tirajana |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/35022/ |
| IDECanarias PGO (índice texto refundido) | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/GC/SLuc/719/indice.html |
| Licencia obra (CCAA, informativo) | https://sede.gobiernodecanarias.org/sede/tramites/1186 |

**Nota:** `www.santaluciadetirajana.es` no resolvió DNS desde el entorno del agente (oct-2026). Otros municipios de Gran Canaria suelen usar WordPress corporativo; aquí la sede espublico es la fuente municipal accesible.

## Cómo se listan expedientes / planeamiento

- **Sede espublico gestiona:** tablón `/board` con tabla HTML (`data-label`: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha). En la muestra consultada (oct-2026) solo categorías *Anuncios* y *Empleo Público* (sin filas urbanísticas recientes).
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-santa-lucia-de-tirajana` con 37 recursos (~10 instrumentos de planeamiento con enlaces GEOBDP, IDECanarias y ZIP SIPU).
- **GEOBDP Grafcan:** 9 documentos con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **IDECanarias:** índices HTML estáticos por instrumento (`/URB_PLA/GC/SLuc/...`) con enlaces a documentación aprobada.

## Licencias de obra

- **Sin dataset** público municipal de licencias concedidas con dirección/coordenadas.
- El tablón sede no publicaba licencias urbanísticas en la fecha de investigación.
- Trámite informativo CCAA (licencia de obra) enlazado en el adapter; no sustituye concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (9 instrumentos: texto refundido PGO, modificaciones puntuales, PE SGEL, sentencias, adaptación Ley 4/17, etc.)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
- **Estrategia:** indexar documentos GEOBDP del municipio; emparejar por título normalizado con recursos SITCAN; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP; tablón sede y licencias sin geometría enlazable; portal corporativo www no accesible en CI.

## Limitaciones generales

- Tablón sede sin histórico completo ni filtro por categoría urbanismo en la muestra actual.
- Sin listado abierto de licencias concedidas.
- Dependencia principal de fuentes autonómicas (SITCAN/GEOBDP) para proyectos históricos de planeamiento.
