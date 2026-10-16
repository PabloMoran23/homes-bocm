# San Sebastián de los Ballesteros — investigación portal ayuntamiento

**Municipio:** San Sebastián de los Ballesteros (Córdoba, Andalucía)  
**Slug:** `san-sebastian-de-los-ballesteros`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://sansebastiandelosballesteros.es | **Operativa** — WordPress Divi + Toolset Views |
| PGOU / planeamiento | https://sansebastiandelosballesteros.es/pgou-san-sebastian/ | **Operativa** — ~70 PDFs (memorias, planos, normas) |
| Sede electrónica | https://sede.eprinsa.es/ssballes | **Operativa** — eprinsa (Diputación Córdoba), Ember.js SPA |
| Tablón de edictos | https://sede.eprinsa.es/ssballes/tablon-de-edictos | **SPA** — componente `wec-bulletins`; token de sesión |
| Portal transparencia | https://transparencia.sansebastiandelosballesteros.es/ | **Operativa** — Divi (publicidad activa, datos abiertos) |
| Open data municipal | https://sansebastiandelosballesteros-opendata.e-admin.es/ | **502** desde red del agente (nginx) |
| Geoportal Diputación | https://www.dipucordoba.es/servicios-geoportal/ | Referenciado en transparencia; sin capa por expediente municipal |

## PGOU y planeamiento (web municipal)

- **CMS:** WordPress Divi; página estática PGOU con documentación del instrumento:
  - Memorias (información, ordenación, subsanación).
  - Planos índice y capas temáticas (`ssb_dB1_INF_*`, `ssb_dC` normas urbanísticas).
  - Áreas homogéneas, alineaciones, edificios protegidos, desarrollo del planeamiento.
- **Formato:** enlaces directos a PDF en `/wp-content/uploads/2022/05/`.
- **WP REST API:** operativa; noticia aprobación definitiva PGOU (2023-01-09).

## Tablón de edictos (eprinsa)

- Misma stack que Fernán Núñez, La Carlota, Fuente Palmera (Diputación Córdoba).
- Sin API REST pública sin token; el adapter documenta el tablón como fuente informativa.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Ordenanza fiscal de construcciones en normativa local (web).
- Trámites vía sede (`/tramites`) y consulta de expedientes con autenticación Cl@ve.

## Proyectos / expedientes

- **Página PGOU:** PDFs parseables por URL (instrumento completo).
- **Noticias WP:** aprobación definitiva PGOU (enero 2023).
- **SITUA** (Junta de Andalucía): consulta regional de planeamiento.
- Sin visor de seguimiento de expedientes urbanísticos público fuera del tablón/sede autenticada.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **PGOU web:** planos en PDF raster (clasificación, usos, parcelario) sin servicio WFS/ArcGIS REST enlazado.
  - **Open data e-admin:** portal caído (502); conjunto «Urbanismo, infraestructuras y equipamientos» no accesible.
  - **Geoportal Diputación Córdoba:** cartografía provincial; sin query por código de expediente del ayuntamiento.
  - **SITUA / VITUA** (Junta): planeamiento regional; sin polígono por expediente municipal.
  - **CSP** de la web menciona `mapserver.eprinsa.es` en `frame-src` pero sin visor público enlazado desde PGOU.
- **Estrategia:** documentación estática en PDF; no hay `objectId` ni capa MapServer accesible por expediente.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST por expediente.
  - Tablón SPA sin API pública.
  - El orquestador aplicará centroide municipio + jitter (`centroid: [37.6531, -4.8214]`).

## Limitaciones generales

- Tablón eprinsa no scrapeable determinísticamente.
- Open data municipal inaccesible en el entorno de CI.
- Muchos PDFs son anexos del mismo PGOU; el adapter deduplica por URL.
- Consulta de expedientes requiere login en sede.

## Adapter implementado

- `municipio.adapters.san_sebastian_de_los_ballesteros:SanSebastianDeLosBallesterosAyuntamientoAdapter`
- Fuentes: página PGOU (proyectos PDF) + noticias WP + páginas informativas sede eprinsa (licencias).
