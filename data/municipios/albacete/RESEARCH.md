# Albacete — investigación portal ayuntamiento

Municipio: **Albacete** (`albacete`) — Castilla-La Mancha, provincia Albacete. Sin boletín regional asociado en cola (`bocm_count: 0`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Sede electrónica (Gerencia Urbanismo) | https://gerenciaurbanismo.sedipualba.es/ |
| Tablón de anuncios | https://gerenciaurbanismo.sedipualba.es/tablondeanuncios/default.aspx |
| Tablón RSS | https://gerenciaurbanismo.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo de trámites | https://gerenciaurbanismo.sedipualba.es/catalogoservicios.aspx |
| Web Gerencia Urbanismo (Drupal) | https://gerencia-urbanismo.albacete.es/es/urbanismo/... |
| Procedimientos en tramitación / IP | https://gerencia-urbanismo.albacete.es/es/urbanismo/procedimientos-tramitacion-informacion-publica |
| Planes y proyectos | https://gerencia-urbanismo.albacete.es/es/urbanismo/planes-desarrollo-instrumentos-gestion-proyectos |
| IDE municipal (gvSIG Online) | https://ide.ayto-albacete.es/gvsigonline/ |
| Planeamiento CLM (ArcGIS) | https://geoservicios.castillalamancha.es/arcgis/rest/services/Vector/Planeamiento_Municipal/MapServer |

## CMS / tecnología

- **Sedipualba / SEGEX** en subdominio `gerenciaurbanismo.sedipualba.es`: tablón ASP.NET (tabla HTML ~30 anuncios visibles), RSS 2.0 (`iso-8859-1`), catálogo de trámites con enlaces `carpetaciudadana/tramite.aspx?idtramite=…`.
- **Drupal** en `gerencia-urbanismo.albacete.es` para documentación de planeamiento (sectores, PGOU, IP). Acceso a expedientes en trámite requiere legitimación / cita previa.
- Integración IDE ↔ Sedipualba documentada públicamente (gvSIG blog): visor urbanismo temático enlazado al gestor de expedientes (no API REST pública simple).

## Proyectos / expedientes urbanísticos

**Fuente principal (pública, scrapeable):** tablón Sedipualba — anuncios de **información pública** (p. ej. instalaciones fotovoltaicas con referencia catastral `Pº… Pª…`), modificaciones de planeamiento, convocatorias internas filtradas por regex.

**Fuente complementaria:** páginas Drupal de la Gerencia (listados de planes parciales, PGOU, estudios de detalle). En entorno cloud agent a menudo **timeout TLS** hacia `gerencia-urbanismo.albacete.es` y `www.ayto-albacete.es`; el adapter intenta semillas con timeout corto y continúa con tablón.

**Formato:** HTML en tablón + PDFs en `tablondeanuncios/documento.aspx?id=…` cuando existen.

## Licencias de obra

No hay dataset público de licencias concedidas. El catálogo Sedipualba expone trámites informativos, entre ellos:

- Declaración responsable por ejecución de obras (`idtramite=19391`)
- Instancia general (`idtramite=2159`)

Las licencias publicadas en tablón (si aparecen) se capturan como filas `edicto tablón`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **CLM ArcGIS** `Vector/Planeamiento_Municipal/0` — polígono del instrumento PGOU del municipio (`COD_INE=02003`, `NOM_PLAN=Plan General de Ordenación Urbana`). Query: `f=geojson`, `outSR=4326`, `returnGeometry=true`.
  - **IDE Albacete** (gvSIG Online, servicios OGC en `ide.ayto-albacete.es`) — visor urbanismo integrado con expedientes; **no accesible** desde el entorno del agente (timeout).
  - Anuncios IP citan parcelas (`Pº78 Pª1`) pero **sin** servicio GIS público enlazado por código de expediente.
- **Estrategia adapter:**
  - Fila proyecto PGOU con polígono CLM + centroide.
  - Anuncios tablón sin geometría per-expediente (orquestador: centroide municipio + jitter).
- **Limitaciones:** sin WFS/ArcGIS municipal por parcela; Drupal/IDE inaccesibles en CI; tablón mezcla empleo público — filtro `RE_NOISE`.

## Limitaciones generales

- Expedientes en trámite no son consultables sin interés legítimo / firma (FAQ Gerencia).
- Tablón: una página (~30 filas) sin paginación visible.
- `www.ayto-albacete.es` y subdominio gerencia pueden bloquear o tardar desde IPs de cloud.
