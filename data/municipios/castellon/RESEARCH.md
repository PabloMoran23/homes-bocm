# Forcall — investigación portal ayuntamiento

**Municipio real:** Forcall (provincia Castellón, Comunitat Valenciana)  
**Slug cola:** `castellon` (nombre DOGV parseado como «Castellón»; `municipio_provincia` = «Forcall, Castellón»)  
**INE:** 12061

## Nota sobre slug / nombre

La cola automática asigna slug `castellon` y nombre «Castellón» por una fila DOGV donde el municipio aparece como provincia. La investigación confirma que el ayuntamiento y las fuentes urbanísticas corresponden a **Forcall** (`www.forcall.es`).

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal (Drupal 9) | https://www.forcall.es |
| Sede electrónica (espublico gestiona) | https://forcall.sedelectronica.es |
| Tablón de anuncios | https://forcall.sedelectronica.es/board |
| Trámites | https://forcall.sedelectronica.es/dossier |
| PGOU — aprobación definitiva | https://www.forcall.es/es/noticias/aprobacion-definitiva-del-plan-general-de-forcall |
| MP1 PGOU — información pública | https://www.forcall.es/es/noticias/informacion-publica-de-la-modificacion-puntual-numero-1-del-plan-general-de-ordenacion |
| Registro planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/3%20CASTELL%D3N/12061%20FORCALL/ |

## Expedientes / planeamiento

- **Drupal:** noticias con PDFs del PGOU y modificaciones puntuales (`/sites/061/files/...`).
- **GVA:** carpeta `12061 FORCALL` en el registro autonómico de planeamiento.
- **Tablón sede:** HTML tabular (clases `class_name`, `class_folderCode`, …); en sept. 2026 sin filas urbanísticas recientes (censo, IAE, saneamiento).
- **Consulta expedientes:** `/expedientes` requiere identificación; sin listado público.

## Licencias

- No hay dataset ni listado histórico de licencias concedidas.
- Trámites de obra/actividad vía sede (`/dossier`); el tablón puede publicar edictos puntuales.
- El adapter incluye páginas informativas del tablón y catálogo de trámites (patrón Pozuelo/Móstoles).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `Planeamiento.Zonificacion` — `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Filtro cliente `cod_ine_mun=12061` (2 polígonos PGOU, expediente `20130105`, zonas ZRC-FO)
  - Sin visor ArcGIS municipal ni enlace expediente→geometría en sede
- **Estrategia:** paginar WFS GML (`outputFormat=application/gml+xml; version=3.2`, `srsName=EPSG:4326`), enriquecer proyectos PGOU/planeamiento por expediente o título.
- **Limitaciones:** solo zonificación del plan general (no parcelas ni licencias); tablón sin coords; sede sin API pública de geometrías.

## Limitaciones generales

- SSL en sede: certificado válido.
- Drupal sin API JSON de expedientes; scrape de noticias + PDFs.
- WFS ICV sin CQL_FILTER fiable; paginación hasta `cod_ine_mun=12061`.

## Adapter

- `municipio.adapters.castellon:CastellonAyuntamientoAdapter`
- IDs: `castellon-lic-*` / `castellon-proy-*` (sha256[:14]).
