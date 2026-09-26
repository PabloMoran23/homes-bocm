# Burjassot — investigación portal ayuntamiento

**Municipio:** Burjassot (Valencia, Comunitat Valenciana)  
**Slug:** `burjassot`  
**INE:** 46078  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.burjassot.org | **Operativa** — WordPress + UberMenu |
| Urbanismo | https://www.burjassot.org/urbanismo/ | PDFs PGOU, encuestas paisaje, planos |
| Trámites urbanismo | https://www.burjassot.org/tramites/urbanisme/ | Información trámites |
| Sede electrónica STA | https://sede.burjassot.org/sta/CarpetaPublic/ | **Operativa** — plataforma STA |
| Tablón edictos | `PAGE_CODE=PTS2_TABLON` | JSON embebido `dataset_PTS2_TABLON` (~188 filas) |
| Catálogo trámites | `PAGE_CODE=CATALOGO` | Trámites urbanismo y vivienda (licencias obra, vía pública) |
| Portal transparencia | https://transparencia.burjassot.org | WordPress — sección urbanismo y medioambiente |
| Expedientes planeamiento | https://transparencia.burjassot.org/urbanismo-y-medioambiente/2-desarrollo-y-gestion-delplan/ | 9+ expedientes activos (mod. PGOU, estudios detalle, PAI) |
| PGOU aprobado | https://transparencia.burjassot.org/urbanismo-y-medioambiente/plan-general-de-ordenacion-urbana/pgou-aprovat-definitivament/ | ZIP/PDF en archivo.burjassot.org |
| Visor urbanismo | http://urbanismo.burjassot.org/es | **No accesible** desde entorno cloud (DNS/timeout) |

## Tablón de anuncios (STA)

- **CMS:** Sede STA propia (`sede.burjassot.org`), no Dival ni espublico.
- **Listado:** HTML con array JavaScript `var dataset_PTS2_TABLON = [...]` (~188 anuncios).
- **Campos:** `descriptionProc`, `pubDateIni`, `dboid`, `remitent`.
- **Paginación:** Todo el dataset en una sola carga (~200 KB HTML, ~40 s descarga).
- **Filtrado urbanismo:** ~3 edictos licencias/zanjas; ~15–20 proyectos tras filtrar ruido (subvenciones, tasas, empleo).

### Ejemplos tablón (urbanismo)

| Título | Tipo |
|--------|------|
| Suspensión temporal otorgamiento licencias zanjas | Licencia / edicto |
| Modificación ordenanza usos residencial plurifamiliar | Ordenanza urbanística |
| Modificación ámbito suspensión licencias (acuerdo pleno 28-07-2020) | Licencia / planeamiento |

## Licencias de obra

- No hay dataset público de concesiones individuales de licencia.
- Catálogo STA incluye trámites: licencia de obras, ocupación vía pública, cambio de uso, etc.
- Edictos puntuales en tablón cuando se publican suspensiones o acuerdos plenarios.

## Expedientes / planeamiento (transparencia)

Páginas dedicadas con título H1 y PDFs:

| Expediente | Tipo |
|------------|------|
| 2021-1007x | Modificación nº 1 Plan General |
| 2021-6714j | Mejora precisión geométrica límite término municipal |
| 2021-12384e | PAI sector Cementos Turia |
| 2022-272c | Estudio detalle manzana ENS-131 |
| 2023-11769c | Desarrollo actuación integrada sector TER-1 La Capella |
| 2024-2501v | Estudio detalle parcela dotacional campus UV |
| 2024-18454p | Modificación puntual nº 2 PGOU |
| 2025-9993y | Modificación puntual nº 3 PGOU |
| UE-1 | Unidad de ejecución 1 |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes investigadas:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `Planeamiento.Zonificacion`, filtro `cod_ine_mun=46078` — **0 polígonos** en offsets 0–16500.
  - PGOU ZIP en `archivo.burjassot.org/archivos/PGOU2019/` (shapefiles/catalogo) — no parseado en adapter (formato binario).
  - Visor `urbanismo.burjassot.org` — no resuelve desde CI.
- **Estrategia:** orquestador aplicará centroide municipio + jitter (`centroid: [39.5097, -0.4133]`).
- **Limitaciones:** sin WFS ni visor accesible; expedientes solo metadatos + PDF.

## Limitaciones generales

- Tablón STA lento (~40 s) por tamaño del HTML embebido.
- Mucho ruido en tablón (subvenciones, tasas, empleo); filtrado por regex.
- Sin listado público de licencias concedidas con coordenadas.
- `urbanismo.burjassot.org` inaccesible en entorno cloud.

## Adapter implementado

- `municipio.adapters.burjassot:BurjassotAyuntamientoAdapter`
- Fuentes: tablón STA + transparencia expedientes + PDFs web urbanismo/PGOU + páginas informativas trámites.
- IDs: `burjassot-lic-*` / `burjassot-proy-*` (sha256[:14]).
