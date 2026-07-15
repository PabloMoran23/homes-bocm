# Loeches — investigación portal ayuntamiento

**Municipio:** Loeches (Comunidad de Madrid / BOCM)  
**Fecha:** 2026-07-15

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://loeches.es |
| Urbanismo (WP) | https://loeches.es/urbanismo/ |
| Categoría WP Urbanismo | https://loeches.es/category/urbanismo/ |
| WP REST posts urbanismo | `https://loeches.es/wp-json/wp/v2/posts?categories=34` |
| PGOU (post + PDFs) | https://loeches.es/plan-general-de-ordenacion-urbana/ |
| Sede electrónica | https://loeches.sedelectronica.es |
| Tablón de anuncios | https://loeches.sedelectronica.es/board/ |
| Trámites IP (sede) | https://loeches.sedelectronica.es/info.0 |

## CMS y formato de listados

- **Web:** WordPress (tema Mandrake / mini-mandrake, Yoast SEO). Redirección `www.loeches.es` → `loeches.es`.
- **Sede:** espublico gestiona **eHome** (tablón HTML con clases `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`; enlaces `preview-document/{uuid}`).
- **Proyectos WP:** REST API categoría `34` (Urbanismo, 5 posts publicados). PGOU con 3 PDFs embebidos en post 16661 (`PLANOS.pdf`, `MEMORIA-PRELIMINAR.pdf`, `TRIPTICO.pdf`).
- **Tablón:** tabla HTML paginada; filas de urbanismo/licencias mezcladas con empleo público y otros anuncios. Filtro por regex en adapter.
- **Licencias:** procedimientos «Licencias Urbanísticas» y «Licencias de Actividad» en tablón; no hay dataset tabular de concesiones históricas. Páginas informativas en sede y web urbanismo.

## Licencias

- Tablón sede: anuncios de información pública de licencias (obra, actividad, infraestructura).
- Trámites informativos: web urbanismo + sede (`/info.0` requiere cookie jar; redirect loop sin sesión).
- Sin visor de licencias con coordenadas parcela.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - No hay visor urbanístico municipal propio.
  - WFS Comunidad de Madrid: `sitcm:VPLA_V_AMBITO` en `https://idem.comunidad.madrid/geoserver3/ows`
  - Filtro municipio: `DS_MUNICIPIO ILIKE '%LOECHES%'` → 8 ámbitos (S-1…S-6, U-1, U-2): PANCHO CHICO, VALDEPOZUELO, EL CRUCERO, LOS PRADOS, CABEZO GORDO, CAMINO PERALTA, etc.
- **Estrategia:** cruce título expediente → ámbito SITCM vía `resolve_ambito_geometry()` / enricher `sitcm_ambito` en orquestador. Códigos tipo `S-4`, `U-1` en nombres de ámbito.
- **Limitaciones:** títulos del tablón no siempre citan código de sector; muchos expedientes son PDFs sin georef; sin ArcGIS municipal. El orquestador aplica centroide municipio + jitter cuando no hay match.

## Limitaciones técnicas

- Certificado SSL de `loeches.sedelectronica.es` inválido en algunos entornos → `insecure_ssl: true`.
- `/info.0` en sede: bucle de redirección sin cookie jar (no usado para scrape principal).
- Tablón mezcla categorías; volumen bajo de filas urbanísticas (~2 en julio 2026).
- Posts WP de categoría urbanismo incluyen noticias no estrictamente expedientes (campañas, parques); filtro `RE_PROYECTO` en adapter.

## Referencias de patrón

- Similar a **Brunete** / **Hoyo de Manzanares**: WP + tablón eHome + PGOU PDFs.
- Geometría como **Leganes** / **Paracuellos**: WFS SITCM `VPLA_V_AMBITO`.
