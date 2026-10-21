# Vitoria-Gasteiz — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.vitoria-gasteiz.org |
| Sede electrónica | https://sedeelectronica.vitoria-gasteiz.org/portal/es/ |
| PGOU — expedientes en tramitación | https://www.vitoria-gasteiz.org/wb021/was/contenidoAction.do?idioma=es&uid=u_16dc2b57_134cb3b30bd__7fe9 |
| Planeamiento de desarrollo (ámbitos) | https://www.vitoria-gasteiz.org/wb021/was/contenidoAction.do?idioma=es&uid=u6bf57c84_13f2c50cf68__7fa9 |
| Convenios urbanísticos | https://www.vitoria-gasteiz.org/wb021/was/contenidoAction.do?idioma=es&uid=u8d5a2c5_13f83da3e15__7fc4 |
| Open data (catálogo) | https://www.vitoria-gasteiz.org/j34-01w/catalogo/portada?idioma=es |

## Expedientes / planeamiento

- CMS propio **j38** (`contenidoAction.do?uid=…`): listas HTML en bloque ODT con enlaces a fichas por expediente.
- Cada ficha enlaza documentación PDF vía `we001Action.do?accionWe001=adjunto&nombre=….pdf`.
- No hay API JSON pública de expedientes; el adapter parsea listas de «Expedientes en tramitación» y «Planeamiento de desarrollo».

## Licencias de obra

- **No** hay dataset abierto de licencias urbanísticas otorgadas (como Madrid/otros).
- Sede: trámites informativos (obra menor, obra mayor reformas, consulta urbanística) sin listado de concesiones.
- **Capa GIS «Proyecto obra»** (obras municipales en ejecución/adjudicadas) con polígonos y fechas — usada como proxy georreferenciado de actividad de obra (`FECHA_ADJU`, `ZONA`, `TITULO`).

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - ArcGIS MapServer `internet/10_u15grupo04/MapServer/10` — capa **Proyecto obra** (polígonos, EPSG:25830 nativo; consulta con `outSR=4326`).
  - ArcGIS MapServer `internet/10_pgou_wms_6_7_omv/MapServer/0` — **Ámbitos** PGOU (`AMBITO`, `NOMBRE`, polígonos).
  - Visor PGOU WMS adicional: `10_pgou_wms_5`, `10_geoVitoria2023` (parcelas `V_PORTAL`, usos suelo).
- **Estrategia:** join heurístico título/código de ámbito (A-13, sector, OA 2.xx) → query ámbitos; licencias desde capa Proyecto obra por `CODIGO`.
- **Limitaciones:** licencias de terceros no publicadas en tablón; matching ámbito–expediente es aproximado cuando el título no cita código PGOU.

## Limitaciones generales

- Sin tablón electrónico de licencias urbanísticas.
- Portal j38: HTML estático, sin paginación en listas actuales.
- ArcGIS `MaxRecordCount` 1000 (suficiente para capas actuales).
