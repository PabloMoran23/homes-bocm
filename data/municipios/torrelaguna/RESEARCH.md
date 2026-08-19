# Torrelaguna — investigación portal ayuntamiento

**Municipio:** Torrelaguna (Comunidad de Madrid)  
**Fecha:** 2026-08-07  
**BOCM regional (referencia):** 7 avisos

## Resumen

Torrelaguna publica trámites y anuncios en la **sede electrónica espublico gestiona**
(`torrelaguna.sedelectronica.es`) y documentación de urbanismo en la **web municipal WordPress
Extra** (`torrelaguna.es`). Los ámbitos de planeamiento están en el **SIT de la Comunidad de
Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://torrelaguna.es` | WordPress Extra | Noticias, ordenanzas, impresos |
| Ordenanzas urbanismo | `https://torrelaguna.es/ordenanzas-urbanismo/` | HTML + PDF | Ordenanzas licencia, DR, ICIO, etc. |
| Impresos y trámites | `https://torrelaguna.es/impresos-y-tramites/` | HTML + PDF | Declaración responsable urbanística |
| Tablón de anuncios | `https://torrelaguna.sedelectronica.es/board` | HTML tabla espublico | Anuncios recientes (convenio UE-9, etc.) |
| Bandos | `https://torrelaguna.es/category/bandos/` | WordPress | Bandos y anuncios municipales |
| Portal transparencia | `https://torrelaguna.sedelectronica.es/transparency` | Wicket | Sin sección urbanismo scrapeable |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | ~36 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='TORRELAGUNA'` |
| Visor SIT CM | `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm` | HTML | Visor regional de planeamiento |

## Tablón de anuncios (`/board`)

Tabla HTML responsive con columnas: Documento, Expediente, Procedimiento, Categoría,
Descripción, Fecha de Publicación. Enlaces `preview-document/{uuid}` (PDF). En agosto 2026
constan anuncios de urbanismo (p. ej. propuesta de convenio urbanístico UE-9) junto a
resoluciones de empleo público.

## Licencias

- **Ordenanzas urbanismo:** PDFs en `/pdf/ordenanzas/web/` (licencia y declaración responsable BOCM 2022, ICIO, etc.).
- **Impresos WP:** modelo declaración responsable urbanística (`wp-content/uploads/2022/11/`).
- **Sede `/board`:** anuncios de licencias cuando se publican.
- No hay dataset histórico de concesiones con coordenadas.

## Proyectos / planeamiento

- **Ordenanzas:** 9 PDFs de ordenanzas urbanísticas en la página de urbanismo.
- **SIT WFS:** 36 ámbitos únicos UE-*, SAU-* con polígonos WGS84.
- **Bandos WP:** anuncios de licitación parcelas urbanas, plan renovación urbana, etc.
- **Tablón sede:** convenios urbanísticos (UE-9) y actuaciones urbanísticas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='TORRELAGUNA'` (`srsName=EPSG:4326`)
  - Visor regional SIT CM: `https://idem.comunidad.madrid/cartografia/sitcm/html/visor.htm`
  - Ordenanzas PDF (sin georreferenciación vectorial)
- **Estrategia:** Semillas de ámbitos desde WFS; enriquecer por código UE/SAU en título cuando
  coincida con `DS_NOMB_AMB`.
- **Limitaciones:** Sin visor ArcGIS propio del ayuntamiento; tablón con pocos anuncios
  urbanísticos; licencias sin GIS enlazable; transparencia Wicket sin scrape estable.

## Limitaciones

- No hay página dedicada «Normas subsidiarias»; planeamiento en ordenanzas PDF.
- Impresos concentrados en una sola página (sin CPT impresos con sitemap).
- Tablón mezcla urbanismo con empleo público y presupuestos.

## Estrategia adapter

1. Scrape tablón `/board` (tabla data-label + fallback enlaces preview-document).
2. Impresos y trámites desde `/impresos-y-tramites/`.
3. PDFs ordenanzas urbanismo como proyectos de planeamiento.
4. Bandos WP con filtro urbanismo/licencias.
5. Semillas de ámbitos SIT WFS con `geom_geojson`.
6. Páginas informativas de referencia (tablón, ordenanzas, impresos).
7. IDs: `torrelaguna-{lic|proy}-{sha256[:14]}`.
