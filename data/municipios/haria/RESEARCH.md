# Haría — investigación portal ayuntamiento

Municipio: **Haría** (`haria`) — Canarias, provincia Las Palmas (norte de Lanzarote). Boletín: `boc_canarias` (2 avisos). INE: 35011.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal WordPress | https://www.ayuntamientodeharia.com/haria |
| Plan General (WP REST id=134) | https://www.ayuntamientodeharia.com/haria/ayuntamiento/normativa/plan-general/ |
| Formularios oficina técnica | https://www.ayuntamientodeharia.com/haria/formularios-y-bases-de-concursos-y-subvenciones/ |
| Sede electrónica (Galileo) | https://sede.ayuntamientodeharia.com |
| Tablón público | https://sede.ayuntamientodeharia.com/publico/tablon |
| Edictos RSS | https://sede.ayuntamientodeharia.com/publico/sindicacion/edictos/RSS |
| Informe urbanístico | https://sede.ayuntamientodeharia.com/publico/territorio/informeurbanistico |
| Transparencia sede | https://sede.ayuntamientodeharia.com/transparencia |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-haria |
| GEOBDP documentos | https://geobdp.grafcan.es/core/documentos/652/ , /1136/ |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LZ/Hria/ |

## Cómo se listan expedientes / planeamiento

- **CMS WordPress:** sitio en subdirectorio `/haria/` con página Plan General que enlaza ~80 PDFs (ordenación estructural, pormenorizada, catálogo patrimonio, modificaciones). Contenido accesible vía REST API (`/wp-json/wp/v2/pages/134`).
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-haria` con 2 instrumentos únicos (adaptación DL 1/2000 y modificación puntual 1-2-3-4) × enlaces SIPU/IDECanarias/GEOBDP.
- **GEOBDP Grafcan:** documentos 652 y 1136 con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Sede Galileo:** tablón `/publico/tablon` renderizado por JavaScript (sin tabla HTML estática en el HTML inicial); edictos vía RSS `/publico/sindicacion/edictos/RSS` (4 items recientes, mayormente no urbanísticos).
- **Tablón autenticado** `/board` redirige a login; no usado.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Formularios PDF en oficina técnica: licencia obras, segregación, comunicación previa, cédula urbanística, etc.
- Trámites vía sede electrónica; el adapter incluye páginas informativas (formularios + informe urbanístico + sede).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent` (docs 652, 1136)
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** indexar documentos GEOBDP desde recursos SITCAN; emparejar por título normalizado; reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo 2 instrumentos de planeamiento en GEOBDP con polígono; PDFs del plan general y formularios sin geometría enlazable; tablón público sin HTML estático; sin listado abierto de licencias concedidas.

## Limitaciones generales

- Tablón sede JS-rendered — no scrapeable sin headless browser.
- Edictos RSS con histórico limitado (~4 items) y pocos anuncios urbanísticos.
- Sin visor urbanístico municipal interactivo; geometría solo vía GEOBDP/SITCAN.
- `insecure_ssl: true` por compatibilidad con sedes Canarias en CI.
