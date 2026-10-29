# Arteixo — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Sede electrónica | https://sede.arteixo.org/sxc/es/ | Trámites, tablón, transparencia (plataforma SXC Diputación A Coruña) |
| Tablón de anuncios | https://sede.arteixo.org/sxc/es/informacion/tablon/index.html | Anuncios HTML; secciones «Urbanismo», «Urbanismo - Planeamiento»; PDF en `/sxc/export/sites/arteixo/recursos/downloads/Tablon/` |
| Procedimientos urbanismo | https://sede.arteixo.org/sxc/es/procedimientosytramites/ | Acordeón Urbanismo: licencia de edificación, demolición, comunicación previa de obra, certificado urbanístico, etc. |
| Web corporativa | https://arteixo.org/servizos/urbanismo/ | Información PXOM en tramitación (WordPress/Divi) |
| SIOTUGA inventario | https://siotuga.xunta.gal/siotuga/inventario.php?inv=1&idconcello=15005&lang=es_ES | Documentos de planeamento (clases 13/14) vía `query_document.php` + token de sesión |
| SIOTUGA urbanismo | https://siotuga.xunta.gal/siotuga/urb?lang=es_ES | Estado normativo (Normas subsidiarias 1995, INE 15005); enlace WMS cartografía |

## Listado de expedientes / proyectos

- **Tablón:** bloques `<div class="noticia">` con categoría (`h3`), fecha `p.fecha` (dd/mm/yyyy) y resumen `p`. Paginación `?page=N` (10 páginas visibles; ~100 anuncios recientes por página). Buscador POST (`query`, `search=search`) amplía resultados filtrando «Urbanismo» / «planeamiento».
- **Detalle:** página estática por anuncio; primer anexo PDF suele ser el BOP/anuncio (`ANUNCIO_PROG_*_ANEXO_*.pdf`).
- **SIOTUGA:** JSON array con `docnome`, `figura`, fechas; no geometría por expediente.

## Licencias

- No hay listado público de licencias concedidas (solo trámites informativos y tablón genérico).
- El adapter ingesta URLs de trámites de la sección Urbanismo de la sede (patrón Pozuelo) y anuncios del tablón que mencionan licencia/obra cuando existen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WMS planeamiento SIOTUGA / IDEG Xunta (clasificación municipal, no polígono por expediente del tablón).
  - Geoportal municipal gvSIG Online (17 capas temáticas, proyecto académico UPV 2025): sin URL pública estable enlazada desde arteixo.org en el momento de la investigación.
  - Anuncios del tablón: PDF sin georreferencia ni código de visor.
- **Estrategia:** metadatos + PDF del tablón; geocode del orquestador usa centroide municipal (`manifest.config.centroid`) + jitter. No se implementa `_fetch_geometry` (sin capa ArcGIS/WFS enlazable a cada fila del tablón).
- **Limitaciones:** SIOTUGA WMS es cartografía de planeamiento general; expedientes concretos no exponen `geom_geojson` en portal municipal.

## Limitaciones técnicas

- Plataforma SXC compartida con otros concellos da Coruña; ritmo de peticiones (`request_delay_s`).
- Buscador del tablón devuelve muchas coincidencias parciales; filtro por regex urbanística en el adapter.
- Sin boletín autonómico asociado en cola (`bocm_count: 0`).
