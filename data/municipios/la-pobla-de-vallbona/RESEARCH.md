# La Pobla de Vallbona — investigación portal ayuntamiento

Municipio: La Pobla de Vallbona (`la-pobla-de-vallbona`), provincia Valencia, Comunitat Valenciana. Boletín: DOGV (`dogv`).

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web municipal (TYPO3) | https://www.lapobladevallbona.es/es/ |
| Urbanismo | https://www.lapobladevallbona.es/es/servicios-municipales/urbanismo-movilidad-y-medio-ambiente/ |
| Plan General Estructural | https://www.lapobladevallbona.es/es/servicios-municipales/urbanismo-movilidad-y-medio-ambiente/plan-general-estructural |
| Proyectos urbanismo | https://www.lapobladevallbona.es/es/servicios-municipales/urbanismo-movilidad-y-medio-ambiente/proyectos-urbanismo |
| Agenda urbana | https://www.lapobladevallbona.es/es/la-ciudad/agenda-urbana |
| Gobierno abierto (WordPress) | https://governobert.lapobladevallbona.es/es/ |
| Sede electrónica STA (TAO/T-Systems) | https://seu.lapobladevallbona.es/sta/ |
| Tablón anuncios | https://seu.lapobladevallbona.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&lang=ES |
| Catálogo trámites | https://seu.lapobladevallbona.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES |
| Transparencia (Governalia) | https://transparencialapobladevallbona.governalia.es/ |

## Listado de expedientes / proyectos

- **Sede STA tablón:** página `PTS2_TABLON` embebe `var dataset_PTS2_TABLON = [...]` (~259 anuncios). Campos: `dboid`, `descriptionProc`, `externString`, `pubDateIni`, `remitent.description`. Detalle: `DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`.
- **Web TYPO3:** sección PGE con decenas de PDFs en `/fileadmin/user_upload/...` (modificaciones puntuales, SAUI/SAUR, fichas de zona, normas urbanísticas). Listado estático HTML sin API.
- **Proyectos urbanismo:** página informativa con enlaces a agenda urbana y PGE; sin listado dinámico de expedientes.
- **No hay** visor municipal ArcGIS ni API de expedientes urbanísticos públicos.

## Licencias

- **Tablón:** sin concesiones individuales de licencias de obra con dirección; anuncios de evaluación ambiental y urbanismo general.
- **Catálogo sede (`CATSERV`):** ~27 trámites de «Urbanismo y vivienda» (licencias obra mayor/menor, DR, compatibilidad urbanística, segregación parcelas, terrazas, redes). Páginas informativas sin listado de concesiones.
- **No hay** dataset ni PDF periódico de licencias concedidas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: sectores SU/SUZ y unidades de ejecución del planeamiento valenciano
  - Filtro cliente: `cod_ine_mun=46202` (La Pobla de Vallbona)
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`); `CQL_FILTER` no fiable en servidor
  - Paginación: `STARTINDEX` + `count=200`
- **Estrategia:** descargar WFS paginado, filtrar INE 46202 (49 polígonos), convertir `gml:posList` → GeoJSON Polygon; enriquecer proyectos PDF/tablón por tokens de sector (`UE-*`, `SAUR-*`, `R-*`, etc.).
- **Limitaciones:** ICV cubre instrumentos de planeamiento aprobados, no licencias de obra ni expedientes del tablón. Sin visor municipal propio. Licencias y anuncios sin georef → orquestador usa centroide + jitter.

## Limitaciones

- Tablón mezcla personal, fiscalidad y subvenciones; filtro regex urbanismo.
- Sin listado público de licencias concedidas con coordenadas.
- PGE en PDF sin servicio SIG municipal enlazable por expediente.
- ICV WFS no enlaza código de expediente municipal; matching por nombre de sector/UE.

## Adapter

- `municipio.adapters.la_pobla_de_vallbona:LaPoblaDeVallbonaAyuntamientoAdapter`
- Fuentes: tablón STA + PDFs TYPO3 (PGE) + ICV WFS + catálogo trámites (licencias informativas)
