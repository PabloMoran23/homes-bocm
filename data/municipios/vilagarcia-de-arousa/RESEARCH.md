# Vilagarcía de Arousa — investigación portal ayuntamiento

Municipio: **Vilagarcía de Arousa** (`vilagarcia-de-arousa`) — Galicia, provincia Pontevedra (Salnés).  
INE: **36060**. Sin boletín regional asociado en la cola (`bocm_count: 0`).

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://vilagarcia.es/ | Portal clásico ASP (servicios, noticias). |
| Urbanismo (web) | https://vilagarcia.es/servicios/urbanismo.asp | Xerencia de Urbanismo — contacto y funciones. |
| Sede electrónica | https://sede.vilagarcia.gal/ | Plataforma **Cividas** (JSF/PrimeFaces). |
| Tablón de anuncios | https://sede.vilagarcia.gal/public/bulletin/bulletin-index.xhtml | ~800 anuncios; filtro por remitente **XERENCIA DE URBANISMO**. |
| Detalle anuncio | `.../bulletin-details.xhtml?idtaskdata={id}` | Título, fecha publicación, categoría, PDF adjunto. |
| Transparencia planeamiento | https://sede.vilagarcia.gal/public/dynamic/transparency/planninginfo/ | Información de planificación (marco Cividas; sin listado expediente scrapeable). |
| Catálogo trámites | https://sede.vilagarcia.gal/public/catalog/catalog-index.xhtml | Procedimiento **02001** licencias y comunicaciones previas. |
| Formularios urbanismo | https://sede.vilagarcia.gal/public/publications/list/forms/FORMS | Bloque 02 Xerencia de Urbanismo. |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=36060&lang=es_ES | PXOM + instrumentos de desarrollo (API POST `query_document.php`). |

## Expedientes / proyectos

- **Tablón sede:** listado HTML estático en una sola página (`idtaskdata` en enlaces). Anuncios de urbanismo con aprobaciones, estudios de detalle, proyectos de urbanización, entidades urbanísticas, etc.
- **SIOTUGA:** `idclase=14` (plan xeral, 9 docs) y `idclase=13` (desarrollo/parciales, ~73 docs; adapter limita a 45).
- **Transparencia `planninginfo`:** página informativa sin tabla de expedientes enlazable por código.
- **Estrategia adapter:** semillas fijas + SIOTUGA + tablón filtrado (`XERENCIA DE URBANISMO` + regex urbanismo). Fecha de publicación desde detalle del anuncio cuando falta en listado.

## Licencias

- No hay registro público de licencias concedidas (solo trámites).
- Catálogo **02001** (licencias y comunicaciones previas) y formularios 020xx en sede.
- Estrategia: filas informativas de trámites (patrón Pozuelo/Dozón).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - SIOTUGA: inventario documental PDF, sin WMS/ArcGIS por expediente.
  - Sede Cividas: anuncios en PDF/HTML sin coordenadas ni enlace a visor.
  - Web municipal: sin visor urbanístico ni datos abiertos georreferenciados.
  - Xunta (`mapas.xunta.gal`): capas autonómicas sin join estable a `idtaskdata` del tablón.
- **Estrategia:** sin `geom_geojson`; orquestador usa centroide manifest + jitter.
- **Limitaciones:** tablón monolítico; detalle requiere una petición por anuncio para fecha.

## Limitaciones técnicas

- SIOTUGA requiere cookie jar + token de sesión en POST.
- User-Agent identificable y `request_delay_s: 0.35`.
- Certificados TLS válidos (no `insecure_ssl`).
