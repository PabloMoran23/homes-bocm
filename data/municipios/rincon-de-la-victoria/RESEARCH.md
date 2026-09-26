# Rincón de la Victoria — investigación portal ayuntamiento

**Municipio:** Rincón de la Victoria (`rincon-de-la-victoria`)  
**INE:** 29038 | **Provincia:** Málaga | **CCAA:** Andalucía  
**Portal base:** https://www.rincondelavictoria.es

## Fuentes identificadas

| Fuente | URL | CMS/plataforma | Contenido |
|--------|-----|----------------|-----------|
| Web municipal | `https://www.rincondelavictoria.es` | Drupal 10 (Bootstrap Barrio) | Urbanismo, PGOM, desarrollo, modificaciones, convenios |
| Ordenación urbanística | `/areas/urbanismo-y-vivienda/ordenacion-urbanistica` | Drupal | Panel lateral: PGOU vigente, desarrollo, modificaciones, catálogo |
| PGOM aprobación inicial | `/areas/urbanismo-y-vivienda/nuevo-plan-general/aprobacion-inicial` | Drupal + PDFs | 24+ documentos (memorias, planos, informes) — aprobado mayo 2025 |
| Desarrollo urbanístico | `/areas/urbanismo-y-vivienda/ordenacion-urbanistica/desarrollo/*` | Drupal + PDFs | Instrumentos por núcleo (La Cala del Moral, Rincón, Benagalbón, Torre) |
| Modificaciones | `/areas/urbanismo-y-vivienda/ordenacion-urbanistica/modificaciones/*` | Drupal + PDFs | Modificaciones puntuales por núcleo |
| Convenios urbanísticos | `/areas/urbanismo-y-vivienda/convenios-urbanisticos` | Drupal + PDFs | Listado convenios 2016+ |
| Información pública | `/areas/urbanismo-y-vivienda/informacion-publica` | Drupal | Página informativa (sin listado dinámico de expedientes) |
| Sede electrónica | `https://sede.rincondelavictoria.es` | SWAL ASP.NET | Trámites, tablón de anuncios y edictos |
| Tablón anuncios | Sede → menú lateral índice 3 (`blLateral=3`) | SWAL postback | Grid `ctl00_principal__gridDetalle` con edictos paginados |
| Visor urbanismo | `/areas/urbanismo-y-vivienda/visor-urbanismo` | — | **En construcción** — sin visor activo |
| SITUA (Junta) | `https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf` | JSF | Consulta planeamiento aprobado regional |

## Cómo se listan expedientes

- **Proyectos/planeamiento:** Páginas Drupal con enlaces a PDFs en `/sites/default/files/YYYY-MM/*.pdf`. Estructura jerárquica por tipo (PGOU, PGOM, desarrollo, modificaciones) y por núcleo de población (La Cala del Moral, Rincón de la Victoria, Benagalbón, Torre de Benagalbón).
- **Información pública:** No hay sección de expedientes en IP con URLs individuales; la página es meramente informativa.
- **Tablón sede:** ASP.NET con postback (`__VIEWSTATE`); paginación vía `lnkSiguiente`. Pocos edictos de urbanismo en las páginas recientes (mayoría fiscal/administrativa).
- **Licencias:** No hay dataset ni listado histórico de licencias concedidas. Solo trámites informativos en sede y contacto urbanismo.

## Cómo se publican licencias

- Sin tablón dedicado a licencias de obra concedidas.
- Sede SWAL ofrece catálogo de trámites (licencias, certificados) con autenticación.
- Edictos de licencia pueden aparecer esporádicamente en el tablón general de anuncios.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Ninguna fuente GIS pública enlazable a expedientes.
  - Visor urbanístico municipal: página indica que está en desarrollo; consultas a urbanismo@rincondelavictoria.es.
  - SITUA (Junta de Andalucía): consulta de planeamiento aprobado, sin API GeoJSON/WFS por expediente.
  - PDFs de planos (PGOM, PGOU): cartografía rasterizada sin servicio WMS/WFS público.
- **Estrategia:** El adapter no implementa `_fetch_geometry`; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** Sin visor ArcGIS/WFS; documentación solo en PDF; tablón sin georreferencia.

## Limitaciones

- Visor urbanístico no operativo.
- Tablón SWAL con poco contenido urbanístico reciente.
- Sin listado de licencias concedidas.
- Sede requiere certificado digital para trámites.
- JSON:API Drupal no habilitado públicamente.

## Estrategia del adapter

1. Crawl BFS de páginas `/areas/urbanismo-y-vivienda/*` (hasta 40 páginas).
2. Extraer PDFs urbanísticos de `/sites/default/files/`.
3. Paginar tablón SWAL (postback `blLateral=3`, hasta 15 páginas).
4. Filtrar por regex urbanismo/licencias.
5. Fila metadata SITUA para PGOU/PGOM regional.
6. IDs: `rincon-de-la-victoria-{lic|proy}-{sha256[:14]}`.
