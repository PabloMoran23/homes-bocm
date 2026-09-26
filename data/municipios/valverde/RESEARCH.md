# Valverde — investigación portal ayuntamiento

Municipio: **Valverde** (`valverde`) — Canarias, provincia Valverde (El Hierro). Boletín: `boc_canarias` (2 avisos BOCM). INE: 38051.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress PageLines) | https://aytovalverde.org |
| Urbanismo y vivienda | https://aytovalverde.org/servicios/urbanismo-y-vivienda/ |
| Sede electrónica (espublico gestiona) | https://aytovalverde.sedelectronica.es |
| Tablón de anuncios | https://aytovalverde.sedelectronica.es/board |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-valverde |
| GEOBDP documentos | https://geobdp.grafcan.es/core/documentos/{id}.html |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/EH/Valv/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress PageLines v2.5 + Yoast SEO (`aytovalverde.org`).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-valverde` con **48 recursos** (13 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP).
- **GEOBDP:** 12 documentos con visor OpenLayers; geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N). Índice construido desde enlaces SITCAN (la página `/core/municipios/38051/` lista otro municipio).
- **Noticias WP:** posts sobre PGO, planeamiento municipal, movilidad urbana, etc. (sitemaps `post-sitemap.xml`).
- **Sede `aytovalverde.sedelectronica.es`:** tablón HTML scrapeable (`/board`) con anuncios, ordenanzas, callejero y expedientes; expedientes personales requieren Cl@ve.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Trámites vía sede electrónica espublico (licencias de obra, comunicaciones previas).
- Tablón publica ordenanzas fiscales de tasas (licencias) pero sin listado histórico georreferenciado.
- El adapter incluye páginas informativas de urbanismo y sede.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (docs 610–623)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es`) sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP desde recursos SITCAN; para cada instrumento emparejar por título normalizado y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (~12 polígonos); noticias WP, tablón y licencias sin geometría enlazable; expedientes de sede requieren autenticación.

## Limitaciones generales

- Sin visor urbanístico municipal propio; datos GIS solo vía GEOBDP/SITCAN regional.
- Tablón sede mezcla urbanismo con actas de pleno, padrón IAE, etc. — filtro por keywords.
- WP mezcla noticias de planeamiento con planes de empleo — filtro por exclusión de `plan-de-empleo`.
- Página GEOBDP municipio 38051 devuelve documentos de otro ayuntamiento; el adapter usa índice SITCAN.
