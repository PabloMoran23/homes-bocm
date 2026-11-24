# Bormujos — investigación portal ayuntamiento

**Municipio:** Bormujos (Sevilla, Andalucía)  
**Slug:** `bormujos`  
**Boletín:** sin boletín regional asociado en cola

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.bormujos.es | **Operativa** — SagaSuite (tema Diputación Sevilla) |
| Urbanismo (delegación) | https://www.bormujos.es/ayuntamiento/delegacionesmunicipales/urbanismo/ | Información de competencias |
| Tema Urbanismo y Obras | https://www.bormujos.es/temas/urbanismo-y-obras/ | Contenido informativo + PDF export |
| E-Tablón embebido | https://www.bormujos.es/actualidad/etablon | **Operativa** — iframe/proxy tablón INPRO |
| Sede GSede | https://sede.bormujos.es | **Operativa** — OpenCMS / Guadaltel |
| Tablón INPRO | https://sede.bormujos.es/tablon-1.0/do/entradaPublica?ine=41017 | **Operativa** — INE **41017** (no confundir con 41018) |
| Sede electrónica nueva | https://bormujos.sedelectronica.es | **Operativa** — board + transparency |
| Tablón board | https://bormujos.sedelectronica.es/board | Anuncios administrativos (HTML tabla) |
| Portal transparencia | https://transparencia.bormujos.es | **Login obligatorio** (401/302 a login) |
| Indicadores PGOU (suffix 00017) | URLs tipo `.../indicador/Plan-General-de-Ordenacion-Urbana-...-00017/` | **401** sin credenciales |
| Licyt@l Diputación | https://sedeelectronicadipusevilla.es/LicytalSede/jsp/index.faces?cif=P4101700E | Contratación local (no licencias obra) |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41017 | Planeamiento aprobado (documentos PDF) |

**Nota:** La antigua sede OpenCMS (`sede.bormujos.es/opencms/...`) convive con la nueva `bormujos.sedelectronica.es` (desde ~2024).

## Tablón electrónico INPRO

- **CMS:** INPRO tablón-1.0 (INPRO S.A. / Diputación Sevilla), parámetro `ine=41017`.
- **Listado:** formulario de búsqueda + tabla `displaytag` cuando hay edictos vigentes.
- **Estado nov 2026:** sin filas en listado público (0 edictos en grid); el adapter mantiene el scraper para cuando haya publicaciones.
- **Asuntos urbanismo disponibles en filtro:** ANUNCIO, aprobación ordenanzas, LICENCIA DE APERTURA, etc.

## PGOU y planeamiento

- PDF informativo del portal: `/pdflink/.../Urbanismo-y-Obras-Contenido-de-Urbanismo-y-Obras.pdf`.
- Indicadores de transparencia (PGOU, modificaciones, convenios) existen con sufijo municipal `00017` pero el portal exige autenticación.
- **SITUA** (Junta de Andalucía) expone documentación de planeamiento por municipio (INE 41017).

## Licencias de obra

- No hay registro público scrapeable de licencias concedidas (Licyt@l = contratación).
- Licencias aparecerían en tablón INPRO o board sedeelectronica; actualmente sin entradas urbanísticas explícitas.
- El adapter incluye páginas informativas (tablón, sede, Licyt@l) como en Marchena/Pozuelo.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** PDFs informativos y SITUA (documentos raster); transparencia con planos PGOU no accesible sin login.
- **Estrategia:** no hay visor ArcGIS/WFS público enlazable por código de expediente en el portal municipal.
- **Limitaciones:** planos en PDF; tablón/board sin georreferencia; transparencia restringida.

## Limitaciones generales

- Tablón INPRO vacío en el listado público (nov 2026).
- Transparencia SagaSuite con login (401).
- Board sedeelectronica mayoritariamente RRHH/subvenciones/pleno (filtrado en adapter).
- Codificación tablón ISO-8859-1.

## Adapter implementado

- `municipio.adapters.bormujos:BormujosAyuntamientoAdapter`
- Fuentes: tablón INPRO + e-tablon + board sedeelectronica + PDF web + SITUA (+ transparencia si accesible).
- IDs: `bormujos-lic-*` / `bormujos-proy-*` (sha256[:14]).
