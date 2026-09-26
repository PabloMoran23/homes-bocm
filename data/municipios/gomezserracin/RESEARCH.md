# Gomezserracín — investigación portal ayuntamiento

**Municipio:** Gomezserracín (Castilla y León, Segovia)  
**INE:** 40095  
**Fecha:** 2026-09-17

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Liferay / Diputación Segovia) | https://www.gomezserracin.es | Portal Segovia12 theme (Diputación de Segovia) |
| Urbanismo | https://www.gomezserracin.es/urbanismo | 1 PDF: Normas Subsidiarias de Planeamiento del término municipal |
| Actualidad municipal | https://www.gomezserracin.es/actualidad-municipal | Noticias (Asset Publisher) |
| Tablón web | https://www.gomezserracin.es/tablon-de-anuncios | Enlace al tablón de la sede |
| Sede electrónica (espublico gestiona) | https://gomezserracin.sedelectronica.es | Trámites, tablón `/board/` |
| Tablón sede | https://gomezserracin.sedelectronica.es/board/ | Anuncios administrativos (tributos, padrón, presupuesto); sin urbanismo activo |
| PLAU Junta CYL (prov. 40, mun. 095) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=095 | Archivo planeamiento aprobado |

## Cómo se listan expedientes

- **Liferay document library** en `/urbanismo`: enlace directo a PDF de Normas Subsidiarias (`/documents/1451654/448f7ef9-...`).
- **Noticias** vía Asset Publisher en actualidad municipal.
- **Tablón espublico** (`/board/`): tabla HTML con `data-label` (documento, expediente, procedimiento, categoría, fecha); enlaces `preview-document/<uuid>`. Actualmente sin entradas de categoría Urbanismo.
- **Sin visor de expedientes** ni API JSON de listado histórico.
- **BOCYL:** 1 entrada en CSV regional (`boletin_source_id: bocyl`).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra publicadas.
- Trámites vía sede electrónica (certificado digital); dossier de trámites responde lento desde CI.
- Tablón sin licencias urbanísticas en el momento de la investigación.
- Estrategia adapter: páginas informativas (urbanismo + sede + tablón) + scraping tablón para futuras publicaciones.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 NNSS MultiPolygon), `urbanismo:plau_cyl_sectores` (1 sector A1 Dehesa Boyal MultiPolygon), `urbanismo:plau_cyl_planes_parciales` (0)
  - Filtro: `n_mun = 'Gomezserracín'`
  - Campos: `n_titulo`, `n_sector`, `n_num_sect`, `c_id_sect` (40095A1), `c_categ_sue` (SUR), `n_uso_glob` (Industrial)
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas Liferay/tablón por coincidencia de nombre de sector en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sin anuncios urbanísticos activos.
  - PDF NNSS sin coords embebidas.
  - Geometría WFS solo para ámbitos PLAU CyL (instrumento + sector), no para licencias individuales.

## Limitaciones generales

- Municipio pequeño (~200 hab.); volumen bajo de publicaciones urbanísticas.
- Portal gestionado por plantilla Diputación de Segovia (Liferay); patrón replicable en otros municipios segovianos (ver Abades).
- Sede dossier (`/dossier`) con timeouts desde CI; no requiere `insecure_ssl`.
