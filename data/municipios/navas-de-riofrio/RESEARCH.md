# Navas de Riofrío — investigación portal ayuntamiento

**Municipio:** Navas de Riofrío (Castilla y León, Segovia)  
**Slug:** `navas-de-riofrio`  
**Boletín:** BOCyL (`boletin_source_id: bocyl`)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal web (Liferay Segovia8 / DipSegovia) | https://www.navasderiofrio.es |
| Urbanismo | https://www.navasderiofrio.es/es/urbanismo |
| Sede electrónica (espublico gestiona) | https://navasderiofrio.sedelectronica.es |
| Tablón sede | https://navasderiofrio.sedelectronica.es/board |
| Información pública sede | https://navasderiofrio.sedelectronica.es/info |
| Catálogo trámites | https://navasderiofrio.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=146 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=146 |

## Expedientes / planeamiento

- **Web urbanismo:** galería Liferay con PDFs (anuncio NNSS, normas subsidiarias provinciales, documentación NUM). Enlaces `/documents/1576266/…`.
- **PLAI JCYL:** tabla HTML paginada; código municipio **146** (provincia 40). Incluye NUM y modificaciones (p. ej. sector 5 «El Barrero», cambios de alineaciones).
- **Tablón sede:** listado Wicket `preview-document/…` (puede estar vacío o con pocos anuncios).
- **Sin visor urbanístico municipal** ni API JSON de expedientes en curso.

## Licencias de obra

- Trámites en sede: «Solicitud de Licencia o Autorización Urbanística», «Declaración Responsable o Comunicación en Materia Urbanística» (`/dossier`, `/info.0`).
- No hay registro público descargable de licencias concedidas con coordenadas.
- Adapter: tablón sede cuando aplique + páginas informativas de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` con `n_mun = 'Navas de Riofrío'`:
  - `urbanismo:plau_cyl_instrumentos_ambito`: 1 feature (Normas Subsidiarias históricas, `MultiPolygon` ~14,8 km²)
  - `urbanismo:plau_cyl_sectores`: 0 features
  - `urbanismo:plau_cyl_planes_parciales`: sin geometría útil para este municipio
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia título/sector en filas PLAI y documentos urbanismo.
- **Limitaciones:** sin visor ArcGIS municipal; sectores NUM no publicados en WFS; licencias sin polígono; tablón mayormente informativo.

## Limitaciones generales

- Sede espublico puede ser lenta; `insecure_ssl: true` por certificados intermedios en algunos entornos.
- Scrape determinista HTML + PLAI + WFS (sin LLM).
