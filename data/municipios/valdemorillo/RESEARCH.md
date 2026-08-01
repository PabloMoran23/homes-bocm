# Valdemorillo — investigación portal ayuntamiento

**Municipio:** Valdemorillo (Comunidad de Madrid)  
**Fecha:** 2026-07-24  
**BOCM regional (referencia):** 14 avisos

## Resumen

Valdemorillo publica trámites y anuncios en la **sede electrónica espublico gestiona**
(`aytovaldemorillo.sedelectronica.es`) y documentación de planeamiento en la **web municipal
WordPress** (`aytovaldemorillo.com/urbanismo/`). Los ámbitos de planeamiento están en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web urbanismo | `https://aytovaldemorillo.com/urbanismo/` | WordPress HTML | Formularios trámites (enlaces `/catalog/t/{uuid}`), NNSS PDFs |
| Tablón de anuncios | `https://aytovaldemorillo.sedelectronica.es/board` | HTML tabla | Anuncios recientes (PGOU avance, padrones vados, etc.) |
| Catálogo trámites | `https://aytovaldemorillo.sedelectronica.es/catalog/t/{uuid}` | HTML sede | Licencias, declaraciones responsables, planeamiento |
| Portal transparencia | `https://aytovaldemorillo.sedelectronica.es/transparency/` | Wicket AJAX | Sección **URBANISMO, URBANIZACIONES, OBRAS PÚBLICAS Y MEDIO AMBIENTE** |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | ~22 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='VALDEMORILLO'` |

## Tablón de anuncios (`/board`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}` (PDF). En julio 2026 incluye avance PGOU (exp. 2932/2026),
padrones de vados y otros anuncios administrativos.

## Licencias

- Trámites informativos enlazados desde `/urbanismo/`: licencia obra mayor/menor, declaraciones
  responsables, segregación/agrupación, etc. (~24 procedimientos).
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia/vados aparecen en tablón cuando se publican.

## Proyectos / planeamiento

- **NNSS:** 9 PDFs en `wp-content/uploads/2022/02/` (acuerdo, catálogo, memoria, planos).
- **PGOU avance:** bando e información pública en tablón (mayo 2026).
- **SIT WFS:** ámbitos UA-*, SAU-*, UA AMPLIACIÓN CERRO ALARCÓN, etc. con polígonos WGS84.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='VALDEMORILLO'` (`srsName=EPSG:4326`)
  - Visor regional SIT CM: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm`
  - No hay visor ArcGIS propio del ayuntamiento ni GeoJSON en datos abiertos locales
- **Estrategia:** Semillas de ámbitos desde WFS; enriquecer por código UA/SAU en título cuando
  coincida con `DS_NOMB_AMB`.
- **Limitaciones:** Tablón/PDF sin georreferenciación; transparencia Wicket no automatizable;
  licencias sin GIS enlazable; `/dossier` y home sede con bucle de redirección 302.

## Limitaciones

- Portal transparencia: árbol Wicket con sesión JS; no scrapeable de forma estable en CI.
- Tablón muestra solo anuncios recientes (~9 filas); sin paginación pública accesible.
- Dominio `www.valdemorillo.es` no resuelve DNS; web oficial es `aytovaldemorillo.com`.

## Estrategia adapter

1. Scrape tablón `/board` (tabla data-label + fallback enlaces).
2. Trámites urbanismo desde página WordPress `/urbanismo/`.
3. PDFs NNSS como proyectos de planeamiento.
4. Semillas de ámbitos SIT WFS con `geom_geojson`.
5. Páginas informativas de referencia (tablón, urbanismo, transparencia).
6. IDs: `valdemorillo-{lic|proy}-{sha256[:14]}`.
