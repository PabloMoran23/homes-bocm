# El Berrueco — investigación portal ayuntamiento

**Municipio:** El Berrueco (Comunidad de Madrid)  
**Fecha:** 2026-07-09  
**BOCM regional (referencia):** 17 avisos

## Resumen

El Berrueco publica anuncios y trámites en la **sede electrónica espublico gestiona**
(`elberrueco.sedelectronica.es`). La documentación de planeamiento (modificaciones de Normas
Subsidiarias, unidades de ejecución) se publica en el **portal de transparencia** y en
**VisualUrb** (agregador externo). Los ámbitos de planeamiento municipal están disponibles en el
**SIT de la Comunidad de Madrid** (WFS `sitcm:VPLA_V_AMBITO`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://elberrueco.sedelectronica.es/board/` | HTML tabla Wicket | Anuncios recientes (bandos, licencias ocupación, normativa) |
| Catálogo trámites | `https://elberrueco.sedelectronica.es/dossier` | HTML enlaces `/catalog/t/{uuid}` | Licencia urbanística, DRUO, certificados urbanísticos |
| Portal transparencia | `https://elberrueco.sedelectronica.es/transparency/` | Wicket AJAX | Sección **8. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE** (3 documentos) |
| Web municipal | `https://www.elberrueco.org/` | WordPress Enfold | Enlace a sede; REST API bloqueada (401) |
| VisualUrb | `https://www.visualurb.es/el-berrueco-...` | HTML | Publicación UE-10 «El Egio» (abril 2021) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | 16 ámbitos `DS_NOMB_AMB` para `DS_MUNICIPIO='EL BERRUECO'` |

## Tablón de anuncios (`/board/`)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document/{uuid}` (PDF). En julio 2026 el tablón muestra ~6 anuncios recientes
(bandos, subasta cinegética, reglamento honores); sin entradas de planeamiento activas.

## Licencias

- Trámites informativos en catálogo sede: *Solicitud de Licencia Urbanística*, *Declaración
  Responsable o Comunicación en Materia Urbanística*, *Solicitud de Licencia de Ocupación*, etc.
- No hay dataset histórico de concesiones con coordenadas.
- Anuncios de licencia aparecen en tablón cuando se publican (procedimiento *Licencias de Ocupación*
  u otros).

## Proyectos / planeamiento

- **Transparencia:** carpeta urbanismo con 3 documentos (PGOU/NNSS, modificaciones); navegación
  Wicket AJAX (tokens de sesión; no scrapeable de forma estable en CI).
- **VisualUrb:** publicación aprobación definitiva modificación puntual NNSS UE-10 «El Egio» (2021).
- **SIT WFS:** 16 ámbitos de ordenación (UE-1 a UE-15, SAU, etc.) con polígonos en EPSG:25830
  reprojectables a WGS84.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='EL BERRUECO'` (`srsName=EPSG:4326`)
  - No hay visor ArcGIS propio del ayuntamiento ni GeoJSON en datos abiertos locales
  - VisualUrb referencia publicaciones pero su API (`api-sig.visualurb.es`) no expone geometría
- **Estrategia:** Enriquecer proyectos con polígono WFS cuando el título contiene código UE/ámbito
  SIT; semillas de ámbitos desde WFS para cobertura de planeamiento municipal.
- **Limitaciones:** Tablón/PDF sin georreferenciación; transparencia Wicket no automatizable;
  licencias sin GIS enlazable.

## Limitaciones

- Portal transparencia: árbol Wicket con `wicketAjaxGet`; respuestas vacías sin sesión JS completa.
- WordPress REST (`/wp-json/`) devuelve 401.
- Tablón muestra solo anuncios recientes (~6 filas); histórico requiere búsqueda POST Wicket.
- `/info` redirige a `/info.0` (usable); `/dossier` accesible para catálogo.

## Estrategia adapter

1. Scrape tablón `/board/` (tabla + fallback enlaces).
2. Catálogo trámites urbanismo desde `/dossier`.
3. Semillas de ámbitos SIT WFS (16 UE/figuras) con `geom_geojson`.
4. Publicación VisualUrb UE-10 como proyecto documental.
5. Páginas informativas de referencia (tablón + trámites).
6. IDs: `el-berrueco-{lic|proy}-{sha256[:14]}`.
