# El Tanque — investigación portal ayuntamiento

Municipio: **El Tanque** (`el-tanque`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (1 aviso BOCM). INE: 38044.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress + Elementor) | https://www.eltanque.es |
| Oficina Técnica (licencias urbanismo) | https://www.eltanque.es/area-administrativa/oficina-tecnica/ |
| Sede electrónica (espublico gestiona) | https://eltanque.sedelectronica.es |
| Tablón de anuncios sede | https://eltanque.sedelectronica.es/board |
| Catálogo trámites sede | https://eltanque.sedelectronica.es/catalog |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-el-tanque |
| GEOBDP municipio | https://geobdp.grafcan.es/core/municipios/38044/ |
| IDECanarias índice | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Tanq/472/indice.html |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress + Elementor + Yoast SEO (`www.eltanque.es`). Dominio `aytoeltanque.es` no resuelve DNS; el portal oficial es `eltanque.es`.
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-el-tanque` con **1 instrumento** (Normas Subsidiarias de Planeamiento, aprobación definitiva 1999/2000).
- **GEOBDP:** documento `561` con visor OpenLayers; geometría embebida en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Noticias WP:** consulta pública previa PGOU 2026, subvención redacción instrumentos ordenación, obras urbanización El Lance, etc. (sitemaps `post-sitemap.xml`).
- **Sede `eltanque.sedelectronica.es`:** tablón `/board` con documentos `preview-document/{uuid}` (edictos, bandos); requiere cookies de sesión (warm-up `/info.0`).

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Trámites descritos en la Oficina Técnica: licencia obra mayor/menor, 1ª ocupación, segregación, actividades, vados, informes urbanísticos.
- Sede espublico: catálogo de trámites sin listado histórico de concesiones scrapeable.
- El adapter incluye páginas informativas (oficina técnica + sede) y filtra el tablón por keywords urbanísticas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/561.html` — polígono municipal Normas Subsidiarias (UTM28N en `zoomToExtent`)
  - SITCAN enlaza el instrumento a GEOBDP e IDECanarias
  - PGOU 2026 en consulta pública previa (WP) sin geometría publicada aún
- **Estrategia:** indexar documento GEOBDP 561; emparejar recurso SITCAN por título; reproyectar EPSG:32628 → WGS84 inline.
- **Limitaciones:** solo 1 polígono de planeamiento vigente en GEOBDP; PGOU 2026 en redacción/consulta sin visor; licencias y tablón sin geometría enlazable.

## Limitaciones generales

- Dominio histórico `aytoeltanque.es` inactivo; usar `eltanque.es`.
- Sede espublico requiere cookie jar (redirect loop `/info` → `/info.0`).
- Tablón mayoritariamente no urbanístico (edictos notariales, bandos forestales).
- WP mezcla noticias de urbanización/obras con cultura/eventos — filtro por keywords.
