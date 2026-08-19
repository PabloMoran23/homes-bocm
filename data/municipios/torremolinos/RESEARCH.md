# Torremolinos — investigación portal ayuntamiento

**Municipio:** Torremolinos (Málaga, Andalucía)  
**BOJA:** 6 entradas en `ccaa_history_parsed_incremental.csv`  
**Fecha investigación:** 2026-08-09

## URLs base y páginas semilla

| Recurso | URL | Tecnología | Contenido |
|---------|-----|------------|-----------|
| Web corporativa | `https://www.torremolinos.es` | WordPress Arthemia v4 | Urbanismo, PGOU vigente, modificaciones puntuales |
| Urbanismo | `/ayuntamiento/urbanismo-infraestructuras/` | WordPress | PGOU 96/97, planos, ME/SUP, PDFs en `wpsystem/wp-content/uploads` |
| Portal transparencia | `https://transparencia.torremolinos.es/obras-publicas/` | WordPress | Expedientes IP, estudios de ordenación, ATU, BOP |
| Planea Torremolinos | `https://planea.torremolinos.es/` | WordPress Kadence | PGOM/POU en trámite, participación ciudadana |
| Documentación Planea | `https://planea.torremolinos.es/documentacion/` | WordPress | Enlaces a PGOU vigente, PGOM y POU |
| Sede espublico gestiona | `https://torremolinos.sedelectronica.es` | Wicket / eHome | Tablón, trámites, consulta expedientes (auth) |
| Tablón de anuncios | `https://torremolinos.sedelectronica.es/board` | HTML tabla espublico | Edictos recientes (~10/página) |
| Sede legacy | `https://sede.torremolinos.es` | — | Redirige a `torremolinos.sedelectronica.es` |

## Cómo se listan expedientes

### WordPress urbanismo (www.torremolinos.es)

- Página estática con toggles y enlaces a PDF (wp-content/uploads) y Google Drive.
- Modificaciones puntuales PGOU (ME SUP-R-1-14, ART-221, etc.) con PDFs directos.
- Fechas inferidas del path (`/2024/04/`) o del nombre de archivo.
- Sin API REST de expedientes; scrape determinista de HTML.

### Portal de transparencia

- Sección «Información Urbanística» con bloques `<strong>` por expediente (p. ej. «Expediente 7567/2024», ATU Bachiller Palma).
- PDFs en `transparencia.torremolinos.es/wp/wp-content/uploads/`.
- Anuncios de información pública con plazo y sede física (Delegación Regeneración Urbana).

### Planea Torremolinos

- Microsite del nuevo planeamiento (PGOM/POU) tras anulación PGOU 2020.
- Documentación enlazada al portal de transparencia; sin listado de expedientes individuales.

### Tablón espublico gestiona

- Tabla HTML con clases `class_name`, `class_folderCode`, `class_folderName`, `class_description`, `class_dateFrom`.
- Enlaces a `/preview-document/{uuid}`.
- En la fecha de investigación predominan anuncios de empleo público; entradas urbanísticas aparecen esporádicamente.

### Licencias

- No hay dataset GeoJSON ni listado tabular público de licencias concedidas con coordenadas.
- Trámites de licencia vía sede (`/dossier`); consulta expedientes requiere autenticación.
- Tablón: edictos de licencia/actividad cuando se publican.
- Web urbanismo: documentación PGOU, no concesiones de licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - `planea.torremolinos.es`: participación y documentación; sin visor ArcGIS ni WFS.
  - VITUA/SITUA (Junta de Andalucía): capas de planeamiento general regional, sin enlace expediente↔polígono municipal.
  - PRP Málaga (`gis.prpmalaga.es`): no expone REST accesible desde CI para Torremolinos.
  - Documentación en PDF/Google Drive sin GeoJSON embebido ni WFS municipal.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter (`centroid: [36.6244, -4.4997]`).
- **Limitaciones:** Sin ArcGIS/WFS/GeoJSON público enlazable a códigos de expediente; fuentes son PDFs y tablón documental.

## Limitaciones

- Tablón paginado: solo primera página en cada ejecución (transparencia y WP compensan volumen).
- Licencias históricas no publicadas en listado tabular; solo páginas informativas de trámites.
- Muchos planos PGOU en Google Drive (no scrapeables como metadatos estructurados; solo enlaces de la página WP).
- Sin geometría de ámbito en fuentes públicas.

## Referencias de implementación

- WordPress + espublico: `municipio/adapters/mijas.py`
- Tablón espublico: `municipio/adapters/competa.py`, `municipio/adapters/cartama.py`
