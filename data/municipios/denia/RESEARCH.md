# Dénia — investigación portal ayuntamiento

Municipio: Dénia (`denia`), provincia Alicante, Comunitat Valenciana. Boletín: DOGV (`dogv`).

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.denia.es/es/ |
| Urbanismo | https://www.denia.es/es/info/urbanisme/index.aspx |
| Planeamiento desarrollo | https://www.denia.es/es/info/urbanisme/planejament/index.aspx |
| Plan Especial Alqueries | https://www.denia.es/es/info/urbanisme/alqueries/index.aspx |
| PGE | https://www.denia.es/es/info/urbanisme/pge/index.aspx |
| POP | https://www.denia.es/es/info/urbanisme/pop/index.aspx |
| Control urbanístico / ECUV | https://www.denia.es/es/info/urbanisme/control/index.aspx |
| Licencias (docs) | https://www.denia.es/es/info/urbanisme/llicencies/index.aspx |
| Cartografía | https://www.denia.es/es/info/urbanisme/cartografia/index.aspx |
| Sede electrónica STA | https://sede.denia.es/sta/ |
| Tablón anuncios | https://sede.denia.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES |
| Catálogo trámites | https://sede.denia.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES |
| Transparencia | http://transparencia.denia.es/es/ |
| Reg. planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03063%20DENIA/ |

## Listado de expedientes / proyectos

- **Sede STA tablón:** página `PTS2_TABLON` con `KEY=all` embebe `var dataset_PTS2_TABLON = [...]` (74 anuncios, ~17 urbanismo/licencias). Campos: `dboid`, `descriptionProc`, `externString`, `pubDateIni`, `remitent.description`.
- **Web urbanismo:** ASP.NET con carpetas de documentos PDF en `/docs/planejament/`, `/docs/alqueries/`, `/docs/llicencies/`, `/docs/control_urb/`. Listados estáticos en HTML (sin API).
- **No hay** visor municipal con expedientes enlazables ni Drupal/Liferay de tramitación pública.

## Licencias

- **Tablón:** anuncios de compatibilidad urbanística vivienda turística, exposición pública, etc. (no concesiones individuales con coords).
- **Catálogo sede:** ~48 trámites urbanísticos (licencias obra mayor, DR, compatibilidad VUT, control urbanístico). Páginas informativas sin listado de concesiones.
- **Web:** PDFs guías y diagramas de procedimientos en `/docs/llicencies/`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: sectores SU/SUZ y unidades de ejecución
  - Filtro cliente: `cod_ine_mun=03063` (Dénia)
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`); JSON no soportado
  - Paginación: `STARTINDEX` + `count=200` (CQL_FILTER ignorado parcialmente)
- **Estrategia:** descargar WFS paginado, filtrar INE 03063, convertir `gml:posList` → GeoJSON Polygon; enriquecer proyectos por coincidencia de título con sector (`pp`, `ue`).
- **Visor cartografía municipal:** enlace a PDF cartografía (`cdn.digitalvalue.es/denia/assets2/...`) y Centinela Lefebvre; sin WFS/ArcGIS propio del ayuntamiento.
- **Limitaciones:** 9 polígonos ICV (sectores planificados), sin geometría para licencias de obra ni expedientes del tablón. Licencias y anuncios sin georef → orquestador usa centroide + jitter.

## Limitaciones

- Tablón mezcla personal/oposiciones/subvenciones; filtro regex urbanismo/licencias.
- Sin listado público de licencias concedidas con dirección.
- Cartografía web sin servicio SIG consultable por expediente.
- ICV WFS no enlaza código de expediente municipal; matching por nombre de sector.

## Adapter

- `municipio.adapters.denia:DeniaAyuntamientoAdapter`
- Fuentes: tablón STA + PDFs web + ICV WFS + catálogo trámites (licencias informativas)
