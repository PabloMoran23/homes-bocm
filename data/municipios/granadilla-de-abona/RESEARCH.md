# Granadilla de Abona — investigación portal ayuntamiento

Municipio: **Granadilla de Abona** (`granadilla-de-abona`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (5 avisos BOCM). INE: 38017.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress + Kadence) | https://www.granadilladeabona.org |
| Sede electrónica (enlace WP) | http://sede.granadilladeabona.es/ |
| Sede electrónica (página informativa) | https://www.granadilladeabona.org/sede-electronica/ |
| Anuncios / tablón WP | https://www.granadilladeabona.org/anuncios/ |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-granadilla-de-abona |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38017/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Grna/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress + Kadence + Yoast SEO (`granadilladeabona.org`).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-granadilla-de-abona` con **60 recursos** (22 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP).
- **GEOBDP:** 20 documentos con visor OpenLayers y botón «Localizar» (`findRecintoByDocumento`); geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Noticias WP:** posts sobre reparcelación San Isidro, plan de choque licencias, modificación PG, sector Noroeste, etc. (sitemaps `post-sitemap*.xml`).
- **Sede `sede.granadilladeabona.es`:** inaccesible desde el entorno del agente (timeout / respuesta vacía); el adapter documenta el enlace y no depende de ella.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Noticias informativas sobre resolución de licencias (`urbanismo-resuelve-*-licencias-*`).
- Trámites vía sede electrónica (no accesible en CI); el adapter incluye páginas informativas (sede + noticias de licencias).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es`) sin query por expediente
- **Estrategia:** indexar documentos GEOBDP del municipio; para cada recurso SITCAN emparejar por título normalizado y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (~20 polígonos); noticias WP y licencias sin geometría enlazable; sede inaccesible.

## Limitaciones generales

- Sede electrónica no responde desde CI (documentado; no bloquea ingesta).
- Sin tablón de licencias concedidas en abierto.
- WP mezcla noticias de exposiciones culturales con urbanismo — filtro por keywords.
