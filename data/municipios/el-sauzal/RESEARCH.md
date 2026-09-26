# El Sauzal — investigación portal ayuntamiento

Municipio: **El Sauzal** (`el-sauzal`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (1 aviso BOCM). INE: 38026.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress Bones) | https://www.elsauzal.es |
| Oficina Técnica Municipal | https://www.elsauzal.es/oficina-tecnica-municipal/ |
| PGOU / planeamiento | https://www.elsauzal.es/plan-general-de-ordenacion-urbanistica-pgou/ |
| Sede electrónica (enlace WP) | https://www.elsauzal.es/sede-electronica/ |
| Sede electrónica (espublico) | https://elsauzal.sedelectronica.es/ |
| eAdmin municipal | https://eadmin.elsauzal.es/ |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-el-sauzal |
| IDECanarias índices | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Sauz/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress con tema Bones + Yoast SEO (`elsauzal.es`).
- **Oficina Técnica / PGOU:** página con PDFs de modificaciones (MM 1/2023, estudios de detalle, consultas públicas, anuncios BOC/BOP).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-el-sauzal` con **31 recursos** (11 instrumentos únicos × enlaces FIP/IDECanarias/GEOBDP).
- **GEOBDP:** documentos `https://geobdp.grafcan.es/core/documentos/{id}.html` con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N). IDs conocidos: 398 (PGOU), 1142, 1145, 1268, 1341, 1470, 1500, 1504, 1512, 1515.
- **Sede `elsauzal.sedelectronica.es`:** plataforma espublico/gestiona; redirige con token desde WP; sin tablón de licencias indexable en HTML estático.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Fichas AUA en eAdmin (`eadmin.elsauzal.es`) como PDF informativo.
- Trámites vía sede electrónica espublico; el adapter incluye páginas informativas (sede + OTM).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{id}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** para cada recurso SITCAN extraer URL GEOBDP; descargar geometría del visor y reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo instrumentos de planeamiento en GEOBDP (~10 polígonos); PDFs WP recientes (MM 1/2023, estudio detalle Los Manzanos) sin geometría enlazable; licencias sin GIS.

## Limitaciones generales

- Sin tablón de licencias concedidas en abierto.
- Sede espublico requiere sesión/token para navegación profunda.
- WP mezcla contenido institucional con urbanismo — filtro por keywords.
