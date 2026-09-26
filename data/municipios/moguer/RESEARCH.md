# Moguer — investigación portal ayuntamiento

**Municipio:** Moguer (Huelva, Andalucía)  
**Slug:** `moguer`  
**BOJA:** `boja` (2 entradas en CSV)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (SAGA Dip. Huelva) | https://www.aytomoguer.es | Portal corporativo OpenCms/SAGA |
| Urbanismo | https://www.aytomoguer.es/es/servicios/urbanismo/ | Enlaces a sede y planeamiento |
| Planeamiento urbanístico | https://www.aytomoguer.es/es/planeamiento-urbanistico-de-moguer/ | Índice planeamiento |
| Planeamiento municipal | https://www.aytomoguer.es/es/planeamiento-urbanistico-de-moguer/planeamiento-municipal/ | Galerías PDF (NNSS, adaptación, Mazagón) |
| Sede electrónica (espublico) | https://moguer.sedelectronica.es | Tablón, trámites, transparencia |
| Tablón de anuncios | https://moguer.sedelectronica.es/board/9753e838-f59b-11de-b600-00237da12c6a/ | Edictos HTML tabla |
| Obras y Urbanismo | https://moguer.sedelectronica.es/citizen-service/17e16d13-06d2-420a-acf8-9e27134736b4 | Info licencias y DR |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Consulta planeamiento regional |

**Nota SSL:** `www.moguer.es` redirige a HTTPS pero el certificado es para `aytomoguer.es`; el adapter usa `insecure_ssl: true`.

## Cómo se listan expedientes / proyectos

1. **Galerías SAGA:** páginas estáticas con enlaces directos a PDF en `/export/sites/moguer/es/.galleries/`. ~47 documentos en planeamiento municipal: texto refundido NNSS (2010), adaptación parcial (2010), modificación Mazagón, planimetrías de clasificación, zonificación, redes.
2. **Tablón espublico:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`. Enlaces a `/preview-document/{uuid}`. Primera página (~10 filas); mayoría empleo público en scraping.
3. **SITUA:** enlace genérico a buscador Junta de Andalucía (sin API scrapeable por expediente).

## Cómo se publican licencias

- **No hay listado histórico público** de licencias concedidas en el portal municipal.
- Página «Obras y Urbanismo» en sede describe declaraciones responsables, licencias urbanísticas, comunicaciones previas y actuaciones en suelo rústico (informativa).
- El tablón sede publica ocasionalmente edictos; la mayoría de filas visibles son empleo/presupuesto.
- Trámites de licencia vía sede (`/dossier`, `/expedientes`) requieren identificación.
- El adapter devuelve páginas informativas del tablón, Obras y Urbanismo y catálogo de trámites (patrón Lepe/Cártama).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - No hay visor urbanístico municipal (ArcGIS, GeoJSON, WFS) enlazado desde el portal.
  - SITUA (Junta de Andalucía) ofrece consulta de planeamiento a escala municipal pero sin polígonos scrapeables por código de expediente desde el adapter.
  - PDFs de planeamiento son planimetrías raster sin geometría vectorial accesible.
  - No se detectó eMap400 ni geoportal municipal.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** solo PDFs sin georreferencia vectorial; tablón sin coordenadas; consulta de expedientes autenticada.

## Limitaciones

- Certificado SSL inválido/mismatch en `www.moguer.es` vs `aytomoguer.es`.
- Tablón sede: paginación Wicket no scrapeada (solo primera página).
- Sin listado público de licencias históricas.
- `/dossier` puede ser lento o interrumpir conexión en CI (timeout).

## Referencias de patrón

- **Lepe** (`lepe.py`): Huelva, Drupal/espublico + PDFs planeamiento.
- **Cártama** (`cartama.py`): espublico tablón + páginas informativas licencias.
- **Bornos** (`bornos.py`): SITUA + PDFs planeamiento Andalucía.
