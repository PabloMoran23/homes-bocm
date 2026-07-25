# Mijas — investigación portal ayuntamiento

**Municipio:** Mijas (Málaga, Andalucía)  
**BOJA:** 25 entradas en `ccaa_history_parsed_incremental.csv`  
**Fecha investigación:** 2026-07-25

## URLs base y páginas semilla

| Recurso | URL | Tecnología | Contenido |
|---------|-----|------------|-----------|
| Web corporativa | `https://www.mijas.es/portal/` | WordPress (qTranslate) | Urbanismo, expedientes, licencias |
| Sede espublico gestiona | `https://mijas.sedelectronica.es` | Wicket / eHome | Tablón, trámites, transparencia |
| Tablón de anuncios | `https://mijas.sedelectronica.es/board` | HTML tabla espublico | Edictos recientes (~10/página) |
| Derecho a la información | `/portal/urbanismo/derecho-a-la-informacion/` | WordPress | ZIP/PDF expedientes urbanísticos (~220 docs) |
| Planes parciales / especiales | `/portal/urbanismo/planes-parciales-de-ordenacion-planes-especiales-y-expedientes-de-adaptacion-al-pgou/` | WordPress | Expedientes SUP/SUNP históricos (~53 docs) |
| Planeamiento | `/portal/urbanismo/planeamiento/` | WordPress | PGOU, estudios de detalle |
| Licencias obras mayores | `/portal/urbanismo/licencias-de-obras-mayores/` | WordPress | Documentación licencias |
| Licencias obra menor | `/portal/urbanismo/licencias-de-obra-menor-concedidas-por-decreto/` | WordPress | PDFs históricos por decreto |
| Sede legacy | `https://sede.mijas.es` | ASP.NET IIS | Redirige a espublico; tablón en `mijas.sedelectronica.es/board` |
| Transparencia sede | `https://mijas.sedelectronica.es/transparency/` | espublico | Portal transparencia (sin scrape profundo) |

## Cómo se listan expedientes

### WordPress urbanismo

- Páginas estáticas con enlaces `<a href="...wp-content/uploads/...">` a PDF y ZIP.
- Títulos en texto del enlace (p. ej. «Expte. 2641», «Expte. 372 SUP R8 Rincón del Hinojal»).
- Fechas inferidas del path (`/2025/08/`) o del nombre de archivo.
- Sin API REST de expedientes; scrape determinista de HTML.

### Tablón espublico gestiona

- Tabla HTML con clases `class_name`, `class_folderCode`, `class_folderName`, `class_description`, `class_dateFrom`.
- Enlaces a `/preview-document/{uuid}`.
- Paginación AJAX (solo primera página scrapeada; suficiente junto con WP).
- Entradas urbanísticas recientes: planeamiento (p. ej. «División en Fases del Sector UER 2-3-4»).

### Licencias

- No hay dataset GeoJSON ni listado tabular de concesiones con coordenadas.
- Licencias mayores: documentación en página WordPress.
- Licencias menores: PDFs agregados históricos (sin parseo de filas).
- Tablón: edictos de licencia/actividad cuando se publican.
- Trámites: `mijas.sedelectronica.es/dossier` (catálogo, sin histórico).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - No hay visor urbanístico municipal propio enlazado desde la sección urbanismo.
  - PRP Málaga (`gis.prpmalaga.es`) no expone REST accesible desde CI.
  - SITUA/Junta de Andalucía: planeamiento regional, sin enlace expediente↔polígono del ayuntamiento.
  - Documentación en PDF/ZIP sin GeoJSON embebido ni WFS municipal.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter (`centroid: [36.5957, -4.6375]`).
- **Limitaciones:** Sin ArcGIS/WFS/GeoJSON público enlazable a códigos de expediente; tablón y WP solo documentos.

## Limitaciones

- Sede legacy (`sede.mijas.es`) usa certificado distinto; tablón migrado a `mijas.sedelectronica.es`.
- Tablón paginado: solo primera página en cada ejecución (WP compensa volumen).
- Licencias históricas en PDF agregado, no filas individuales scrapeables.
- Sin geometría de ámbito en fuentes públicas.

## Referencias de implementación

- Tablón espublico: `municipio/adapters/coin.py`, `municipio/adapters/ronda.py`
- WordPress semillas: `municipio/adapters/villanueva_de_la_canada.py`
