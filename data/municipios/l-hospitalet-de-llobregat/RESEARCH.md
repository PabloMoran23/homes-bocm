# L'Hospitalet de Llobregat — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.l-h.cat |
| Urbanismo y vivienda | https://www.l-h.cat/urbanismehabitatge/264048_1.aspx?id=1 |
| Sede electrónica | https://seuelectronica.l-h.cat |
| Consultas públicas previas (planeamiento) | https://seuelectronica.l-h.cat/2317545_2.aspx |
| Trámites urbanismo y obras | https://seuelectronica.l-h.cat/tramits/r/navegacioTramits.aspx (tema *Urbanisme i permisos d'obres*) |
| Tauler d'anuncis (e-TAULER CAOC) | https://tauler.seu.cat/inici.do?idens=810170005 |
| Cartografía planeamiento (CPd-LH) | https://www.l-h.cat/itcartografia/1590282_2.aspx |
| Geoportal — guía urbana | https://geoportal.l-h.cat/guiaurbana/ |
| Geoportal — urbanismo (expedientes) | https://geoportal.l-h.cat/urbanisme/ |

**Nota:** el dominio histórico `l-hospitalet.cat` está caído/redirigido; el dominio operativo es **`l-h.cat`**.

## Proyectos / expedientes

- **Fuente principal:** API **CartoAPI** del geoportal municipal (MapiaBox / Infraplan).
  - Endpoint: `GET https://geoportal.l-h.cat/CartoAPI.ashx?request=GetLayer&layer=PLA_AMBITS&language=ca&srid=EPSG:4326`
  - Respuesta: **GeoJSON FeatureCollection** (~500+ ámbitos de planeamiento).
  - Campos útiles: `name`, `expedientG` (RPUC), `instrument`, `tipus`, `dataAprovacio`, `dataPublicacio`, `description` (HTML con enlaces PDF).
- **Complemento:** página de **consulta pública previa** en la sede (memorias PDF vía `obreFitxer.ashx`); no siempre están aún en la capa PLA_AMBITS.

## Licencias de obra

- No hay listado masivo público de concesiones (como tablón HTML indexable).
- **e-TAULER** (`tauler.seu.cat`) es una SPA React sin feed RSS/API pública en esta investigación.
- La sede publica **trámites** de licencia (obra mayor/menor, comunicación previa, declaración responsable) en `detallTramit.aspx` — filas informativas, no concesiones con fecha/distrito.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:** CartoAPI capa `PLA_AMBITS` (polígonos en `EPSG:4326` vía parámetro `srid`).
- **Estrategia:** descarga masiva del FeatureCollection en el adapter; reproyección **EPSG:25831 → EPSG:4326** (el parámetro `srid=EPSG:4326` no transforma las coordenadas en la API); `geom_geojson` + centroide para `lat`/`lon`.
- **Limitaciones:** filtros `filter=param:'value'` del visor web no reducen el payload en pruebas curl (se filtra en cliente); consultas públicas y trámites de licencia no aportan geometría.

## Limitaciones generales

- Dominio legacy `www.l-hospitalet.cat` no usable.
- Tablón de anuncios requiere navegación SPA (no scrape determinista sin API).
- Fechas de licencias concesionadas no disponibles en fuentes públicas indexadas.
