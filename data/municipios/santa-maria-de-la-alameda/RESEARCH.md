# Santa María de la Alameda — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `santa-maria-de-la-alameda` |
| Provincia | Madrid (Sierra Oeste) |
| CCAA | Comunidad de Madrid |
| Boletín | BOCM (`bocm_count`: 8) |

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://santamariadelaalameda.com | WordPress + Elementor (Hello Elementor) |
| Avance PGOU | https://santamariadelaalameda.com/avance-plan-general/ | Noticia/página del avance del Plan General |
| Ordenanzas | https://santamariadelaalameda.com/portal-de-transparencia/normativa-municipal/ordenanzas/ | PDFs ordenanzas (licencias urbanísticas, IBI, etc.) |
| Trámites | https://santamariadelaalameda.com/portal-de-transparencia/tramites/ | Índice trámites (Tasas y Licencias Urbanísticas) |
| Tablón web | https://santamariadelaalameda.com/tablon-de-anuncios/ | Enlace a sede electrónica |
| Histórico bandos | https://santamariadelaalameda.com/tablon-de-anuncios/historico-bandos/ | Bandos históricos (limpieza parcelas, etc.) |
| Sede electrónica | https://santamariadelaalameda.sedelectronica.es | **espublico gestiona** (Wicket) |
| Tablón sede | https://santamariadelaalameda.sedelectronica.es/board/ | Tabla HTML con preview-document PDF |
| Catálogo trámites | https://santamariadelaalameda.sedelectronica.es/dossier | Catálogo procedimientos (licencias, urbanismo) |
| Transparencia sede | https://santamariadelaalameda.sedelectronica.es/transparency | Secciones urbanismo/actividades |

## Cómo se listan expedientes / proyectos

1. **Sede espublico — tablón** (`/board/`): tabla responsive con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces `preview-document/{uuid}` a PDF firmado. Categorías: Bandos, Anuncios, Urbanismo (cuando aplica).
2. **WordPress**: post «Avance Plan General» (2022-12-14); páginas de ordenanzas con enlaces PDF directos.
3. **Histórico bandos**: bandos municipales en PDF (limpieza de parcelas, etc.) — contenido urbanístico indirecto.
4. **No hay** visor de expedientes urbanísticos ni API JSON pública de proyectos.

## Cómo se publican licencias

- **No hay** dataset ni listado de concesiones individuales con coordenadas.
- Ordenanza reguladora de licencias urbanísticas (PDF en web).
- Trámites informativos en sede `/dossier` (solicitud licencia, comunicación previa, etc.).
- Tablón sede publica anuncios/bandos cuando procede; actualmente pocos ítems de licencia explícita.
- Estrategia adapter: páginas informativas + tablón + ordenanzas + formularios catálogo (patrón Pozuelo/Talamanca).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid SITCM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='SANTA MARÍA DE LA ALAMEDA'`
  - Campo nombre ámbito: `DS_NOMB_AMB` (códigos P-1…P-11: casco antiguo, ensanche, río Cofio, etc.)
- **Estrategia:** descarga WFS por municipio; matching por código P-N o ILIKE en título; polígonos en EPSG:4326.
- **Limitaciones:**
  - Ámbitos de planeamiento (NNSS/PGOU), no parcelas ni expedientes individuales.
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Tablón y PDFs sin georreferencia embebida.
  - El orquestador aplicará centroide municipio + jitter cuando no haya polígono.

## Limitaciones generales

- CMS WordPress Elementor; sin REST API de posts filtrable por categoría urbanismo de forma fiable.
- Sede espublico sin paginación masiva en tablón (pocos anuncios visibles).
- SSL sede válido; no requiere `insecure_ssl`.
- Dominio histórico `santamaria.deamescua.com` en bandos antiguos (enlaces rotos o legacy).

## Referencias de patrón

- Adapter similar: `talamanca_de_jarama.py`, `venturada.py`, `pedrezuela.py`
- WFS SITCM partial geometry (11 ámbitos únicos)
