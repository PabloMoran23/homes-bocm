# Trespaderne — investigación portal ayuntamiento

Municipio: Trespaderne (Burgos, Castilla y León). Código INE `09299` (provincia PLAI `09`, municipio `299`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://trespaderne.burgos.es | Drupal 10, tema Toools (Diputación Burgos); `www.trespaderne.es` redirige aquí |
| Sede electrónica | https://trespaderne.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://trespaderne.sedelectronica.es/board | Anuncios Wicket (presupuestos, ordenanzas; sin licencias urbanísticas recientes) |
| Servicio URBANISMO | https://trespaderne.sedelectronica.es/citizen-service/2c314061-c7de-4583-aea1-04ba11588afd | Trámites/licencias de obras (informativo) |
| Catálogo trámites | https://trespaderne.sedelectronica.es/dossier | Redirige a `/dossier.0` (requiere cookies) |
| Normativa | https://trespaderne.burgos.es/normativa | Ordenanzas municipales |
| Archivo PLAI JCyL | http://www.jcyl.es/plau/lplanes.plau?municipio=09299 | Listado histórico planeamiento |
| API PLAI scrape | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=9&municipio=299 | Sin filas en muestra (0 documentos indexados) |
| OVC Diputación | https://ovc.diputaciondeburgos.es/ | Visor cartográfico provincial (enlace desde web municipal) |
| Diputación Burgos | https://burgos.es/provincia/municipio/trespaderne | Metadatos municipio |

## Expedientes / proyectos

- **Principal (geometría):** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Trespaderne'` — 1 instrumento (NUM), 1 plan parcial, 27 sectores.
- **PLAI JCyL:** sin documentos publicados en `searchVPubDocMuniPlai` para mun. 299 (el adapter consulta por si se indexan en el futuro).
- **Tablón sede:** actas de arqueo, balances y ordenanzas fiscales; sin anuncios de exposición pública urbanística en la muestra actual.
- **Web Drupal:** sin sección `/urbanismo` dedicada; menú corporativo + enlaces a sede y OVC.

Instrumentos WFS identificados: NORMAS URBANÍSTICAS MUNICIPALES; sectores codificados U1–U5, etc.

## Licencias de obra

- No hay listado público de concesiones de licencia en el tablón.
- Trámites vía sede (catálogo `/dossier`, servicio URBANISMO) — páginas informativas.
- El adapter devuelve trámites informativos cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Trespaderne'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar features WFS como proyectos con polígono MultiPolygon; enriquecer filas tablón/trámite por coincidencia de título o código sector (U1, U5, …).
- **Limitaciones:** sin visor municipal ArcGIS propio; licencias sin georreferencia; PLAI sin documentos indexados; geometría WFS a nivel instrumento/sector, no expediente individual de licencia.

## Limitaciones

- Tablón espublico sin categoría urbanismo activa con expedientes recientes.
- Drupal sin descargas PDF urbanísticas en rutas estándar.
- `/dossier` requiere seguir redirect a `.0` con cookies (el adapter usa cookie jar).
- SSL sede: certificado gestionado por espublico (`insecure_ssl: true`).
