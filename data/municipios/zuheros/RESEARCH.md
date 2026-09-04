# Zuheros — investigación portal ayuntamiento

**Municipio:** Zuheros (Córdoba, Andalucía)  
**Slug:** `zuheros`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://zuheros.es | **Operativa** — WordPress Divi |
| PGOU | https://zuheros.es/ayuntamiento/documentos/pgou/ | **Operativa** — 6 documentos Google Drive (memoria, planos, normas, catálogo, resumen) |
| Delegación urbanismo | https://zuheros.es/delegaciones/urbanismo/ | **Operativa** — inventario caminos rurales, modificación PGOU, enlace SITUA |
| Instancias y solicitudes | https://zuheros.es/ayuntamiento/documentos/instancias-y-solicitudes/ | **Operativa** — modelos PDF licencias/DR obras |
| Portal transparencia | https://transparencia.zuheros.es | WordPress Divi (e-admin); publicidad activa, datos abiertos |
| Catálogo datos abiertos | https://zuheros-opendata.e-admin.es | CKAN; categoría urbanismo (callejero, edificios; sin expedientes) |
| Sede electrónica | https://sede.eprinsa.es/zuheros | **Operativa** — plataforma eprinsa (Diputación de Córdoba), Ember.js SPA |
| Tablón de edictos | https://sede.eprinsa.es/zuheros/tablon-de-edictos | **SPA** — componente `wec-bulletins`; requiere token de sesión |
| Geoportal Diputación | https://www.dipucordoba.es/servicios-geoportal/ | WMS/WFS provinciales (mapserver.eprinsa.es); no por expediente municipal |

## PGOU y planeamiento (web municipal)

- **CMS:** WordPress Divi; página PGOU con documentos alojados en **Google Drive**:
  - Documento A: Memoria información / Memoria de ordenación
  - Documento B: Planos (información, evaluación, diagnóstico, criterios, ordenación)
  - Documento C: Normas urbanísticas
  - Documento D: Catálogo
  - Documento E: Resumen ejecutivo
- **Delegación urbanismo:** modificación PGOU (aprobación provisional 9 agosto 2018), inventario caminos rurales 2023 (Google Drive).
- **SITUA:** enlace a https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — visor regional Junta de Andalucía.
- **WP REST API:** operativa (`/wp-json/wp/v2/pages/7051`, `/pages/8186`).

## Tablón de edictos (eprinsa)

- **Plataforma:** sede.eprinsa.es — misma stack que La Carlota/Fernán Núñez (Diputación Córdoba).
- **Listado:** SPA Ember; sin API REST pública sin token.
- **Edictos web:** página `/ayuntamiento/documentos/edictos-y-bandos/` con bandos históricos (mayoría COVID/tráfico; sin licencias urbanísticas recientes).

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Modelos en instancias y solicitudes: licencia obra, declaración responsable, parcelación, ocupación edificación, finalización obras.
- Trámites vía sede (`/tramites`) y consulta de expedientes con autenticación.

## Proyectos / expedientes

- **PGOU:** 6 documentos + enlace modificación catálogo.
- **Urbanismo:** inventario caminos rurales, SITUA planeamiento vigente.
- Sin visor de seguimiento de expedientes urbanísticos público fuera del tablón/sede autenticada.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **Geoportal Diputación Córdoba** (mapserver.eprinsa.es): WMS/WFS provinciales (`planes_especiales_wfs`, cartografía territorial); no enlaza expedientes del ayuntamiento ni consulta por código municipal.
  - **SITUA / SituaDIFusión** (Junta de Andalucía): cartografía LISTA/PGOU regional; sin campo expediente municipal ni geometría descargable por API desde el portal de Zuheros.
  - **zuheros-opendata.e-admin.es:** callejero y edificios (CKAN); sin capas de planeamiento vectorial por expediente.
  - **PGOU web:** documentos en Google Drive (memoria, planos PDF raster); sin servicio WFS/ArcGIS REST enlazado.
- **Estrategia:** los planos son PDFs/Google Drive sin georreferencia vectorial accesible; no hay `objectId` ni capa MapServer pública por expediente.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por expediente desde el portal municipal.
  - Tablón SPA sin API pública.
  - El orquestador aplicará centroide municipio + jitter (`centroid: [37.5431, -4.3150]`).

## Limitaciones generales

- Tablón eprinsa no scrapeable determinísticamente (token de sesión).
- PGOU en Google Drive (no URLs estables wp-content).
- Consulta de expedientes requiere login en sede.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.zuheros:ZuherosAyuntamientoAdapter`
- Fuentes: PGOU + delegación urbanismo (proyectos vía WP REST) + SITUA + modelos instancias + páginas informativas sede eprinsa (licencias).
