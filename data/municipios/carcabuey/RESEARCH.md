# Carcabuey — investigación portal ayuntamiento

**Municipio:** Carcabuey (Córdoba, Andalucía)  
**Slug:** `carcabuey`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://carcabuey.es | **Operativa** — WordPress Divi + Toolset Views |
| Urbanismo / planeamiento | https://carcabuey.es/urbanismo/ | **Operativa** — memoria PGOU, normativa, planimetría (PDFs) |
| Sede electrónica | https://sede.eprinsa.es/carcabuey | **Operativa** — plataforma eprinsa (Diputación de Córdoba), Ember.js SPA |
| Tablón de edictos | https://sede.eprinsa.es/carcabuey/tablon-de-edictos | **SPA** — componente `wec-bulletins`; requiere token de sesión |
| Catálogo trámites | https://sede.eprinsa.es/carcabuey/tramites | Trámites administrativos (sin histórico de licencias) |
| Transparencia | https://transparencia.carcabuey.es | Portal separado (plenos, contratos) |
| Enlace sede web | https://carcabuey.es/sede | Redirige a sede eprinsa (SPA embebida) |
| Edictos web | https://carcabuey.es/edictos-bandos-y-ordenanzas/ | Enlaces genéricos; sin listado urbanístico estructurado |

## PGOU y planeamiento (web municipal)

- **CMS:** WordPress Divi.
- **Secciones en `/urbanismo/`:**
  - Modelos de solicitud (licencias obras mayores/menores, DR actividad, comunicación previa).
  - Normativa urbanística: memoria NN.SS y memoria PGOU (PDF).
  - Planimetría: ordenación estructural (término, núcleo, Algar), edificios protegidos/zonificación, planeamiento vigente PL01/PL02 (PDF).
- **BOJA:** subsanación PGOU publicada en BOJA 2023 (Delegación Territorial Córdoba); referencia en adapter vía entrada SITUA.
- **WP REST API:** accesible (`/wp-json/wp/v2/posts`); pocas noticias urbanísticas recientes.

## Tablón de edictos (eprinsa)

- **Plataforma:** sede.eprinsa.es — APIs en `apis.dipucordoba.es` (`apifire`, `apisede`, `apitokenv3`).
- **Listado:** web component `@componentes/wec-bulletins` con token de sesión.
- **Conclusión:** no hay endpoint REST scrapeable sin sesión de navegador; el adapter documenta el tablón como fuente informativa de licencias.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Formularios PDF en la web municipal (solicitudes, DR, comunicación previa).
- Las licencias publicadas como edictos deberían aparecer en el tablón eprinsa (cuando existan).
- Consulta de expedientes vía sede con autenticación Cl@ve/certificado.

## Proyectos / planeamiento

- **PDFs urbanismo:** 8 documentos de planeamiento (memorias, planimetría estructural y vigente).
- **SITUA:** instrumentos de planeamiento autonómicos consultables en visor Junta.
- **Sin visor de seguimiento** de expedientes urbanísticos público fuera del tablón/sede autenticada.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ — cartografía LISTA/PGOU por municipio; sin campo expediente del ayuntamiento.
  - SITUA: https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — documentación de instrumentos; sin query por código de expediente municipal.
  - Planimetría web: PDFs raster (ordenación estructural, zonificación) sin servicio WFS/ArcGIS enlazado.
- **Estrategia:** VITUA/SITUA muestran clasificación y ámbitos del PGOU vigente, pero **no enlazan** con filas del tablón ni expedientes de la sede. Los anuncios son PDF sin georreferencia embebida.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por expediente o sector desde el portal municipal.
  - Tablón SPA sin API pública.
  - El orquestador aplicará centroide municipio + jitter (`centroid: [37.4394, -4.2728]`).

## Limitaciones generales

- Tablón eprinsa no scrapeable determinísticamente (token de sesión).
- Licencias: solo formularios y páginas informativas, sin histórico de concesiones.
- Consulta de expedientes requiere login.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.carcabuey:CarcabueyAyuntamientoAdapter`
- Fuentes: PDFs planeamiento en `/urbanismo/` + páginas informativas sede eprinsa (licencias) + entrada SITUA (PGOU).
