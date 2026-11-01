# Culleredo — portal ayuntamiento

## Fuentes base

| Recurso | URL |
|---------|-----|
| Web corporativa (Drupal) | https://www.culleredo.es |
| Urbanismo / planeamento | https://www.culleredo.es/es/urbanredes |
| Ordenaciones en tramitación | https://www.culleredo.es/es/node/8163 |
| Ordenaciones aprobadas (PDFs) | https://www.culleredo.es/es/node/8164 |
| Criterios / convenios | https://www.culleredo.es/es/node/8162 |
| Sede Sedipualba (catálogo) | https://sede.culleredo.es |
| Catálogo urbanismo (URB.*) | https://sede.culleredo.es/catalogoservicios.aspx?ambito=2&area=1821 |
| Sede OpenSIAC | https://sedeelectronica.culleredo.es |
| Tablón (enlace web) | http://sede.culleredo.es/tablondeanuncios |
| SIOTUGA visor | https://siotuga.xunta.gal/siotuga/visor |
| SIOTUGA inventario INE 15031 | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15031&lang=es_ES |

## Proyectos / expedientes

- **SIOTUGA:** PGOU 1987 + ~99 instrumentos de desarrollo (SUNP, PS, PERI…) vía `query_document.php` (`idclase` 14 y 13). Metadatos y fechas de aprobación; sin scrape de geometría por expediente.
- **Drupal:** nodos 8162–8164 enlazan anuncios (p. ej. PERI UA-58/59 en Vilaboa, node/7920) y PDFs de planeamiento aprobado bajo `/files/documentos/urbanismo/pxom87/…`.
- **Información pública en tramitación:** la web remite al tablón de la sede; en este entorno OpenSIAC `infopublica` devuelve 404 (no hay listado HTML scrapeable equivalente a Paterna/Sabadell).
- Codificación mixta UTF-8 (web) y páginas sede en castellano/galego.

## Licencias

- **No** hay registro público de licencias concedidas con fecha y ubicación.
- Procedimientos **URB.01–URB.07** (obra mayor, comunicaciones previas, primera ocupación…) en el catálogo Sedipualba `area=1821`.
- El adapter ingiere filas **informativas** de trámite (`carpetaciudadana/tramite.aspx?idtramite=…`).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Visor SIOTUGA (`siotuga/visor`, concello Culleredo 15031) con capas de planeamiento aprobado; no expone join estable código expediente/tablon → polígono para scraping automático sin sesión de visor ArcGIS.
- **Estrategia:** Metadatos de planeamiento desde inventario SIOTUGA + documentos Drupal; el orquestador aplica centroide municipal (`manifest.config.centroid`) + jitter en `geocode`. No se rellena `geom_geojson` en el adapter.
- **Limitaciones:** Certificado SSL intermedio no confiable en `sedeelectronica.culleredo.es` / `sede.culleredo.es` (se usa `insecure_ssl`). Tablón OpenSIAC sin endpoint `infopublica` activo.

## Limitaciones técnicas

- `sede.culleredo.es/catalogoservicios.aspx` accesible con verificación SSL desactivada; `sedeelectronica.culleredo.es` mismo caso.
- Token SIOTUGA debe obtenerse en la misma sesión HTTP (CookieJar) antes del POST a `query_document.php`.
- BOCM: sin boletín asociado en cola (`bocm_count: 0`).
