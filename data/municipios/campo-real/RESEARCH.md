# Campo Real — investigación portal ayuntamiento

**Municipio:** Campo Real (Comunidad de Madrid)  
**Fecha:** 2026-08-08  
**BOCM regional (referencia):** 6 avisos

## Resumen

Campo Real publica trámites y modelos de licencia en la **web corporativa Joomla** (`camporeal.es`)
y anuncios en la **sede electrónica espublico gestiona** (`camporeal.sedelectronica.es`).
Los ámbitos de planeamiento municipal (unidades de actuación UA-* y suelo urbanizable SAU-*)
están en el **SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`, código municipio 033).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web urbanismo | `https://www.camporeal.es/concejalias/urbanismo-y-obras-publicas` | Joomla HTML + PDFs | Modelos licencia obra, primera ocupación, segregación, vados, ordenanzas |
| Tablón de anuncios | `https://camporeal.sedelectronica.es/board/` | HTML tabla Wicket | Bandos, anuncios municipales (~10 filas recientes) |
| Catálogo trámites | `https://camporeal.sedelectronica.es/dossier` | HTML enlaces `/catalog/t/{uuid}` | Licencia urbanística, DR, certificados (acceso lento/redirect) |
| Portal transparencia | `https://camporeal.sedelectronica.es/transparency` | Wicket AJAX | Carpeta «7. URBANISMO…» (29 docs; requiere AJAX, no scrapeable) |
| Visor SITCM | `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm?municipio=033` | Visor web CM | Planeamiento municipal Campo Real |
| SIT WFS | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 29 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='CAMPO REAL'` |
| Visor planeamiento CM | `http://www.madrid.org/cartografia/planea/planeamiento/html/visor.htm` | Enlace desde web | Visor regional de planeamiento |

## Tablón de anuncios (`/board/`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.
Enlaces `preview-document/{uuid}` (PDF). En agosto 2026 el tablón muestra ~9 anuncios recientes
(empleo público, bandos informativos); sin entradas de licencias urbanísticas con coordenadas.

## Licencias

- Modelos PDF en web Joomla: licencia de obra, primera ocupación, segregación, autoalineación, vados, etc.
- Ordenanza reguladora licencia/DR publicada en BOCM (PDFs en `/images/noticias/` y `/images/archivos/`).
- Trámites informativos en catálogo sede `/dossier` (redirect 302; acceso intermitente desde CI).
- No hay dataset histórico de concesiones con coordenadas ni listado de licencias otorgadas.

## Proyectos / planeamiento

- **Web Joomla:** formularios y ordenanzas urbanísticas en `/concejalias/urbanismo-y-obras-publicas`.
- **SIT WFS:** 29 ámbitos (UA-1 a UA-21, SAU-R1 a SAU-R6, SAU-I1) con polígonos en WGS84.
- **Tablón sede:** bandos informativos (sin planeamiento detallado en el momento de la investigación).
- **Transparencia:** 29 documentos en carpeta urbanismo (Wicket AJAX; no extraíbles sin sesión).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='CAMPO REAL'` (`srsName=EPSG:4326`)
  - Visor SITCM Comunidad de Madrid `municipio=033` (sin API directa por expediente)
  - No hay visor ArcGIS propio del ayuntamiento ni GeoJSON en datos abiertos locales
- **Estrategia:** Semillas de ámbitos SIT WFS con `geom_geojson`; enriquecer por código UA-/SAU- en títulos.
- **Limitaciones:** Tablón/PDF sin georreferenciación; transparencia Wicket no scrapeable;
  licencias sin GIS enlazable; `/dossier` con redirect y latencia alta.

## Limitaciones

- Portal transparencia: subcarpetas Wicket con `wicketAjaxGet`; no accesibles sin interacción.
- Tablón muestra solo anuncios recientes (~9 filas); histórico requiere búsqueda POST Wicket.
- `/dossier` devuelve 302 y puede agotar timeout en entornos cloud.
- Sin listado público de licencias otorgadas con dirección/coordenadas.

## Estrategia adapter

1. Scrape web Joomla urbanismo (PDFs licencia, segregación, vados, ordenanzas).
2. Scrape tablón `/board/` (tabla data-label + fallback preview-document).
3. Catálogo trámites urbanismo desde `/dossier` (con timeout extendido).
4. Semillas de ámbitos SIT WFS (29 UA-/SAU-) con `geom_geojson`.
5. Páginas informativas de referencia (tablón + trámites + urbanismo web).
6. IDs: `campo-real-{lic|proy}-{sha256[:14]}`.
