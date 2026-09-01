# Novelda — investigación portal ayuntamiento

Municipio: Novelda (`novelda`), provincia Alicante, Comunitat Valenciana. Boletín: DOGV (`dogv`).

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.novelda.es/ |
| Concejalía Urbanismo | https://www.novelda.es/el-ayuntamiento/concejalias/urbanismo/ |
| Agenda Urbana 2030 | https://www.novelda.es/agenda-urbana-novelda-2030/ |
| Sede electrónica STA (TAO) | https://sede.novelda.es/sta/ |
| Tablón anuncios | https://sede.novelda.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON&lang=ES |
| Catálogo trámites | https://sede.novelda.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV&lang=ES |
| Reg. planeamiento GVA | https://mediambient.gva.es/auto/urbanismo/reg-planeamiento/2%20ALICANTE/03104%20NOVELDA/ |

## Listado de expedientes / proyectos

- **Sede STA tablón:** página `PTS_TABLON` embebe `var dataset_PTS_TABLON = [...]` (~43 anuncios vigentes). Campos: `dboid`, `descriptionProc`, `externString`, `pubDateIni`, `remitent.description`.
- **Web urbanismo:** WordPress con PDFs enlazados en la página de concejalía (información pública, estudios de integración paisajística, modificaciones puntuales, fotovoltaica, etc.). Sin API REST de documentos.
- **ICV WFS:** capa `InventarioSuSuz` con 47 sectores/unidades de ejecución para Novelda (SU, SUZ, UZI, UZO, UZE, UBO).
- **No hay** visor municipal ArcGIS ni expedientes urbanísticos consultables por código.

## Licencias

- **Tablón:** mayoritariamente subvenciones y personal; pocos anuncios de urbanismo/licencias.
- **Catálogo sede:** ~25 trámites urbanísticos (licencia obra mayor, DR obras menores, comunicación previa, ocupación vía pública con obras, etc.). Páginas informativas sin listado histórico de concesiones.
- **No hay** dataset público de licencias concedidas con dirección.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: sectores SU/SUZ y unidades de ejecución (UZI, UZO, UZE, UBO)
  - Filtro cliente: `noms_mun=Novelda` o `cod_ine_mun` en {03104, 03093} (ICV mezcla códigos INE)
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`); JSON no soportado
  - Paginación: `STARTINDEX` + `count=200`
- **Estrategia:** descargar WFS paginado, filtrar por municipio, convertir `gml:posList` → GeoJSON Polygon; enriquecer proyectos web/tablón por coincidencia de título con sector.
- **Limitaciones:** 47 polígonos ICV (sectores planificados), sin geometría para licencias de obra ni expedientes del tablón. Sin visor municipal propio. Licencias y anuncios sin georef → orquestador usa centroide + jitter.

## Limitaciones

- Tablón mezcla subvenciones/personal/ambiental; filtro regex urbanismo.
- Sin listado público de licencias concedidas con dirección.
- ICV WFS no enlaza código de expediente municipal; matching por nombre de sector.
- Web WordPress sin visor SIG integrado.

## Adapter

- `municipio.adapters.novelda:NoveldaAyuntamientoAdapter`
- Fuentes: tablón STA + PDFs web urbanismo + ICV WFS + catálogo trámites (licencias informativas)
