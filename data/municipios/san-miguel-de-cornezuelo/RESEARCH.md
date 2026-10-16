# San Miguel de Cornezuelo — investigación portal ayuntamiento

Localidad del municipio de **Valle de Manzanedo** (Burgos, Castilla y León). Código INE entidad `09409001500`; municipio PLAI `09` / `409` (`09409`). Población ~10 hab.; planeamiento y sede electrónica a nivel de ayuntamiento de Valle de Manzanedo.

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://valledemanzanedo.burgos.es | Drupal, tema Toools (Diputación Burgos) |
| Sede electrónica | https://valledemanzanedo.sedelectronica.es | espublico gestiona — tablón, trámites, transparencia |
| Tablón de anuncios | https://valledemanzanedo.sedelectronica.es/board | Anuncios Wicket |
| Normativa | https://valledemanzanedo.burgos.es/normativa | Enlaces a NUM y ordenanzas |
| NUM (PDFs) | https://valledemanzanedo.burgos.es/normativa/normas-urbanisticas-municipales-documentos-de-aprobacion-inicial | Documentación fase II aprobación inicial (múltiples PDF en `/sites/valledemanzanedo/files/urbanismo/`) |
| PLAI JCyL | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?municipio=409&provincia=9 | Modificación NUM parcela en **San Miguel de Cornezuelo** (exp. 120/21W) |
| PLAU CyL | http://www.jcyl.es/plau/lplanes.plau?municipio=09409 | Archivo histórico planeamiento |
| OVC Diputación | https://ovc.diputaciondeburgos.es/ | Visor cartográfico provincial (enlace menú web) |

## Expedientes / proyectos

- **Drupal:** NUM del término municipal de Valle de Manzanedo (aplica a Cornezuelo y resto de núcleos); PDFs estáticos enlazados desde normativa.
- **PLAI JCyL:** al menos un expediente de modificación de NUM con ámbito explícito en San Miguel de Cornezuelo (cambio calificación parcela ref. catastral `09421A001252080000UY`).
- **IDECyL WFS:** instrumentos y sectores del municipio **Valle de Manzanedo** (`n_mun = 'Valle de Manzanedo'`).
- **Tablón sede:** sin filas urbanísticas destacadas en muestra HTML estática; adapter parsea `preview-document` si aparecen.

## Licencias de obra

- No hay listado público de concesiones de licencia en el tablón en la muestra actual.
- Trámites vía sede (`/dossier`, transparencia) — páginas informativas.
- El adapter devuelve trámites informativos cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Valle de Manzanedo'`, `srsName=EPSG:4326`
  - OVC Diputación Burgos (sin API expediente enlazada al tablón)
- **Estrategia:** ingestar polígonos WFS como proyectos del municipio matriz; enriquecer por código sector si aparece en título PLAI/tablón.
- **Limitaciones:** sin visor urbanístico municipal propio; licencias sin georreferencia; geometría WFS a nivel instrumento/sector del término de Valle de Manzanedo, no parcela individual del expediente PLAI.

## Geocodificación (localidad)

- IGN no publica límite municipal para la localidad; en `manifest.yaml` se usa `geocode.official_boundary_municipio: Valle de Manzanedo` y centroide de la localidad para jitter.

## Limitaciones

- La localidad no dispone de web propia; toda la gestión urbanística es del ayuntamiento de Valle de Manzanedo.
- Tablón espublico puede cargar filas vía AJAX (Wicket); el adapter usa HTML inicial + enlaces `preview-document`.
- SSL sede: `insecure_ssl: true` en manifest (patrón Burgos/espublico).
