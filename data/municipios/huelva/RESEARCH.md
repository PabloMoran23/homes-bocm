# Huelva — investigación portal ayuntamiento

Municipio: **Huelva** (`huelva`) — capital de provincia, Andalucía (BOJA).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://sede.huelva.es/ | OpenSIAC / OpenCERTIAC (GADD) |
| Tablón edictos | https://sede.huelva.es/opensiac/action/custom?method=enter&page_index=1 | Índice tablones |
| Publicaciones OTROS | https://sede.huelva.es/opensiac/informacionpublica/infopublica.action?edictos=OTROS | Tablón municipal (~48 publicaciones) |
| Búsqueda AJAX | POST `infopublica_search.action` | `botonTodos` / `descripcionPublicacion` |
| Consultas públicas | https://sede.huelva.es/opensiac/informacionpublica/infopublica?method=enter&edictos=CP | IP expedientes urbanísticos |
| Licencias urbanismo | https://sede.huelva.es/opensiac/action/tramitesinfo?id=35&method=enter | Trámites obra mayor/menor, legalizaciones |
| Catálogo trámites | https://sede.huelva.es/opensiac/informacionpublica/tramites_enter.action | Urbanismo y Medio Ambiente |
| PGOU (web) | https://www.huelva.es/portal/plan-general-de-ordenación-urbana-y-modificaciones-puntuales-del-pgou | PDFs PGOU y modificaciones |
| PGOU histórico | https://www.huelva.es/portal/en/paginas/plan-general-de-ordenación-urbana | Memorias, planos, ordenanzas |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento general Andalucía |

## Cómo se listan expedientes

- **CMS:** OpenSIAC (Java/Struts) con codificación `iso-8859-15`.
- **Tablón:** formulario POST a `infopublica_search.action` devuelve tabla HTML con columnas título, fecha publicación, fecha fin, enlace `infopublica_ver.action?id=…`.
- **Detalle:** tabla `Etiqueta`/`Descripcion` con título, fechas y ficheros PDF (`infopublica_descargar.action`).
- **Categorías:** menú lateral con grupos (Urbanismo `#l86` tiene publicaciones puntuales); la tabla no incluye categoría.
- **Consultas públicas:** tablón separado (`edictos=CP`) para información pública de expedientes.
- **Licencias:** solo trámites informativos; no hay listado histórico de concesiones en sede.

## Cómo se publican licencias

- Trámite **Licencias Urbanismo** (id=35): formularios descargables para obra mayor/menor, legalizaciones, comunicación previa.
- Resoluciones puntuales en tablón edictos (categoría Urbanismo) cuando se publican.
- Sin dataset ni API de licencias concedidas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - `www.huelva.es` PGOU: solo PDFs/planos estáticos; **timeout SSL** desde entorno CI (no scrapeable).
  - SITUA/VITUA (Junta de Andalucía): consulta documental del PGOU vigente; sin WFS/ArcGIS enlazable a expedientes del tablón.
  - Sede OpenSIAC: publicaciones sin coordenadas ni enlace a visor cartográfico.
- **Estrategia:** no aplicable; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** capital con PGOU histórico (1999 + adaptación LOUA) en PDF; sin visor urbanístico municipal público con API; tablón sin georreferencia.

## Publicaciones urbanísticas encontradas (muestra)

| ID | Título | Fecha |
|----|--------|-------|
| 10614 | Modificación puntual PGOU — catálogo edificios | 2026-09-11 |
| 10613 | PRI "Cash Colombino" — aprobación inicial | 2026-09-11 |
| 10559 | Medidas cautelares — orden ejecución inmueble | — |
| 10670 | Consulta pública — ordenanza comercio ambulante | 2026-09-18 |

## Limitaciones

- `www.huelva.es` inaccesible por handshake SSL timeout (documentado; referencias estáticas).
- Tablón mayoritariamente personal/concursos; urbanismo requiere búsqueda por términos.
- Sin listado histórico de licencias concedidas.
- Encoding `iso-8859-15` en sede.
