# La Losa — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León, INE **40113**). El ayuntamiento publica una **web WordPress** en `www.lalosa.es` (turismo y servicios básicos, sin sección de urbanismo propia) y un **portal Liferay de la Diputación de Segovia** (`dipsegovia.es/web/ayuntamiento-de-la-losa`). La **sede electrónica** es **espublico gestiona** (`lalosa.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal (WordPress) | https://www.lalosa.es |
| Portal Liferay (DipSegovia) | https://www.dipsegovia.es/web/ayuntamiento-de-la-losa |
| Normativa municipal | https://www.dipsegovia.es/web/ayuntamiento-de-la-losa/normativa-municipal |
| Área de descargas | https://www.dipsegovia.es/web/ayuntamiento-de-la-losa/area-de-descargas |
| Sede electrónica | https://lalosa.sedelectronica.es |
| Tablón sede | https://lalosa.sedelectronica.es/board |
| Trámites (catálogo) | https://lalosa.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=113 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=113 |

## Expedientes / planeamiento

- **Web municipal:** WordPress sin listado de expedientes urbanísticos; enlace a la sede electrónica.
- **DipSegovia:** portal informativo (corporación, normativa, descargas); **no hay sección urbanismo** dedicada (404 en `/urbanismo`).
- **PLAI JCYL:** tabla HTML paginada con ~15 documentos de planeamiento aprobado (NUM, modificaciones puntuales, estudio de detalle UA-1 Tres Peñas, junta de compensación, etc.) y 1 expediente en información pública (UA-7 El Roquedal, agosto 2026).
- **Tablón sede:** accesible pero **vacío** (sin filas `preview-document` en septiembre 2026).
- **Sin visor municipal propio** ni Drupal con expedientes IP.

## Licencias de obra

- Trámites en sede espublico (`/dossier`); el catálogo `/catalog` devuelve 404.
- No hay listado público de licencias concedidas con coordenadas.
- El adapter incluye páginas informativas de trámites y entradas del tablón cuando existan.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'La Losa'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature: Normas Urbanísticas Municipales)
  - `urbanismo:plau_cyl_planes_parciales` (0 features)
  - `urbanismo:plau_cyl_sectores` (14 features: Mano Sacristán, Tres Peñas, Palacio, Roquedal-I/II, El Plantío, Los Egidos II, etc.)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAI y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; tablón sede vacío; expedientes PLAI no siempre enlazan a sector WFS concreto.

## Limitaciones generales

- Sin sección urbanismo en web ni DipSegovia; planeamiento centralizado en PLAI JCYL.
- Sede `/dossier` puede responder lento o vacío; el adapter tolera timeout.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
