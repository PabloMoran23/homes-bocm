# Calahorra — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Slug | `calahorra` |
| INE | 26012 |
| Web | https://calahorra.es (WordPress) |
| Sede | https://sede.calahorra.es (STA / T-Systems) |
| Visor | https://gis.calahorra.es (UrbanCity) |

## Fuentes

### Portal web (WordPress)

- **Base:** https://calahorra.es
- **Urbanismo (noticias):** categoría `urbanismo` — REST `wp-json/wp/v2/posts?categories=204`
- **Documentación planeamiento:** CPT `documento` listado en `documento-sitemap.xml` (+ `documento-sitemap2.xml`). URLs `/documento/...` con título en `<title>` y PDFs en `/wp-content/uploads/`.
- **Transparencia:** https://calahorra.es/el-ayuntamiento/portal-de-transparencia/ (planeamiento enlazado desde notas de urbanismo)

### Sede electrónica STA

- **Tablón:** https://sede.calahorra.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON  
  - Dataset embebido: `var dataset_TABLON = [...]` (~155 anuncios vigentes).  
  - Detalle: `...&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`
- **Catálogo trámites:** `PAGE_CODE=CATALOGO`, dataset `CATSERV` — trámites con keywords `UR` / urbanismo (licencias, cédulas, parcelación).
- **Nota:** `KEY=all` en tablón devuelve dataset vacío/placeholder; usar URL sin `KEY`.

### Licencias

- No hay listado público de concesiones de licencia de obra (solo anuncios puntuales en tablón, p. ej. licencia conjunta ambiental y de obras).
- **Adapter:** trámites informativos del catálogo STA + anuncios de tablón que mencionen licencia/obra.

### Proyectos / expedientes

1. **WFS UrbanCity** — instrumentos de planeamiento con polígono (29 features).
2. **Documentos** — sitemap `documento` filtrado (modificaciones PGM, planes parciales, convenios, proyectos de urbanización, interpretaciones).
3. **Tablón STA** — aprobaciones iniciales, información pública, U.E., etc.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - GeoServer WFS: `https://gis.calahorra.es/geoserver/calahorra_urban_city_instrumentos/wfs`
  - Capa: `calahorra_urban_city_instrumentos:instrumentos`
  - Campos: `name`, `description`, `instrument_type_name`, `approval_date`, geometría MultiPolygon en EPSG:4326 vía `outputFormat=application/json&srsName=EPSG:4326`
  - Visor web Angular: https://gis.calahorra.es (UrbanCity; capas adicionales en workspace `calahorra_urban_city`)
  - Referencia regional: IDE La Rioja https://www.iderioja.larioja.org/geovisor/index_fs.php?map=CALAHORRA (catastro; no enlazado por expediente)
- **Estrategia:** descarga WFS de instrumentos → filas con `geom_geojson`; enriquecimiento por coincidencia de tokens del título para documentos/tablón.
- **Limitaciones:** expedientes concretos (Exp: …-UR-…) no tienen capa WFS individual; geometría heredada del instrumento/planeamiento relacionado cuando hay match textual. Licencias del tablón suelen ir sin polígono.

## Limitaciones generales

- Tablón mezcla materias no urbanísticas (empleo, subvenciones); filtrado por regex.
- CPT `documento` sin REST API pública; ingest vía sitemap + scrape ligero de `<title>`.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
