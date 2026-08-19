# Priego de Córdoba — investigación portal ayuntamiento

## Municipio

- **Nombre:** Priego de Córdoba
- **Provincia:** Córdoba (Andalucía)
- **BOJA:** 4 avisos en `ccaa_history_parsed_incremental.csv`

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web oficial | https://priegodecordoba.es |
| Urbanismo (área temática) | https://priegodecordoba.es/temas/urbanismo-suelo-y-vivienda/ |
| Normativa municipal PGOU/PE | https://priegodecordoba.es/temas/urbanismo-suelo-y-vivienda/normativa-municipal-de-urbanismo/ |
| Documentación y modelos solicitud | https://priegodecordoba.es/temas/urbanismo-suelo-y-vivienda/documentacion-y-modelos-de-solicitud-del-area-de-urbanismo/ |
| Sede electrónica (eprinsa) | https://priegodecordoba.es/sede → https://sede.eprinsa.es/priego |
| Trámites sede | https://sede.eprinsa.es/priego/tramites |

## CMS y formato de datos

- **Web institucional:** WordPress + Divi (Toolset Views). REST API pública en `/wp-json/wp/v2/`.
- **Noticias urbanismo:** categoría WP `71` (`include_categories` en módulo blog del área). ~69 entradas con título + enlace a PDF en `wp-content/uploads/`.
- **Planeamiento:** PDFs históricos en página de normativa (PGOU, PEPRICCH, innovaciones, plan parcial).
- **Licencias:** no hay listado de concesiones; modelos de solicitud/declaración responsable en documentación urbanismo. Algunas noticias mencionan licencias concedidas (prensa).
- **Sede eprinsa:** Ember SPA (Diputación de Córdoba). Tablón `wec-bulletins` vía `apifire`/`apiconfiguracion` requiere token de sesión — no scrapeable sin browser (mismo patrón que La Carlota).

## Expedientes / proyectos

1. **WP REST API** `GET /wp-json/wp/v2/posts?categories=71&per_page=100` — anuncios BOJA/BOP, aprobaciones PGOU/PE, avances ARI, cambios de uso, etc.
2. **HTML normativa** — PDFs de innovaciones y planes especiales enlazados directamente.
3. Cada post suele tener un único PDF: `Clicar aquí para ver anuncio.`

## Licencias

- Modelos PDF: declaración responsable obras, licencia espectáculo público, ocupación vía pública (documentación urbanismo).
- Noticias WP con palabras clave licencia/obra/cambio de uso filtradas como concesiones publicadas.
- Tablón sede eprinsa inaccesible para scraping determinista.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes investigadas:**
  - `mapserver.eprinsa.es` referenciado en CSP de la web pero `/arcgis/rest/services` devuelve 404.
  - `www.aytopriegodecordoba.es` redirige a priegodecordoba.es (sin visor propio).
  - VITUA/SITUA Junta de Andalucía: sin enlace por expediente municipal identificable.
  - Anuncios y PDFs sin ref. catastral ni coordenadas.
- **Estrategia:** orquestador aplicará centroide municipio + jitter (`centroid: [37.4389, -4.1958]`).
- **Limitaciones:** sin polígonos de ámbito en fuentes públicas; futuro visor eprinsa requeriría reverse-engineering API autenticada.

## Limitaciones

- Tablón edictos sede eprinsa no accesible sin sesión.
- Licencias mayoritariamente informativas (formularios), no registro de concesiones.
- Sin geometría GIS enlazable a expedientes.
