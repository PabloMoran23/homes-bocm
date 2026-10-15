# Rute — investigación portal ayuntamiento

**Municipio:** Rute (Córdoba, Andalucía)  
**Slug:** `rute`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://rute.es | **Operativa** — WordPress ePrinsa (CloudFront/nginx) |
| Urbanismo | https://rute.es/servicios/urbanismo/ | Índice; enlace PGOU, LOCALIZAIN, BOP |
| PGOU | https://rute.es/servicios/urbanismo/pgou/ | Documentos Google Drive + enlace SITUA + BOP-A-2023-4034 |
| Programa LOCALIZAIN | https://rute.es/servicios/urbanismo/programa-localizain/ | Polígono industrial Las Salinas (Diputación) |
| Modelos solicitud | https://rute.es/ayuntamiento/normativa-municipal/modelos-de-solicitud/ | PDFs licencia obra, DR, comunicación previa, consulta urbanística |
| Transparencia | https://transparencia.rute.es/ | Portal e-admin (sin expedientes urbanísticos estructurados) |
| Sede electrónica | https://sede.eprinsa.es/rute | **Operativa** — Ember.js SPA (Diputación Córdoba) |
| Tablón de edictos | https://sede.eprinsa.es/rute/tablon-de-edictos | **SPA** — componente `wec-bulletins`; requiere sesión |
| Sede embebida | https://rute.es/sede | Redirige a sede.eprinsa.es/rute |

## PGOU y planeamiento (web municipal)

- **CMS:** WordPress; página PGOU (WP id 7582) con carpetas/archivos en **Google Drive** (memoria, planos, normas) y publicación en **BOP Diputación** (`bop.dipucordoba.es/visor-pdf/.../BOP-A-2023-4034.pdf`).
- **SITUA:** enlace a https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — visor regional Junta de Andalucía.
- **LOCALIZAIN:** programa de localización industrial; enlaces a `proyectoseuropeos.dipucordoba.es` (polígono Las Salinas).
- **WP REST API:** operativa (`/wp-json/wp/v2/pages/7582`, `8975`, `8936`, `8864`).

## Tablón de edictos (eprinsa)

- Misma plataforma que otros municipios de la Diputación de Córdoba (Zuheros, La Carlota, Priego).
- Listado en SPA Ember; sin API REST pública scrapeable sin token de sesión.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Modelos PDF en normativa municipal: licencia de obras, DR obras, comunicación previa, consulta urbanística, primera ocupación, etc.
- Trámites vía sede (`/tramites`) y consulta de expedientes con autenticación.

## Proyectos / expedientes

- **PGOU:** Google Drive + BOP + SITUA.
- **Urbanismo:** BOP modificación PGOU, programa LOCALIZAIN.
- Sin visor de seguimiento de expedientes urbanísticos público fuera del tablón/sede autenticada.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **Geoportal Diputación Córdoba** (`mapserver.eprinsa.es`, referenciado en CSP de rute.es): servicios provinciales; no accesible por API REST sin autenticación desde el entorno del agente; no enlaza expedientes municipales.
  - **SITUA / SituaDIFusión** (Junta de Andalucía): cartografía de planeamiento regional; sin geometría descargable por expediente desde el portal municipal.
  - **PGOU web:** documentos en Google Drive y PDF BOP; sin capa WFS/ArcGIS REST enlazada.
  - **LOCALIZAIN:** documentación de polígono industrial (PDF/web Diputación); sin servicio vectorial por licencia.
- **Estrategia:** no hay `objectId` ni capa MapServer pública consultable por código de expediente; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** tablón SPA; planos raster/PDF; mapserver.eprinsa.es no expuesto de forma scrapeable.

## Listado de datos

- **Proyectos:** enlaces WP (PGOU, urbanismo, LOCALIZAIN), posts WP con términos planeamiento, SITUA.
- **Licencias:** páginas informativas sede + modelos PDF (no concesiones).

## Adapter

- `municipio.adapters.rute:RuteAyuntamientoAdapter`
- Patrón: Zuheros / municipios eprinsa Córdoba.
