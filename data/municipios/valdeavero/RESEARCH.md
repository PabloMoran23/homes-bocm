# Valdeavero — investigación portal ayuntamiento

**Municipio:** Valdeavero (Comunidad de Madrid)  
**Fecha:** 2026-08-23  
**BOCM regional (referencia):** 3 avisos

## Resumen

Valdeavero publica noticias y trámites informativos en la **web corporativa WordPress TownPress**
(`ayuntamientovaldeavero.es`) y anuncios en la **sede electrónica espublico gestiona**
(`valdeavero.sedelectronica.es`).
Los ámbitos de planeamiento municipal (sectores A-1, B-1…B-10, suelo urbano)
están en el **SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`, código municipio 156).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web corporativa | `https://ayuntamientovaldeavero.es` | WordPress TownPress | Noticias, plan de vivienda, cita previa urbanismo |
| Cita previa urbanismo | `https://ayuntamientovaldeavero.es/cita-previa-tecnico-de-urbanismo/` | HTML | Información y cita con técnico municipal |
| Plan de vivienda | `https://ayuntamientovaldeavero.es/plan-de-vivienda-valdeavero/` | HTML + PDFs | Registro demanda vivienda, captación suelo |
| Ordenanzas (sitemap) | `https://ayuntamientovaldeavero.es/attachment-sitemap.xml` | XML sitemap | Ordenanzas fiscales y urbanísticas (instalaciones, ocupación suelo, etc.) |
| Tablón de anuncios | `https://valdeavero.sedelectronica.es/board` | HTML tabla Wicket | Bandos y anuncios (~10 filas recientes) |
| Catálogo trámites | `https://valdeavero.sedelectronica.es/dossier` | HTML enlaces `/catalog/t/{uuid}` | Trámites informativos (acceso lento) |
| Portal transparencia | `https://valdeavero.sedelectronica.es/transparency` | Wicket AJAX | Carpeta «7. URBANISMO…» (16 docs; requiere AJAX) |
| Consulta expedientes | `https://valdeavero.sedelectronica.es/expedientes` | Wicket | Consulta individual (sin listado masivo) |
| Visor SITCM | `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=156` | Visor web CM | Planeamiento municipal Valdeavero |
| SIT WFS | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 12 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='VALDEAVERO'` |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.
Enlaces `preview-document/{uuid}` (PDF). En agosto 2026 incluye convenio abastecimiento agua urbanizaciones
«La Cardosa» y «Los Cerezos»; sin licencias urbanísticas con coordenadas.

## Licencias

- Cita previa con técnico de urbanismo en web WordPress.
- Ordenanzas urbanísticas (instalaciones y obras, ocupación suelo, servicios urbanísticos) en attachment-sitemap.
- Trámites informativos en catálogo sede `/dossier` (redirect/latencia alta).
- No hay dataset histórico de concesiones con coordenadas ni listado de licencias otorgadas.

## Proyectos / planeamiento

- **SIT WFS:** 12 ámbitos (A-1, B-1…B-10, B-6.1, B-6.2) suelo urbano con polígonos en WGS84.
- **Tablón sede:** convenio proyecto abastecimiento agua urbanizaciones.
- **Web:** Plan de Vivienda Valdeavero (2026).
- **Transparencia:** 16 documentos en carpeta urbanismo (Wicket AJAX; no extraíbles sin sesión).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='VALDEAVERO'` (`srsName=EPSG:4326`)
  - Visor SITCM Comunidad de Madrid `municipio=156` (sin API directa por expediente)
  - No hay visor ArcGIS propio del ayuntamiento ni GeoJSON en datos abiertos locales
- **Estrategia:** Semillas de ámbitos SIT WFS con `geom_geojson`; enriquecer por código A-/B- en títulos.
- **Limitaciones:** Tablón/PDF sin georreferenciación; transparencia Wicket no scrapeable;
  licencias sin GIS enlazable; `/dossier` con latencia alta.

## Limitaciones

- Portal transparencia: subcarpetas Wicket con `wicketAjaxGet`; no accesibles sin interacción.
- Tablón muestra solo anuncios recientes (~10 filas).
- `/dossier` puede agotar timeout en entornos cloud.
- Sin listado público de licencias otorgadas con dirección/coordenadas.

## Estrategia adapter

1. Scrape web WordPress (cita previa urbanismo, plan vivienda, ordenanzas del sitemap).
2. Scrape tablón `/board` (tabla data-label + fallback preview-document).
3. Catálogo trámites urbanismo desde `/dossier` (con timeout extendido).
4. Semillas de ámbitos SIT WFS (12 A-/B-) con `geom_geojson`.
5. Páginas informativas de referencia (tablón + trámites + visor SITCM).
6. IDs: `valdeavero-{lic|proy}-{sha256[:14]}`.
