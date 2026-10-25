# Mairena del Aljarafe — investigación portal ayuntamiento

**Municipio:** Mairena del Aljarafe (Sevilla, Andalucía)  
**Slug:** `mairena-del-aljarafe`  
**INE:** 41068

## URLs base y semillas

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.mairenadelaljarafe.es | OpenCMS InPro (theme4) |
| Proyecto de ciudad / urbanismo | https://www.mairenadelaljarafe.es/es/proyecto-de-ciudad/ | Enlaces GMU y planeamiento |
| PAI EDIL | https://www.mairenadelaljarafe.es/es/pai-edil/ | Plan de actuación integral edilicio |
| PGOU documentación GMU | https://www.mairenadelaljarafe.es/es/ayuntamiento/organismos-y-sociedades/gerencia-municipal-de-urbanismo/Documentos-urbanisticos-aprobados/Planeamiento/planeamiento-general-pgou-e-innovaciones/ | **~109 PDFs** (mapas, normas, innovaciones) |
| Portal transparencia Dipusevilla | https://transparencia.mairenadelaljarafe.es | SagaSuite / Diputación Sevilla |
| IND-50 PGOU | https://transparencia.mairenadelaljarafe.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00020/ | 3 PDFs resumen |
| Sede general | https://mairenadelaljarafe.sedelectronica.es | espublico gestiona |
| Tablón general | https://mairenadelaljarafe.sedelectronica.es/board | Filas varias (RRHH, subvenciones, urbanismo puntual) |
| Sede GMU | https://gmumairenadelaljarafe.sedelectronica.es | Gerencia Municipal de Urbanismo |
| Tablón GMU | https://gmumairenadelaljarafe.sedelectronica.es/board | **Urbanismo** (planeamiento BOP, licencias actividad, actuaciones) |
| Transparencia sede | https://mairenadelaljarafe.sedelectronica.es/transparency | Sección urbanismo (documentos vía AJAX) |
| Consulta expedientes | https://gmumairenadelaljarafe.sedelectronica.es/expedientes | Requiere identificación |
| LicytalPub Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4106800F | Licencias provinciales |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41068 | Planeamiento autonómico |

## Listado de expedientes / proyectos

- **Tablón espublico:** HTML con filas `<tr>` y celdas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, enlaces `/preview-document/{uuid}`.
- **PGOU OpenCMS:** listado estático de PDFs en galería `/export/sites/mairena/.galleries/DOCUMENTOS-gerencia-urbanismo/PGOU/`.
- **Transparencia IND-50:** PDFs en galería IND-50.
- **Expedientes individuales:** no hay API pública; consulta en sede tras login.

## Licencias

- Edictos de **licencias de actividad** y obras en tablón GMU (categoría Urbanismo / Anuncios).
- Histórico masivo: portal **LicytalPub** Diputación (CIF `P4106800F`), sin scrape automatizado en esta fase (página JSF).
- Trámites informativos en catálogo sede GMU (`/dossier`).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:** PGOU en PDF (mapas raster, sin servicio WMS/WFS público en web municipal); Google Maps embebido en portada (sin capas urbanísticas); SITUA Junta (consulta por municipio, no geometría por expediente del tablón).
- **Estrategia:** el orquestador usará centroide municipal + jitter (`manifest.config.centroid`).
- **Limitaciones:** sin visor ArcGIS/WFS municipal; tablón solo PDF; expedientes tras autenticación.

## Adapter

- `municipio.adapters.mairena_del_aljarafe:MairenaDelAljarafeAyuntamientoAdapter`
- IDs: `mairena-del-aljarafe-lic-*` / `mairena-del-aljarafe-proy-*` (sha256[:14]).

## Limitaciones

- Certificados sede: `insecure_ssl: true` en manifest (patrón municipios espublico provincia Sevilla).
- Crawl PGOU (~109 PDFs) implica ~40s de backfill por `request_delay_s`.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
