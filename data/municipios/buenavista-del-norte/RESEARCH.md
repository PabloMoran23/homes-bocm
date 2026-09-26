# Buenavista del Norte — investigación portal ayuntamiento

Municipio: **Buenavista del Norte** (`buenavista-del-norte`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (1 aviso BOCM). INE: 38010.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal (WordPress + Divi) | https://www.buenavistadelnorte.es |
| Oficina Técnica (urbanismo) | https://www.buenavistadelnorte.es/ayuntamiento/areas-municipales/oficina-tecnica/ |
| Sede electrónica tributaria | https://sede.buenavistadelnorte.es |
| Tasas construcción/obras | https://sede.buenavistadelnorte.es/publico/recaudacion/tasas |
| Sede expedientes (Cl@ve) | https://buenavistadelnorte.sedelectronica.es/expedientes |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-buenavista-del-norte |
| GEOBDP municipio (INE 38010) | https://geobdp.grafcan.es/core/municipios/38010/ |
| IDECanarias índice PGO | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/Buen/457/indice.html |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress + Divi Child + Yoast SEO (`buenavistadelnorte.es`).
- **Planeamiento sistematizado (Gobierno de Canarias):** dataset CKAN SITCAN `planeamiento-urbanistico-de-buenavista-del-norte` con el **PGO aprobado definitivamente** (BOC 087/07, 11/06/2007). Recursos: SIPU ZIP, FIP ZIP, visor GEOBDP HTML, índice IDECanarias PDF.
- **GEOBDP:** documento `452` con visor OpenLayers; geometría del ámbito en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N). Incluye planes especiales (litoral, casco histórico) como capas internas.
- **Noticias WP:** posts sobre reparcelación Daute Flor, asistencia urbanística insular, plan de movilidad urbana sostenible, obras municipales (sitemaps `post-sitemap.xml`).
- **Sede expedientes:** `buenavistadelnorte.sedelectronica.es/expedientes` requiere identificación Cl@ve; sin listado público de expedientes.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- La Oficina Técnica tramita licencias y disciplina urbanística (información de contacto en web).
- Autoliquidación de **impuesto sobre construcciones, instalaciones y obras** en sede tributaria.
- El adapter incluye páginas informativas (sede + oficina técnica); no hay tablón de licencias en abierto.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/452.html` — polígono PGO UTM28N en `zoomToExtent`
  - SITCAN enlaza el instrumento a GEOBDP e IDECanarias
  - IDECanarias WMS regional sin query por expediente individual
- **Estrategia:** emparejar recurso SITCAN con documento GEOBDP 452 por título; descargar geometría embebida y reproyectar EPSG:32628 → WGS84.
- **Limitaciones:** solo el PGO sistematizado tiene polígono en GEOBDP (1 documento); noticias WP y licencias sin geometría enlazable; sede de expedientes con login.

## Limitaciones generales

- Sin tablón de anuncios/licencias concedidas en HTML abierto.
- Expedientes administrativos detrás de Cl@ve.
- WP mezcla noticias culturales/deportivas con urbanismo — filtro por keywords en el adapter.
