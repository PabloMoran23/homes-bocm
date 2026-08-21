# Fernán Núñez — investigación portal ayuntamiento

**Municipio:** Fernán Núñez (Córdoba, Andalucía)  
**Slug:** `fernan-nunez`  
**Boletín:** BOJA (`boja`, 3 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://fernannunez.es | **Operativa** — WordPress Divi v4.27 + Yoast SEO |
| Urbanismo / PGOU | https://fernannunez.es/ayuntamiento/urbanismo/ | **Operativa** — 118+ PDFs (NNSS, PGOU 2025, planes parciales, convenios, BOP) |
| Sede electrónica | https://sede.eprinsa.es/fnunez | **Operativa** — plataforma eprinsa (Diputación de Córdoba), Ember.js SPA |
| Tablón de edictos | https://sede.eprinsa.es/fnunez/tablon-de-edictos | **SPA** — componente `wec-bulletins`; requiere token de sesión |
| Catálogo trámites | https://sede.eprinsa.es/fnunez/tramites | Trámites administrativos (sin histórico de licencias) |
| Transparencia sede | https://sede.eprinsa.es/fnunez/transparency | Portal transparencia eprinsa |
| Documentos ayuntamiento | https://fernannunez.es/ayuntamiento/ayuntamiento-documentos/ | Ordenanzas (obras menores, administración electrónica) |

## PGOU y planeamiento (web municipal)

- **CMS:** WordPress Divi; página estática de urbanismo con secciones:
  - Normas Subsidiarias de Planeamiento (1991 + modificaciones).
  - Plan General de Ordenación Urbana (PGOU) — aprobación parcial BOJA 2023, definitiva 2025.
  - **PLANOS PGOU 2025** (clasificación, calificación, sectores, protección, término municipal).
  - Modificaciones del PGOU (innovaciones, modificaciones puntuales NNSS).
  - Planeamiento de desarrollo (PPR-1, PPI-2/3, estudios de detalle R1-01/R1-02).
  - Convenios urbanísticos (PPR-2 UE-1/UE-2, local cine, Antonia Vázquez, etc.).
- **Formato:** enlaces directos a PDF en `/wp-content/uploads/` (2014–2015; planos PGOU 2025 referenciados en sección 2026).
- **WP REST API:** operativa (`/wp-json/wp/v2/posts`); noticia PGOU provisional (2020-09-29).

## Tablón de edictos (eprinsa)

- **Plataforma:** sede.eprinsa.es — misma stack que La Carlota/Priego (Diputación Córdoba).
- **Listado:** SPA Ember con assets `/assets/sede-*.js`; sin API REST pública sin token.
- **Conclusión:** no hay endpoint scrapeable determinísticamente; el adapter documenta el tablón como fuente informativa.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Ordenanza de obras menores en documentos del ayuntamiento (PDF).
- Trámites vía sede (`/tramites`) y consulta de expedientes con autenticación.

## Proyectos / expedientes

- **Página urbanismo:** ~118 PDFs parseables (PGOU, planes parciales, convenios, publicaciones BOP/BOJA).
- **Noticias WP:** aprobación provisional PGOU (2020).
- **BOJA:** PGOU aprobación parcial 2023 y definitiva 2025 (Junta de Andalucía).
- Sin visor de seguimiento de expedientes urbanísticos público fuera del tablón/sede autenticada.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **IDECampiSur** (Mancomunidad Campiña Sur): https://www.idecampisur.es/ — portal IDE histórico con módulo planeamiento; **inaccesible** desde red pública (timeout/DNS).
  - **SITUA / VITUA** (Junta de Andalucía): cartografía LISTA/PGOU regional; sin campo expediente municipal ni query por código del ayuntamiento.
  - **PGOU web:** planos en PDF raster (clasificación, calificación, sectores) sin servicio WFS/ArcGIS REST enlazado.
- **Estrategia:** los planos son PDFs estáticos sin georreferencia vectorial accesible; no hay `objectId` ni capa MapServer pública por expediente.
- **Limitaciones:**
  - Sin WFS/GeoJSON/ArcGIS REST accesible por expediente o sector desde el portal municipal.
  - Tablón SPA sin API pública.
  - IDECampiSur caído o restringido.
  - El orquestador aplicará centroide municipio + jitter (`centroid: [37.6722, -4.7256]`).

## Limitaciones generales

- Tablón eprinsa no scrapeable determinísticamente (token de sesión).
- Muchos PDFs son fragmentos de un mismo instrumento (índices, anexos); el adapter deduplica por URL.
- Consulta de expedientes requiere login en sede.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.fernan_nunez:FernanNunezAyuntamientoAdapter`
- Fuentes: página urbanismo (proyectos PDF) + noticias WP + páginas informativas sede eprinsa (licencias).
