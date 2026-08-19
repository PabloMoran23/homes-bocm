# El Paso — investigación portal ayuntamiento

Municipio: **El Paso** (`el-paso`) — Canarias, provincia Santa Cruz de Tenerife (La Palma). Boletín: `boc_canarias` (3 avisos BOCM). INE: 38027.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress + Elementor) | https://elpaso.es |
| Sede electrónica (Maggioli ATM Angular) | https://sede.elpaso.es |
| Anuncios / bandos WP | https://elpaso.es/institucion/anuncios/ |
| Planes municipales | https://elpaso.es/institucion/planes-municipales/ |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-el-paso |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38027/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/Paso/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress + Elementor + Yoast SEO (`elpaso.es`).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-el-paso` con **16 recursos** (5 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP).
- **GEOBDP:** 5 documentos con visor OpenLayers y botón «Localizar» (`findRecintoByDocumento`); geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Noticias WP:** posts sobre urbanización calles, obras casco urbano, rehabilitación viviendas volcán, etc. (sitemaps `post-sitemap.xml`).
- **Sede `sede.elpaso.es`:** SPA Angular Maggioli; expedientes referenciados en BOC (p. ej. modificación PGO expediente 3679/2025) pero sin API pública de tablón scrapeable; el adapter documenta el enlace informativo.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Trámites vía sede electrónica Maggioli (licencias de obra, comunicaciones previas).
- El adapter incluye páginas informativas de la sede y enlaces a trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es`) sin query por expediente
- **Estrategia:** indexar documentos GEOBDP del municipio; para cada recurso SITCAN emparejar por título normalizado y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (5 polígonos); noticias WP y licencias sin geometría enlazable; sede SPA sin tablón HTML.

## Limitaciones generales

- Sede electrónica es SPA sin tablón scrapeable (documentado; no bloquea ingesta).
- Sin tablón de licencias concedidas en abierto.
- WP mezcla noticias de obras/urbanización con otros temas — filtro por keywords.
- Páginas institucionales (anuncios, planes) con spam SEO inyectado en footer; el adapter filtra por dominio elpaso.es.
