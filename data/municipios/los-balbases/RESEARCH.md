# Los Balbases — investigación portal ayuntamiento

Municipio: Los Balbases (Burgos, Castilla y León). Código INE `09034`; PlanPublica JCyL provincia `09`, municipio `034`.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://losbalbases.es | Drupal 10, tema Toools (Diputación Burgos) |
| Sede electrónica | https://losbalbases.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://losbalbases.sedelectronica.es/board | Tablón Wicket (vacío en muestra actual) |
| Transparencia | https://losbalbases.sedelectronica.es/transparency | Sección 7 «Urbanismo, obras públicas y medio ambiente» (17 docs, AJAX) |
| Anuncios Drupal | https://losbalbases.es/noticias/anuncios | Consulta pública modificación NUM 2 (PDF) |
| Normativa | https://losbalbases.es/normativa | Enlace institucional |
| Archivo PLAU JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=034 | 3 documentos aprobados (NUM + 2 modificaciones) |
| Archivo PLAI JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=034 | Sin documentos en información pública |
| Visor provincial | https://ovc.diputaciondeburgos.es/ | Visor cartografía Diputación Burgos (sin enlace directo a expedientes) |

## Expedientes / proyectos

- **Principal:** archivo PlanPublica JCyL (`searchVPubDocMuniPlau.do`) — tabla HTML con Libro, Instrumento, fechas y título. Documentos descargables vía `openDocumento.do?cDocId=` cuando el HTML expone `doOpen(...)`.
- **Geometría:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Los Balbases'` (`c_mun = '09034'`).
- **Drupal:** anuncio de consulta pública previa a modificación NUM 2 (`consulta_publica.pdf`).
- **Tablón sede:** sin anuncios publicados en la muestra actual (0 filas con `preview-document`).

Instrumentos PLAU identificados: NORMAS URBANÍSTICAS MUNICIPALES (2012), modificación NUM aprovechamiento/alturas (2019), modificación NUM EQ-PB (2024).

Sectores WFS: `SUR-I`, `SUR-R`.

## Licencias de obra

- No hay listado público de concesiones en el tablón.
- Catálogo sede `/dossier` con ~25 trámites urbanísticos/licencias (páginas informativas espublico).
- El adapter devuelve trámites informativos cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Los Balbases'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar features WFS como proyectos con polígono; enriquecer filas PlanPublica/Drupal por coincidencia de título o códigos sector (`SUR-I`, `SUR-R`).
- **Limitaciones:** sin visor municipal ArcGIS; licencias sin georreferencia; tablón vacío; geometría WFS a nivel instrumento/sector, no expediente individual; transparencia urbanismo requiere AJAX Wicket.

## Limitaciones

- Tablón espublico sin anuncios activos.
- PLAI JCyL vacío para este municipio.
- Drupal sin sección urbanismo dedicada; solo anuncios históricos.
- SSL sede gestionado por espublico (adapter usa `insecure_ssl`).
