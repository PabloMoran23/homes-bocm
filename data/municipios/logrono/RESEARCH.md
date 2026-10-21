# Logroño — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Formato |
|--------|-----|---------|
| Exposición pública | https://logrono.es/exposicion-publica | Liferay portlet `ExposicionPublicaPortlet`, HTML paginado (`cur`, `delta`) |
| Últimas aprobaciones | https://logrono.es/ultimas-aprobaciones | Liferay, listado de títulos de planeamiento |
| Urbanismo (info) | https://logrono.es/unidad-urbanismo | Enlaces al visor y normativa |
| Sede electrónica urbanismo | https://sedeelectronica.logrono.es/.../urbanismo | IBM WebSphere; tablones de obras/actividades (HTML pesado) |
| Últimas modificaciones (sede) | https://sedeelectronica.logrono.es/.../ultimosProyectos | PDFs históricos (misma info parcial en web Liferay) |

### Exposición pública

- Cada entrada: `<h2 class="titulo">`, fechas inicio/fin (`dd/mm/yyyy`), enlace `/documents/...` (PDF o ZIP).
- Códigos habituales: `URB20-2026/0139`, `URB27_2026_0002`, `URB14-2024-0002`, `0712 Expte 2025/9026`.
- Paginación: parámetros `_es_logrono_exposicion_publica_ExposicionPublicaPortlet_cur` y `_delta`.

### Licencias

- Publicadas en **exposición pública** como “Licencia conjunta ambiental y de obras…” (no hay listado tabular de concesiones definitivas en abierto).
- La sede describe tablones de “Novedades negociado de Obras/Actividades” pero sin API estable para scrape masivo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor PGM/cartografía: http://gis.logro-o.org (Angular + OpenLayers, EPSG:25830 en cliente)
  - GeoServer WFS: `http://gis.logro-o.org/gs/geoserver/wfs`
    - `CARTO:Unidad de Ejecucion` — polígonos UE (campo `titulo`, p. ej. `N07.5 "MERCADAL 2"`)
    - `CARTO:Portales` — puntos de portal catastral (`vial`, `numero`, `direccion_completa`)
- **Estrategia:** extraer código UE (`N07.5`, `M14.4`, …) o vía+número del título; consultar WFS con `CQL_FILTER`, `srsName=EPSG:4326`, `outputFormat=application/json`.
- **Limitaciones:**
  - El visor no expone enlace directo expediente↔geometría; no hay capa de licencias por código URB.
  - Portales devuelve `Point` (útil para `lat`/`lon`, no cuenta como `with_geometry` en parity).
  - Direcciones ambiguas o fuera del catastro municipal → sin geometría.
  - Sede/tablon histórico no georreferenciado.

## Limitaciones generales

- Histórico largo de planeamiento está en PDFs en sede; el adapter usa exposición + últimas aprobaciones (determinista, sin LLM).
- Entradas no urbanísticas en exposición (castañas, subvenciones) se filtran.
- Sin `boletin_source_id` en cola (0 entradas BOCM para Logroño).
