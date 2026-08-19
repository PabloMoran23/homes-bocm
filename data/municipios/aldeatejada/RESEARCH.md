# Aldeatejada — investigación portal ayuntamiento

**Municipio:** Aldeatejada (Castilla y León, Salamanca)  
**Fecha:** 2026-08-09

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (WordPress Divi) | https://aldeatejada.es | Portal activo (tema Divi Lawyer) |
| Urbanismo | https://aldeatejada.es/ayuntamiento/#urbanismo | ~35 bloques con PGOU, planes parciales, estudios de detalle, licencias ambientales, PDFs |
| Fichas parcelas resultantes | https://aldeatejada.es/fichas-parcelas-resultantes/ | Fichas reparcelación (enlaces PDF) |
| Fichas parcelas aportadas | https://aldeatejada.es/fichas-parcelas-aportadas/ | Fichas aportadas |
| Planos reparcelación | https://aldeatejada.es/planos-de-reparcelacion/ | Planos PDF |
| Tablón de anuncios | https://aldeatejada.es/tablon-de-anuncios/ | Posts WP (bandos, avisos) |
| Edictos | https://aldeatejada.es/edictos/ | Edictos municipales |
| Bandos | https://aldeatejada.es/bandos/ | Bandos |
| WP REST API | https://aldeatejada.es/wp-json/wp/v2 | pages + posts |
| Boletín municipal (ESLA) | http://eslaweb.esla.com/web_278 | Boletín local (externo) |

## Cómo se listan expedientes

- **WordPress:** sección `#urbanismo` en `/ayuntamiento/` con listas anidadas `<strong>` (título del expediente) + enlaces PDF en `/wp-content/uploads/`.
- **REST API:** `wp/v2/pages` (fichas parcelas, planos) y `wp/v2/posts` (edictos con urbanismo, p. ej. autorización uso provisional SUD-11).
- **Sin sede electrónica** espublico/STA propia del municipio; trámites vía web corporativa.
- **Sin visor de expedientes** ni API JSON de listado histórico.
- **BOCYL:** referencias en PDFs y publicaciones (p. ej. aprobaciones PGOU).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra individual.
- Ordenanzas fiscales PDF: tasa licencias urbanísticas, licencia apertura establecimientos.
- Edictos puntuales en urbanismo (p. ej. licencia ambiental taller mecánico, mayo 2026).
- Estrategia adapter: páginas informativas de trámites + posts WP con keyword licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `n_mun = 'Aldeatejada'`
  - Campo sector: `n_num_sect` (16 sectores con polígono: SUD-1, SUD-6, SUNC-2, AH-1, etc.)
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas WP por código de sector en título (SUD-3, SU-NC-01, UR-3R, …).
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - PDFs PGOU sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Municipio periurbano de Salamanca (~1.800 hab.); volumen alto de documentación PGOU en web pero sin API.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 5 entradas en CSV).
- Certificado SSL válido en web principal.
