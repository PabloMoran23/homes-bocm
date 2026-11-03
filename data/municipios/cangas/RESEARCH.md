# Cangas — investigación portal ayuntamiento

Municipio: **Cangas** (`cangas`) — Galicia, provincia Pontevedra (Morrazo).  
INE: **36008**. Sin boletín regional asociado en cola (`bocm_count: 0`).

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Web corporativa | https://cangas.gal | Drupal 8 (tema Gavias) |
| Urbanismo | https://cangas.gal/es/areas/urbanismo | PXOM, PEPRI, normativa, enlaces transparencia sede |
| Inventario municipal (web) | https://cangas.gal/es/areas/urbanismo/inventario | PDFs catálogo arqueológico / planos |
| PXOM | https://cangas.gal/es/areas/urbanismo/pxom | Documentación proceso PXOM |
| PEPRI | https://cangas.gal/es/areas/urbanismo/pepri | PDF PEPRI |
| Sede electrónica | https://cangas.sedelectronica.gal | espublico gestiona (Wicket) |
| Taboleiro de anuncios | https://cangas.sedelectronica.gal/board | Tabla HTML (`class_name`, `class_folderCode`, `preview-document/…`) |
| Transparencia urbanismo (sede) | p. ej. `…/transparency/f8e126cf-…/` | Filas con `preview-document` (varias carpetas enlazadas desde web) |
| Catálogo trámites | https://cangas.sedelectronica.gal/dossier | Urbanismo: comunicación previa, licencia obras, primera ocupación (timeout frecuente >45s) |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36008&lang=es_ES | Token + cookie jar; POST `query_document.php` |
| SIOTUGA tabla | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | Metadatos autonómicos |

## Proyectos / expedientes

1. **SIOTUGA:** ~16 instrumentos plan xeral (idclase 14) y ~31 de desenvolvemento (idclase 13) para INE 36008 (`docnome`, `figura`, `fechaaddef`).
2. **Web Drupal:** PDFs en `/sites/default/files/…` (PXOM, PEPRI, normativa, inventario).
3. **Taboleiro sede:** HTML scrapeable; entradas recientes mezclan ordenanzas fiscales e información pública (expedientes tipo `8808/2025`).
4. **Transparencia sede:** documentos urbanísticos en carpetas UUID con enlaces `preview-document`.
5. **Consulta expedientes** en sede requiere certificado (carpeta ciudadana) — no usable para scrape público.

## Licencias de obra

- No hay dataset abierto de licencias concedidas con dirección/coordenadas.
- Catálogo sede incluye trámites de urbanismo (comunicación previa, licencia obras mayores, primera ocupación).
- Taboleiro puede publicar edictos puntuales; el adapter ingiere **páginas informativas** + filas del tablón que coinciden con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SIOTUGA WMS por concello: `https://siotuga.xunta.gal/siotuga/ws?codine=36008&SERVICE=WMS&REQUEST=GetCapabilities` (capas raster por documento de planeamento).
  - Visor cartográfico Xunta: https://siotuga.xunta.gal/siotuga/carto
- **Estrategia:** metadatos vía `query_document.php`; polígonos vectoriales no expuestos en API REST simple enlazable al código de expediente del tablón. WMS requiere identificar capa por `iddoc` (raster).
- **Limitaciones:** sin visor municipal ArcGIS público; tablón y PDFs sin georreferencia; licencias sin coords. El orquestador aplica centroide municipal + jitter cuando no hay `geom_geojson`.

## Limitaciones generales

- `/dossier` de la sede a veces no responde en tiempo útil en CI cloud.
- Token SIOTUGA ligado a sesión HTTP (cookie jar obligatorio).
- Taboleiro muestra solo la página actual (~10 filas visibles en prueba).

## Adapter

- `municipio/adapters/cangas.py` — SIOTUGA + crawl Drupal + taboleiro/transparencia espublico + semillas fijas (PXOM, PEPRI, trámites).
