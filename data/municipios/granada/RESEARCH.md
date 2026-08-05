# Granada — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.granada.org |
| Urbanismo, obras y licencias | https://www.granada.org/urbanismo.nsf/byclave/inicio |
| Planeamiento urbanístico (Lotus) | https://www.granada.org/urbanismo.nsf/vwplan |
| Avance PGOM | https://www.granada.org/urbanismo.nsf/byclave/avancepgom |
| Sede electrónica STA | https://sede.granada.org |
| Tablón edictos (desde mar-2025) | https://sede.granada.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON_EDICTOS |
| Tablón dataset (PTS2_TABLON) | https://sede.granada.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all |
| Catálogo trámites | https://sede.granada.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |
| Edictos IP urbanismo (legacy, vacío) | https://www.granada.org/inet/edictos.nsf/infpuburb |
| Visor GeoGranada | http://geoweb.granada.org/visorweb/util/xvisor_bienvenida.html |

**Nota:** `granada.sedelectronica.es` (espublico gestiona) devuelve “Sede Electrónica Indeterminada”. La sede activa es **sede.granada.org** (STA / T-Systems).

## Cómo se listan expedientes / proyectos

1. **Sede STA — tablón:** HTML con `var dataset_PTS2_TABLON = [...]` embebido (~52 filas, KEY=all). Campos: `descriptionProc`, `externString` (expediente), `pubDateIni`, `dboid`. Detalle vía `DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`.
2. **Web Lotus — planeamiento:** Vista jerárquica en `urbanismo.nsf/vwplan` con enlaces `!OpenDocument` a fichas de PGOU/PGOM, planes parciales, PEPRI, innovaciones (~18 documentos visibles).
3. **Avance PGOM:** Página estática con enlaces a memorias y planos PDF.
4. **Edictos anteriores a 20/03/2025:** Redirigidos a sede STA; el listado legacy `edictos.nsf` está vacío para IP urbanismo.

## Cómo se publican licencias

- **Tablón STA:** edictos de licencias y actividad mezclados con otros anuncios; filtro por texto en `descriptionProc`.
- **Catálogo STA:** ~94 trámites relacionados con licencias/obras/urbanismo (declaraciones responsables, comunicaciones previas, etc.) — páginas informativas, no histórico de concesiones.
- **No hay** listado público de expedientes de licencia con coordenadas ni visor enlazado por código de expediente.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **GeoGranada** (`geoweb.granada.org`): callejero municipal; descarga DWG/Shape de calles, sin capa de expedientes ni API REST/WFS.
  - **PGOM/PGOU:** documentación y planos en PDF en `urbanismo.nsf`; sin MapServer/FeatureServer público.
  - **Pgo.nsf** (visor PGOU 2001): navegador HTML de fichas, sin geometría descargable por expediente.
  - **sede.icagr.es** (cartografía provincial): enlace desde web municipal; no expone consulta por expediente urbanístico.
- **Estrategia:** el adapter no enriquece `geom_geojson`; el orquestador aplica centroide municipio + jitter.
- **Limitaciones:** planeamiento solo en PDF/HTML; tablón sin georreferencia; visor callejero no enlazable a filas del scrape.

## Limitaciones generales

- Sede STA: respuesta lenta (~30 s para tablón completo); SSL verificado con `sede_insecure_ssl` por compatibilidad.
- Web `granada.org` usa Lotus Notes/Domino (charset ISO-8859-1 en algunas páginas).
- Edictos pre-marzo-2025 no scrapeables desde `edictos.nsf` (redirección sin datos).
- Paginación planeamiento: solo ~18 entradas en vista actual (histórico concentrado en PGOU 2001 y avance PGOM).
