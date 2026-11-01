# Puntallana — investigación portal ayuntamiento

Municipio: **Puntallana** (`puntallana`) — Canarias, provincia Santa Cruz de Tenerife (La Palma). Boletín: `boc_canarias` (1 aviso BOCM). INE: 38030.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress) | https://puntallana.es |
| Oficina Virtual / Técnica | https://puntallana.es/category/oficina-virtual/oficina-tecnica/ |
| Sede electrónica (espublico gestiona) | https://puntallana.sedelectronica.es |
| Tablón de anuncios | https://puntallana.sedelectronica.es/board |
| Transparencia | https://puntallana.sedelectronica.es/transparency |
| Catálogo de trámites | https://puntallana.sedelectronica.es/dossier.0 |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-puntallana |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38030/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress en `puntallana.es` con sección «Oficina Virtual» (modelos y guías de licencias urbanísticas, obras de urbanización, etc.).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-puntallana` con **6 recursos** (2 instrumentos: adaptación parcial PGOU 2005 y aprobación definitiva PGO 2019; formatos SIPU/PDF/HTML).
- **GEOBDP:** al menos el documento **1264** (PGO aprobación definitiva 2019) con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Sede tablón:** HTML scrapeable (`/board`) con filas `data-label` (Descripción, Expediente, Fecha de Publicación, …); incluye edictos y expedientes de rectificación catastral/urbanística mezclados con otros anuncios.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Trámites en sede: «Solicitud de Licencia o Autorización Urbanística», «Solicitud de Actuación Urbanística», etc. (catálogo `/dossier.0`, sección Urbanismo y Vivienda).
- Oficina Técnica publica requisitos y modelos en la web municipal.
- El adapter incluye páginas informativas (tablón, oficina técnica, catálogo de trámites) y extrae del tablón filas que coinciden con keywords de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza instrumentos de planeamiento (HTML/GEOBDP)
- **Estrategia:** indexar documentos GEOBDP del municipio; emparejar recursos SITCAN por título normalizado; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (~1–2 polígonos municipales); tablón y licencias sin geometría enlazable; noticias WP sin visor SIG.

## Limitaciones generales

- Tablón mezcla urbanismo con censos electorales y catastro — filtro por regex.
- Sin visor urbanístico municipal propio; dependencia de GEOBDP regional.
- Licencias concedidas no publicadas en abierto con coords.
