# El Atazar — investigación portal ayuntamiento

**Municipio:** El Atazar (Comunidad de Madrid)  
**Fecha investigación:** 2026-08-27  
**Portal base:** https://elatazar.org

## Resumen

El Atazar es un municipio muy pequeño (~107 habitantes) de la Sierra Norte de Madrid.
Publica normativa urbanística y formularios de trámites en su **web municipal WordPress**
(`elatazar.org`, tema Elementor) y dispone de **sede electrónica espublico gestiona**
(`elatazar.sedelectronica.es`). El planeamiento urbanístico municipal (PGOU) se gestiona
a través de la **Mancomunidad de Servicios de Arquitectura y Urbanismo Sierra Norte (MSAU)**.

## URLs base y páginas semilla

| Recurso | URL | Formato | Contenido |
|---------|-----|---------|-----------|
| Web municipal | `https://elatazar.org` | WordPress (Elementor) | Portal principal |
| Urbanismo | `https://elatazar.org/urbanismo/` | HTML estático | Servicios técnicos MSAU, PGOU, PIC catastral |
| Impresos y trámites | `https://elatazar.org/impresos-y-tramites/` | HTML + PDFs | Actuación comunicada, licencia obra menor, solicitud general |
| Normativa | `https://elatazar.org/normativa/` | HTML + PDFs | Ordenanzas fiscales (tasa licencias urbanísticas, ICIO, tráfico casco urbano) |
| Sede electrónica | `https://elatazar.sedelectronica.es` | espublico gestiona | Trámites, tablón, transparencia |
| Tablón sede | `https://elatazar.sedelectronica.es/board/` | HTML Wicket/YUI | Tablón de anuncios (vacío ago 2026) |
| Transparencia sede | `https://elatazar.sedelectronica.es/transparency/` | Wicket | Portal transparencia |
| MSAU Sierra Norte | `https://www.msau-sierranorte.es/` | Web mancomunidad | PGOU y servicios técnicos compartidos |
| Plan Embalse Atazar | `https://www.comunidad.madrid/publicacion/ref/3509` | PublicaMadrid | Plan de Ordenación del Embalse (ámbito regional) |
| Visor SITCM | `https://idem.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/SITCM | Consulta visual planeamiento CCAA |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | WFS GeoJSON | **0 ámbitos** para `DS_MUNICIPIO='EL ATAZAR'` |

## Cómo se listan expedientes / proyectos

- **Urbanismo:** página informativa con referencia al PGOU vía MSAU; sin listado de expedientes.
- **Normativa:** PDFs de ordenanzas fiscales y reglamentos (tasa licencias urbanísticas, ICIO, tráfico casco urbano).
- **Impresos:** formularios PDF descargables (actuación comunicada, licencia obra menor).
- **Posts WordPress:** noticias ocasionales (p. ej. obras en carretera M-133); sin categoría urbanismo dedicada.
- **Tablón sede:** tabla HTML con `emptyRow` (sin anuncios publicados online).
- **No hay** visor urbanístico municipal ni listado estructurado de expedientes IP.

## Cómo se publican licencias

- **No hay dataset** ni listado de licencias concedidas (tablón vacío).
- Formularios informativos en `/impresos-y-tramites/`:
  - Solicitud de actuación comunicada
  - Solicitud licencia de obra menor
  - Solicitud general
- Ordenanza fiscal reguladora de tasa por licencias urbanísticas en `/normativa/`.
- Trámites en sede (`/dossier`, `/expedientes`) requieren identificación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Visor SITCM (`idem.madrid.org/cartografia/sitcm/html/visor.htm`) — consulta visual sin API por expediente
  - WFS `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='EL ATAZAR'` → **0 features** (verificado 2026-08-27)
- **Estrategia:** sin polígonos descargables; el orquestador aplicará centroide municipio + jitter
- **Limitaciones:** municipio rural sin ámbitos de planeamiento digitalizados en SITCM; PGOU gestionado externamente por MSAU

## Limitaciones

- Tablón de anuncios sede vacío (sin licencias ni IP publicadas online).
- Sin sección de expedientes ni visor urbanístico propio.
- SITCM sin geometrías para el municipio.
- SSL sede gestionado por espublico (adapter usa `insecure_ssl: true`).
- Urbanismo externalizado a Mancomunidad MSAU (cita previa por teléfono).

## Patrón adapter

1. Crawl semillas WP (`urbanismo`, `impresos-y-tramites`, `normativa`) + búsqueda REST API.
2. Referencias PGOU (MSAU) y Plan Ordenación Embalse (Comunidad de Madrid).
3. Tablón sede espublico (vacío; preparado para preview-document).
4. Licencias: formularios informativos de trámites (sin listado de concesiones).
5. IDs: `el-atazar-{lic|proy}-{sha256[:14]}`.
