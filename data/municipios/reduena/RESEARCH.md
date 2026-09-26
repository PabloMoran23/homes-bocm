# Redueña — investigación portal ayuntamiento

**Municipio:** Redueña (Comunidad de Madrid, provincia Madrid)  
**INE:** 28121 / CD_MUNICIPIO SITCM: 121  
**Fecha:** 2026-09-01  
**BOCM regional (referencia):** 2 avisos

## Resumen

Redueña es un municipio pequeño de la Comunidad de Madrid (Sierra Norte). La **web oficial**
(`www.reduena.com`) usa WordPress con tema Freepress. La **sede electrónica**
(`reduena.sedelectronica.es`) usa **espublico gestiona** con tablón de anuncios y portal de
transparencia. No hay visor urbanístico municipal propio; la geometría de ámbitos de planeamiento
está disponible en el WFS SITCM de la Comunidad de Madrid.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.reduena.com/` | WordPress REST + HTML | Urbanismo, normas subsidiarias, licencias |
| Urbanismo | `https://www.reduena.com/servicios-municipales/urbanismo/` | HTML | Enlaces a normas, licencias, sede |
| Normas subsidiarias | `https://www.reduena.com/normas-subsidiarias/` | HTML + 8 PDFs | NNSS aprobada 2023 (memoria, planos, catálogo) |
| Licencias de obras | `https://www.reduena.com/licencias-de-obras/` | HTML + PDFs | Formularios obra mayor, declaración responsable |
| Sede electrónica | `https://reduena.sedelectronica.es/` | espublico gestiona | Inicio, tablón, transparencia |
| Tablón anuncios | `https://reduena.sedelectronica.es/board/` | HTML tabla Wicket | **Vacío** en septiembre 2026 |
| Transparencia | `https://reduena.sedelectronica.es/transparency/` | HTML estático | Secciones normativa/documentación |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS 2.0 | 13 ámbitos `DS_MUNICIPIO='REDUEÑA'` |

## Normas subsidiarias (web)

Página `normas-subsidiarias` (categoría WP Urbanismo, feb 2023) con documentación PDF:

- Normas urbanísticas, Acuerdo, Catálogo, Índice, Memoria
- Planos catálogo, información y ordenación

## Licencias

- No hay dataset histórico de concesiones con coordenadas.
- Formularios en web: licencia obra mayor (PDF 2023), declaración responsable urbanística (2024).
- Tablón de anuncios sin filas en el momento de la investigación.
- Trámites informativos vía sede y formularios WP.

## Proyectos / planeamiento

- **NNSS:** Documentación completa en web (8 PDFs, feb 2023).
- **SITCM WFS:** 13 ámbitos con polígonos:
  - UE-01 a UE-07 (unidades de ejecución)
  - SAU-R.1 a SAU-R.5, SAU-I.1 (sectores de actuación urbanizable)
- **Tablón:** Sin anuncios de planeamiento publicados actualmente.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='REDUEÑA'` — 13 polígonos en EPSG:4326.
  Campos: `DS_NOMB_AMB` (código ámbito), `DS_FIG_DES` (figura de planeamiento).
- **Estrategia:** Descarga directa WFS por municipio; enriquecimiento por código ámbito (UE-*, SAU-*)
  en títulos de proyectos.
- **Limitaciones:** Sin visor municipal interactivo; tablón sin georreferenciación; licencias solo
  como trámites/formularios sin coords.

## Limitaciones

- Tablón de anuncios vacío (sin histórico paginado accesible).
- `/dossier` de sede no responde o timeout en el entorno de scraping.
- Sin publicación de licencias concedidas con ubicación.
- Geometría solo para ámbitos de planeamiento en SITCM, no para expedientes individuales.

## Estrategia adapter

1. Crawl WP: urbanismo, normas subsidiarias (PDFs), licencias de obras.
2. WP REST categoría Urbanismo (id 25).
3. Tablón sede `/board` (si hay filas).
4. WFS SITCM: 13 ámbitos como proyectos con `geom_geojson`.
5. Licencias: páginas informativas + formularios PDF.
6. IDs: `reduena-{lic|proy}-{sha256[:14]}`.
