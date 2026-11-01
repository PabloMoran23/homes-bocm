# Benalmádena — investigación portal ayuntamiento

Municipio: **Benalmádena** (`benalmadena`), provincia de Málaga, Andalucía.

## URLs base y semillas

| Recurso | URL | Formato |
|---------|-----|---------|
| Web municipal | https://www.benalmadena.es | CMS propio (PHP) |
| Delegación Urbanismo | https://www.benalmadena.es/delegacion-de-urbanismo.html | HTML informativo |
| Información pública expedientes | https://www.benalmadena.es/contenido_transparencia.php?m=benalmadena-transparencia&s=informacion-publica-de-expedientes-de-urbanismo | HTML tablas + PDFs en `/docs/` (~36 bloques, ~88 PDFs) |
| Alias URL | https://www.benalmadena.es/informacion-publica-de-expedientes-de-urbanismo.html | Misma sección (menos contenido embebido) |
| PGOU vigente (transparencia) | https://www.benalmadena.es/contenido_transparencia.php?m=benalmadena-transparencia&s=pgou-planeamiento-general-vigente | PDFs innovaciones/modificaciones PGOU |
| Mapas urbanismo (estático) | https://www.benalmadena.es/urbanismo-mapas/mapa-general.jpg | Imagen JPG, no visor interactivo |
| Sede electrónica | https://sede.benalmadena.es/sta/ | STA TAO (T-Systems) |
| Tablón anuncios | https://sede.benalmadena.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_TABLON&lang=ES | `dataset_PTS_TABLON` JSON embebido (~26 filas visibles) |
| Catálogo trámites | https://sede.benalmadena.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_CATSERV&lang=ES | `dataset_CATSERV` (~89 trámites urbanismo/licencias) |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=29025 | Visor regional planeamiento (JSF) |

Detalle tablón: `doEvent?APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS_TABLON&lang=ES`.

## Listado de expedientes / proyectos

1. **Transparencia — IP expedientes:** tablas HTML con `<thead>` por expediente (título con número de expte., sector SP, estudio de detalle, etc.) y enlaces a anuncios/resúmenes ejecutivos en `https://www.benalmadena.es/docs/...pdf`. Principal fuente histórica del adapter.
2. **Tablón STA:** anuncios recientes (urbanismo, medio ambiente, etc.) con `descriptionProc`, `externString`, `pubDateIni`, `remitent`.
3. **PGOU transparencia:** PDFs de innovaciones y modificaciones puntuales del plan general.
4. **SITUA:** consulta del planeamiento aprobado en Andalucía (referencia, sin scrape de geometría por expediente).

## Licencias de obra

- **Catálogo sede:** trámites «Licencia de obra», comunicaciones previas, vados, declaraciones responsables, etc. (páginas informativas).
- **Tablón:** algún anuncio de licencias/uso de espacios; no hay listado masivo de concesiones con dirección.
- Formularios PDF en web (`/docs/procedimientos/urb*.pdf`) — trámites, no concesiones publicadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Mapa estático `urbanismo-mapas/mapa-general.jpg` sin servicio WMS/WFS ni enlace a expediente.
  - SITUA (`cid=29025`) — consulta documental del PGOU; API no orientada a polígonos por expediente municipal.
  - No se localizó ArcGIS/FeatureServer municipal público enlazado desde la sede o transparencia.
- **Estrategia:** sin `geom_geojson` en adapter; geocode con centroide municipal (`manifest.portal.config.centroid`) + jitter.
- **Limitaciones:** expedientes publicados como PDF; tablón sin coordenadas.

## Limitaciones generales

- Tablón STA expone ventana limitada de anuncios (~26 entradas); la IP web concentra el histórico.
- Respuesta tablón ~30–60 s; timeout recomendado ≥120 s.
- Muchos anuncios del tablón son no urbanísticos (padrón, subvenciones); filtros en adapter.
