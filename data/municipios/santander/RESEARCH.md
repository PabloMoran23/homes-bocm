# Santander — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal 7) | https://www.santander.es |
| PGS — información pública | https://www.santander.es/ciudad/pgs/informacion-publica |
| PGS — estudios de detalle (en vigor) | https://www.santander.es/ciudad/pgs/en-vigor/estudios-detalle |
| PGS — unidades de actuación / sectores / modificaciones | https://www.santander.es/ciudad/pgs/en-vigor/ |
| Sede electrónica | https://sede.santander.es |
| Tablón — otros anuncios (exposición pública) | https://sede.santander.es/tablon-de-edictos/otros-anuncios |
| Trámites licencias de obra | https://sede.santander.es/tramites/tramites-procedimientos/areas-sede/urbanismo-y-ciudad/territorio-urbanismo-y-vivienda/licencias-de-obra-e-instalaciones |
| Plano interactivo (callejero) | https://aytosantander.maps.arcgis.com/apps/webappviewer/index.html?id=81908d63b4be4ec3a2f9f1e93a608888 |
| Geoportal gestión territorial | https://gestionterritorial-cegird.hub.arcgis.com/ |
| Datos abiertos | http://datos.santander.es/data/ |

## Cómo se listan expedientes / planeamiento

- **Drupal 7 (PGS):** bloques `field-contenido` con títulos en `<li><strong>…</strong>` y PDFs en `/sites/default/files/*.pdf`; la página de **información pública** agrupa expedientes activos en `<ul><li>título</li></ul>` + `<ol>` de documentos.
- **Estudios de detalle / en vigor:** listados históricos y vigentes con enlaces a memoria/planos y, en muchos casos, enlace a publicación en **BOC** (`boc.cantabria.es`).
- **Tablón sede:** vista Drupal `tablon_anuncios` (tabla HTML) con unidad tramitadora y fecha de exposición; filtro por área (p. ej. «Licencias de Obras», «Planeamiento urbanístico…»).
- **Consulta de expedientes** en sede requiere ser interesado (carpeta ciudadana); no hay API pública de expedientes urbanísticos.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- El tablón publica edictos puntuales (filtro «Licencias de Obras»); en la muestra actual del tablón general hay pocos anuncios urbanísticos.
- Trámites informativos indexados: obra mayor/menor, declaración responsable, derribo, colocación de medio auxiliar, etc. (`/tramites/<slug>`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **SIUCAN / Gobierno de Cantabria:** `https://geoservicios.cantabria.es/inspire/rest/services/Urbanismo/MapServer` — capa **1 Sectores** (`CodSect`, `DenSect`, `NomMuni`).
  - Plano interactivo municipal (ArcGIS Web App) y geoportal de gestión territorial: capas cartográficas y callejero; sin enlace directo expediente→polígono en el portal Drupal.
- **Estrategia:** tras extraer el título del expediente, intentar `query` ArcGIS en Sectores (`returnGeometry=true`, `f=geojson`, `outSR=4326`) cuando el título menciona sector (`S-n`, `SECTOR n`), código de sector conocido o fragmento de `DenSect` (p. ej. «LOS ALEBRIJES»). Unidades de actuación / áreas de reparto no tienen capa dedicada enlazable en SIUCAN.
- **Limitaciones:** estudios de detalle y expedientes IP son principalmente PDF; UA/AR no mapean de forma fiable a `CodSect`; licencias sin geometría; sin boletín BOCM asociado en cola (`bocm_count: 0`).

## Limitaciones del scrape

- HTML Drupal largo con PDFs de gran tamaño (solo se indexan URLs).
- Tablón sin API JSON; paginación limitada en la vista pública.
- SIUCAN tiene carácter informativo (metadatos Gobierno de Cantabria).
