# Monòver — investigación portal ayuntamiento

**Municipio:** Monòver / Monóvar (Alicante, Comunitat Valenciana)  
**Slug:** `monover`  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)  
**INE:** 03090

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.monovar.es | **Operativa** — WordPress |
| Urbanismo | https://www.monovar.es/urbanismo/ | Formularios PDF licencias/DR |
| PGOU vigente | https://www.monovar.es/plan-general-de-ordenacion-urbana-de-monovar/ | PDF PGOU 1985 + planos |
| PGOU en trámite | https://www.monovar.es/propuesta-plan-general-estructural-2019-2a-exposicion-publica/ | Documentación exposición pública |
| Plan especial vertedero | https://www.monovar.es/plan-especial-vertedero-de-inertes/ | IP / aprobación DOGV |
| Sede electrónica | https://monovar.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://monovar.sedelectronica.es/board | **Operativa** — ~10 filas visibles |
| Catálogo trámites | https://monovar.sedelectronica.es/dossier | Trámites urbanismo (sin histórico) |
| Consulta expedientes | https://monovar.sedelectronica.es/expedientes | Requiere identificación |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Alcalà de Xivert.
- **Listado:** tabla HTML (`class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`).
- **Documentos:** `preview-document/{uuid}`.
- **Urbanismo reciente (sep 2026):** aprobación definitiva urbanización y reparcelación **Sector 4 de Cañada**; rehabilitación edificio C/ Cid 11-13 (obra).

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Modelos PDF en `/urbanismo/` (licencias, DR, segregación, etc.).
- Concesiones publicadas como edictos en tablón cuando procede.

## Proyectos / planeamiento

- **PGOU 1985** y planos en web municipal.
- **PGOU estructural 2019** en segunda exposición pública (página dedicada).
- **Plan especial vertedero de inertes** — documentación DOCV / información pública.
- **Tablón:** actuaciones urbanísticas (sectores, reparcelación, proyectos de urbanización).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - ICV WFS `InventarioSuSuz`: `https://terramapas.icv.gva.es/0702_Planeamiento` — barrido ~8.4k features, **0** con `cod_ine_mun=03090`.
  - Visor GVA regional: sin inventario SU/SUZ para Monòver.
  - Web municipal: solo PDFs/planos raster sin servicio WMS/ArcGIS enlazable a expediente.
- **Estrategia:** el adapter intenta WFS ICV y emparejamiento por sector en títulos; sin polígonos disponibles el orquestador usa centroide municipal + jitter.
- **Limitaciones:** PGOU y tablón sin geometría vectorial pública; consulta expedientes con login.

## Limitaciones generales

- Tablón: una página HTML estática en adapter (sin paginación Wicket).
- SSL sede: certificado con hostname `monovar`; `insecure_ssl: true` en manifest.
- Sin visor urbanístico municipal interactivo con capas descargables.

## Adapter implementado

- `municipio.adapters.monover:MonoverAyuntamientoAdapter`
- Fuentes: WordPress (PGOU/urbanismo PDFs) + tablón sede + páginas informativas de trámites + intento ICV WFS.
