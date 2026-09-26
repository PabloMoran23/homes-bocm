# Palma del Río — investigación portal ayuntamiento

## Municipio

- **Nombre:** Palma del Río
- **Provincia:** Córdoba (Andalucía)
- **INE:** 14057
- **BOJA:** 3 avisos en `ccaa_history_parsed_incremental.csv`

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web oficial | https://palmadelrio.es |
| Urbanismo y vivienda | https://palmadelrio.es/urbanismo-y-vivienda/ |
| Planes (PGOU, PEI, PMVS) | https://palmadelrio.es/urbanismo-y-vivienda/planes/ |
| Licencia obras y cocheras | https://palmadelrio.es/urbanismo-y-vivienda/licencia-para-obras-y-cocheras/ |
| Declaración responsable | https://palmadelrio.es/urbanismo-y-vivienda/declaracion-responsable/ |
| Otros servicios urbanísticos | https://palmadelrio.es/urbanismo-y-vivienda/otros-servicios-urbanisticos/ |
| Sede electrónica (eprinsa) | https://sede.eprinsa.es/palmario |
| Tablón de edictos | https://sede.eprinsa.es/palmario/tablon-de-edictos |
| Validación documentos sede | https://sede.eprinsa.es/palmario/validacion-de-documentos |
| Transparencia | https://transparencia.palmadelrio.es/ |
| Visor documental PGOU (e-admin) | https://palmario-ofvirtual.e-admin.es/webdocumental/paginas/visor-resguardos.xhtml |

## CMS y formato de datos

- **Web institucional:** WordPress + Divi (Toolset Views, Getwid). REST API pública en `/wp-json/wp/v2/`.
- **Noticias urbanismo:** categoría WP `135` (Urbanismo, 79 entradas). Incluye aprobaciones PGOU/PERI, convenios urbanísticos, estudios de ordenación, proyectos de urbanización.
- **Planeamiento:** PDFs del PGOU (5 tomos + normas), Plan Especial de Infraestructuras, PMVS y visores documentales e-admin en página de planes.
- **Licencias:** no hay listado público de concesiones; páginas informativas con modelos de solicitud y declaración responsable. Algunas noticias WP mencionan licencias/urbanización.
- **Sede eprinsa:** Ember SPA (Diputación de Córdoba / Eprinsa). Tablón de edictos vía SPA sin API REST pública scrapeable (mismo patrón que Priego, Fernán Núñez, La Carlota).

## Expedientes / proyectos

1. **WP REST API** `GET /wp-json/wp/v2/posts?categories=135&per_page=100` — anuncios BOP/BOJA, aprobaciones PERI/PGOU, convenios urbanísticos, estudios de ordenación, proyectos de urbanización.
2. **HTML planes** — PDFs PGOU (tomos I–V), PEI, PMVS y enlaces a visor documental e-admin.
3. **Búsqueda WP** por términos `planeamiento`, `pgou`, `urbanismo` para capturar entradas fuera de categoría.

## Licencias

- Modelos PDF: declaración responsable obras, licencia obras y cocheras, ocupación vía pública.
- Tablón sede eprinsa (SPA) inaccesible para scraping determinista.
- Noticias WP con palabras clave licencia/obra filtradas como concesiones publicadas cuando aplica.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes investigadas:**
  - `palmario-ofvirtual.e-admin.es` — visor documental de resguardos PGOU (PDFs escaneados, sin geometría vectorial).
  - `sede.eprinsa.es/palmario` — Ember SPA; CSP referencia `apis.dipucordoba.es` pero sin MapServer/ArcGIS público accesible.
  - SITUA (Junta de Andalucía): visor regional de planeamiento sin WFS por expediente municipal enlazable.
  - PDFs de anuncios y PGOU sin ref. catastral ni coordenadas en metadatos scrapeables.
- **Estrategia:** orquestador aplicará centroide municipio + jitter (`centroid: [37.6992, -5.2817]`).
- **Limitaciones:** sin polígonos de ámbito en fuentes públicas; tablón sede requiere sesión/token.

## Limitaciones

- Tablón edictos sede eprinsa no accesible sin sesión Ember.
- Licencias mayoritariamente informativas (formularios), no registro de concesiones.
- Sin geometría GIS enlazable a expedientes individuales.
