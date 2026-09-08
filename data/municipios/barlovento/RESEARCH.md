# Barlovento — investigación portal ayuntamiento

Municipio: **Barlovento** (`barlovento`) — Canarias, provincia Santa Cruz de Tenerife (La Palma). Boletín: `boc_canarias` (1 aviso BOCM). INE: 38007.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress + CityGov theme) | https://barlovento.es |
| Anuncios municipales | https://barlovento.es/anuncios/ |
| Sede electrónica (espublico gestiona) | https://barlovento.sedelectronica.es |
| Tablón de anuncios | https://barlovento.sedelectronica.es/board |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-barlovento |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38007/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LP/Barl/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress + Yoast SEO (`barlovento.es`), secciones noticias/anuncios/eventos.
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-barlovento` con **10 recursos** (3 instrumentos únicos × enlaces SIPU/IDECanarias/GEOBDP):
  - Normas Subsidiarias del PGO (BOC 120/99) → GEOBDP doc **563**
  - Catálogo Protección Arquitectónico y Etnográfico (BOC 053/17) → GEOBDP doc **1076**
  - Plan Parcial Turístico S.A.U. La Fajana (BOC 007/01, BOP 090/13) → GEOBDP doc **1524**
- **GEOBDP:** visor OpenLayers con geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Noticias WP:** posts sobre urbanización, rehabilitación viviendas, suelo urbano La Fajana, obras trama urbana (sitemaps `post-sitemap*.xml`).
- **Sede tablón:** tabla HTML scrapeable en `/board` (espublico gestiona); incluye anuncios de subvenciones rehabilitación vivienda, modificaciones presupuestarias, etc.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Trámites vía sede electrónica (competencia Urbanismo y Vivienda).
- El adapter incluye páginas informativas de la sede y tablón, más anuncios WP/sede filtrados por keywords.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional (`idecan2.grafcan.es`) sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP del municipio (38007); para cada recurso SITCAN emparejar por título normalizado o URL GEOBDP y descargar geometría; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (2–3 polígonos verificados); noticias WP, tablón y licencias sin geometría enlazable; catálogo arquitectónico (doc 1076) puede no exponer polígono en visor.

## Limitaciones generales

- Tablón sede mezcla urbanismo con plenos, presupuestos y subvenciones — filtro por keywords y exclusiones.
- Sin listado histórico de licencias de obra concedidas.
- WP mezcla noticias de obras/urbanización con cultura/deportes — filtro por keywords en sitemap y semillas.
