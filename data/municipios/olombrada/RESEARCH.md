# Olombrada — investigación portal ayuntamiento

Municipio: **Olombrada** (`olombrada`), provincia Segovia, Castilla y León. Código PLAI/JCYL `40149` (provincia 40, municipio 149).

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web oficial (Liferay Segovia16) | https://www.olombrada.es |
| Urbanismo (web propia) | https://www.olombrada.es/urbanismo |
| Portal DipSegovia | https://www.dipsegovia.es/web/ayuntamiento-de-olombrada |
| Urbanismo DipSegovia | https://www.dipsegovia.es/web/ayuntamiento-de-olombrada/urbanismo |
| Sede electrónica (espublico) | https://olombrada.sedelectronica.es |
| Tablón / info pública | https://olombrada.sedelectronica.es/board , `/info` |
| Catálogo trámites | https://olombrada.sedelectronica.es/dossier |
| PLAI JCYL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=149 |
| PLAI JCYL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=149 |

## Proyectos / planeamiento

- **Web / DipSegovia:** tema Liferay compartido con otros ayuntamientos segovianos; sección urbanismo enlaza al archivo PLAI JCYL.
- **PLAI JCYL:** listado HTML paginado (`searchVPubDocMuniPlau` / `Plai`) con instrumentos aprobados y en información pública para `municipio=149`.
- **IDECyL WFS:** capas `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito` con `n_mun = 'Olombrada'`. Sectores vigentes con polígono (p. ej. **La Era U1**, otros sectores SU-NC).
- **Sede tablón:** documentos en `/preview-document/` (HTML tabla estándar espublico gestiona); mezcla de anuncios administrativos y urbanismo puntual.

## Licencias de obra

- No hay registro público estructurado de concesiones con coordenadas.
- Licencias y comunicaciones previas se tramitan vía sede; el tablón publica PDFs puntuales.
- **Estrategia adapter:** anuncios del tablón filtrados por patrón + páginas informativas del catálogo de trámites (`/dossier`) y semillas urbanismo.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `CQL_FILTER=n_mun = 'Olombrada'`, `srsName=EPSG:4326`, `outputFormat=application/json`
  - Campos: `n_sector`, `n_num_sect`, `c_id_sect` (p. ej. `40149U1 La Era`)
- **Estrategia:** descarga WFS por municipio; filas WFS como proyectos con `geom_geojson`; cruce por nombre de sector en títulos PLAI/tablón.
- **Limitaciones:** polígonos a nivel sector/planeamiento, no por expediente; sin visor ArcGIS municipal propio; licencias sin geometría enlazable.

## Limitaciones generales

- PLAI con volumen moderado según instrumentos publicados en JCYL.
- Tablón sede con pocos documentos urbanísticos explícitos.
- SSL sede: patrón espublico (`insecure_ssl: true` en manifest por compatibilidad con otros municipios CYL).
- Paginación PLAI estándar JCYL (15 filas/página).
