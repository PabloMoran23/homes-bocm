# Güímar — investigación portal ayuntamiento

Municipio: **Güímar** (`guimar`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (2 avisos BOCM). INE: 38020.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (Drupal 9 + Gavias Elix) | https://www.guimar.es |
| Ordenación del territorio (PGO, planos, catálogo) | https://www.guimar.es/ordenacion-del-territorio |
| Modelos de solicitud (licencias obra) | https://www.guimar.es/modelos-de-solicitud |
| Sede electrónica (espublico) | https://guimar.sedelectronica.es |
| Tablón de anuncios | https://guimar.sedelectronica.es/board |
| Portal transparencia sede | https://guimar.sedelectronica.es/transparency |
| Sede tributos (guimar.gob.es) | https://sede.guimar.gob.es |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-guimar |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38020/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** Drupal 9 (`www.guimar.es`, tema Gavias Elix).
- **Ordenación del territorio:** página estática con enlaces a Google Drive (normativa PGO, planos estructurales/pormenorizados, catálogo elementos protegidos, ordenanzas edificación).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-guimar` con **49 recursos** (13 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP).
- **GEOBDP:** 13 documentos con visor OpenLayers y botón «Localizar» (`findRecintoByDocumento`); geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Tablón sede:** tabla HTML espublico/Wicket con columnas Descripción, Expediente, Procedimiento, Categoría, Fecha de Publicación; mayoría de anuncios son tráfico/sanciones, ocasionalmente edictos rústica/urbana.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Modelos PDF en `/modelos-de-solicitud` (licencia obra mayor/menor, segregación — enlaces archive.org).
- Trámites vía sede electrónica; el adapter incluye páginas informativas (tablón + modelos + ordenación).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio (INE 38020); para cada recurso SITCAN emparejar por título normalizado y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (~13 polígonos); planos en Google Drive sin georreferencia; tablón y modelos sin geometría enlazable.

## Limitaciones generales

- Planos PGO alojados en Google Drive (no scrapeables como geometría).
- Sin tablón de licencias concedidas en abierto con coordenadas.
- Tablón sede mezcla trámites no urbanísticos — filtro por keywords RE_LICENCIA/RE_PROYECTO.
