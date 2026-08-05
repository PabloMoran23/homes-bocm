# Lozoya — investigación portal ayuntamiento

**Municipio:** Lozoya (Comunidad de Madrid)  
**Fecha investigación:** 2026-08-03  
**Portal base:** https://www.lozoya.es

## Resumen

Lozoya publica normativa urbanística y trámites en su **web municipal WordPress**
(`www.lozoya.es`) y gestiona expedientes en la **sede electrónica espublico gestiona**
(`lozoya.sedelectronica.es`). No hay sección dedicada de urbanismo; el contenido está
disperso en ordenanzas, impresos descargables y noticias/posts del CMS.

## URLs base y páginas semilla

| Recurso | URL | Formato | Contenido |
|---------|-----|---------|-----------|
| Web municipal | `https://www.lozoya.es` | WordPress (Vantage) | Portal principal |
| Ordenanzas | `https://www.lozoya.es/ordenanzas/` | collapse-o-matic + PDFs | Ordenanzas fiscales y reglamentos (incl. tasa licencia urbanística, residuos construcción) |
| Impresos | `https://www.lozoya.es/descarga-de-impresos/` | HTML + PDFs | Solicitud licencia de obras, DR urbanística actividad |
| Transparencia WP | `https://www.lozoya.es/portal-de-transparencia/` | WordPress | Enlace a sede transparencia |
| Sede electrónica | `https://lozoya.sedelectronica.es` | espublico gestiona | Trámites, expedientes, tablón |
| Tablón sede | `https://lozoya.sedelectronica.es/board/` | HTML espublico | Tablón de anuncios (vacío ago 2026) |
| Transparencia sede | `https://lozoya.sedelectronica.es/transparency/` | Wicket | Portal transparencia |
| Visor planeamiento | `https://idem.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/SITCM | Enlace desde menú WP (consulta visual) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | **0 ámbitos** para `DS_MUNICIPIO='LOZOYA'` |

## Cómo se listan expedientes / proyectos

- **Ordenanzas:** secciones `collapse-o-matic` (ORDENANZAS FISCALES, REGLAMENTOS) con enlaces PDF.
- **Posts WordPress:** noticias históricas sobre NNSS, modificaciones puntuales, anuncios urbanismo
  (p. ej. `anuncio-modificacion-normas-subsidiarias-urbanismo`, `781-2` modificación NNSS manzanas 27-28).
- **API REST:** `https://www.lozoya.es/wp-json/wp/v2/posts?search=...` para búsqueda por términos urbanísticos.
- **Tablón sede:** tabla HTML con preview-document (actualmente sin filas).
- **No hay** listado estructurado de expedientes IP ni visor con ficha por código.

## Cómo se publican licencias

- **No hay dataset** de licencias concedidas ni listado en tablón (vacío).
- Trámites informativos en `/descarga-de-impresos/`:
  - Solicitud de licencia de obras (`licencia-obrasimpreso.pdf`)
  - DR urbanística actividad y funcionamiento (2026)
  - Cambio titularidad licencia de actividad
- Ordenanza tasa licencia urbanística en `/ordenanzas/`.
- Trámites en sede electrónica (`/dossier`, `/expedientes`) requieren identificación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Visor SITCM (`idem.madrid.org/cartografia/sitcm/html/visor.htm`) — consulta visual sin API pública por expediente
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='LOZOYA'` → **0 features** (verificado 2026-08-03)
- **Estrategia:** sin polígonos descargables; el orquestador aplicará centroide municipio + jitter
- **Limitaciones:** municipio pequeño sin ámbitos de planeamiento digitalizados en SITCM; visor solo informativo

## Limitaciones

- Tablón de anuncios sede vacío (sin licencias ni IP publicadas online).
- Sin sección urbanismo dedicada; contenido en posts dispersos (~6500 entradas WP).
- SITCM sin geometrías para el municipio.
- SSL sede con certificado gestionado por espublico (adapter usa `insecure_ssl: true`).

## Patrón adapter

1. Crawl semillas WP (`ordenanzas`, `impresos`, `transparencia`) + búsqueda REST API.
2. Parse collapse-o-matic y enlaces PDF.
3. Tablón sede espublico (preview-document).
4. Licencias: páginas informativas de trámites (sin listado de concesiones).
5. IDs: `lozoya-{lic|proy}-{sha256[:14]}`.
