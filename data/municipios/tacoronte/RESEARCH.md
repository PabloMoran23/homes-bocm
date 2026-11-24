# Tacoronte — investigación portal ayuntamiento

## Fuentes principales

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.tacoronte.es | WordPress (Divi); guía sede, servicios municipales |
| Sede electrónica | https://tacoronte.sedelectronica.es | espublico **gestiona** (Wicket) |
| Tablón de anuncios | https://tacoronte.sedelectronica.es/board | Tabla HTML con preview-document UUID; categorías *Urbanismo*, *Licencias Urbanísticas* |
| Catálogo trámites | https://tacoronte.sedelectronica.es/dossier | Procedimientos telemáticos (urbanismo / licencias) |
| Consulta expedientes | https://tacoronte.sedelectronica.es/expedientes | Requiere identificación para actuaciones personales |
| SITCAN CKAN | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-tacoronte | Instrumentos de planeamiento (PDF, IDE Canarias, GEOBDP) |
| GEOBDP Grafcan | https://geobdp.grafcan.es/core/municipios/38043/ | Índice documentos urbanísticos + visor OpenLayers |

## Listado de expedientes / licencias

- **Tablón (`/board`)**: filas con documento, expediente (p. ej. `9869/2024`), procedimiento, categoría, descripción y fecha `DD/MM/YYYY`. Enlaces a `preview-document/{uuid}` (PDF vía AJAX espublico).
- **Licencias**: procedimiento *Licencias Urbanísticas*, categoría *Urbanismo* (anuncios BOP, solicitudes de licencia de obras).
- **Planeamiento**: procedimientos genéricos y documentación en SITCAN/GEOBDP (PGOU, revisiones parciales, planes especiales).
- **Consulta expedientes**: no scrapeable sin certificado/Cl@ve.

## Geometría / visor

- **geometry_status:** `available` (planeamiento) / `partial` (licencias de tablón sin enlace GIS)
- **Fuentes:**
  - GEOBDP document pages (`/core/documentos/{id}.html`) — `App.Map.zoomToExtent(FeatureCollection)` en **EPSG:32628** (UTM 28N), reprojectado a WGS84 en el adapter.
  - Enlaces desde SITCAN resources hacia `geobdp.grafcan.es/core/documentos/…`
  - Enlace geoportal desde web (`https://grafcan.es/T5p1cWT` → Grafcan)
- **Estrategia:** emparejar título SITCAN/GEOBDP con índice municipal GEOBDP; descargar polígono del visor embebido.
- **Limitaciones:** anuncios de licencias en tablón no exponen geometría del ámbito de obra; solo metadatos + PDF. Consulta de expediente personal requiere auth.

## Limitaciones generales

- Sin boletín regional asociado en cola (`bocm_count: 0`).
- Tablón mezcla edictos no urbanísticos (presupuesto, personal); filtrado por regex en adapter.
- Paginación del tablón vía Wicket (una página visible en HTML estático; suficiente para licencias recientes).

## Adapter

`municipio.adapters.tacoronte:TacoronteAyuntamientoAdapter` — patrón Telde/Tenerife: SITCAN + GEOBDP + tablón espublico + páginas semilla web.
