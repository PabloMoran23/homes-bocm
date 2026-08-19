# La Carlota — investigación portal ayuntamiento

**Municipio:** La Carlota (Córdoba, Andalucía)  
**Slug:** `la-carlota`  
**Boletín:** BOJA (`boja`, 5 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://lacarlota.es | **Operativa** — WordPress Divi v4.27 |
| PGOU / planeamiento | https://lacarlota.es/pgou-de-la-carlota/ | **Operativa** — listado textual de instrumentos, sectores y planos (sin PDFs enlazados en HTML) |
| Sede electrónica | https://sede.eprinsa.es/carlota | **Operativa** — plataforma eprinsa (Diputación de Córdoba), Ember.js SPA |
| Tablón de edictos | https://sede.eprinsa.es/carlota/tablon-de-edictos | **SPA** — componente `wec-bulletins`; requiere `appToken` de sesión |
| Validación documentos (CSV) | https://sede.eprinsa.es/carlota/validacion-de-documentos | Consulta por código seguro de verificación |
| Catálogo trámites | https://sede.eprinsa.es/carlota/tramites | Trámites administrativos (sin histórico de licencias) |
| Transparencia | https://transparencia.lacarlota.es | Portal separado; sin carpetas urbanismo estructuradas |
| Enlace sede web | https://lacarlota.es/sede | Redirige a sede.eprinsa.es/carlota |

## PGOU (web municipal)

- **CMS:** WordPress Divi + Toolset Views.
- **Contenido:** instrumentos de planeamiento en texto plano:
  - Plan Parcial sector SUBS I-8 (aprobación inicial; CSV en sede).
  - Referencias BOJA (aprobación definitiva PGOU 2014, toma de conocimiento 2023).
  - Documento refundido: ordenación, ordenanzas, catálogo, planos por núcleos (Fuencubierta, Las Pinedas, La Chica Carlota, El Garabato, Aldea Quintana, El Rinconcillo, Monte Alto, El Arrecife, Núcleo Principal).
- **Sin enlaces PDF** en el HTML renderizado; documentación en sede vía CSV o transparencia.
- **WP REST API:** la página PGOU no expuesta por slug en `/wp-json` (posible restricción); el scrape usa HTML público.

## Tablón de edictos (eprinsa)

- **Plataforma:** sede.eprinsa.es — APIs en `apis.dipucordoba.es` (`apifire`, `apisede`, `apitokenv3`).
- **Listado:** web component `@componentes/wec-bulletins` con `token`, `scheme` y `setUp` de entidad.
- **APIs internas:** `apifire` responde 404 desde red pública; `apiconfiguracion` exige token autorizado.
- **Conclusión:** no hay endpoint REST scrapeable sin sesión de navegador; el adapter documenta el tablón como fuente informativa de licencias.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Las licencias publicadas como edictos deberían aparecer en el tablón eprinsa (cuando existan).
- Trámites vía sede (`/tramites`) y consulta de expedientes con autenticación (`/expedientes`).

## Proyectos / planeamiento

- **PGOU web:** ~45 entradas parseables (sectores, planos, BOJA, plan parcial en trámite).
- **BOJA:** innovaciones PGOU (Hábitat Rural Diseminado 2024; sector SUBO-PPI Crta. de la Paz 2026) publicadas en Junta de Andalucía, no replicadas en listado web actualizado.
- **Sin visor de seguimiento** de expedientes urbanísticos público fuera del tablón/sede autenticada.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ — cartografía LISTA/PGOU por municipio; sin campo expediente del ayuntamiento.
  - SITUA: documentación de instrumentos de planeamiento autonómicos; sin query por código de expediente municipal.
  - PGOU web: solo títulos de planos (A-1.1, N-10.1, etc.) sin servicio WFS/ArcGIS enlazado.
- **Estrategia:** VITUA muestra clasificación y ámbitos del PGOU vigente, pero **no enlaza** con filas del tablón ni CSV de la sede. Los anuncios son PDF/texto sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por expediente o sector desde el portal municipal.
  - Tablón SPA sin API pública.
  - El orquestador aplicará centroide municipio + jitter (`centroid: [37.6736, -4.9292]`).

## Limitaciones generales

- Tablón eprinsa no scrapeable determinísticamente (token de sesión).
- PGOU sin PDFs directos en HTML.
- Consulta de expedientes requiere login.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.la_carlota:LaCarlotaAyuntamientoAdapter`
- Fuentes: página PGOU (proyectos) + páginas informativas sede eprinsa (licencias).
