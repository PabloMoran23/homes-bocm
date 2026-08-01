# Segovia — investigación portal ayuntamiento

Municipio: **Segovia** (`segovia`) — Castilla y León / BOYL (`bocyl`)

## URLs base

| Recurso | URL |
|---------|-----|
| Web corporativa (Drupal) | https://www.segovia.es |
| Planeamiento urbanístico | https://www.segovia.es/ayuntamiento/planeamiento-urbanistico |
| PGOU | https://www.segovia.es/ayuntamiento/planeamiento-urbanistico/pgou |
| Modificaciones PGOU | https://www.segovia.es/ayuntamiento/planeamiento-urbanistico/modificaciones |
| PGOU consolidado (oct 2024) | https://www.segovia.es/area/urbanismo/pgou-consolidado |
| Noticias urbanismo | https://www.segovia.es/area/urbanismo |
| Sede electrónica (STA / T-Systems) | https://sede.segovia.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME |
| Tablón de anuncios | https://sede.segovia.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all |
| Catálogo de trámites | https://sede.segovia.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |
| Expedientes (privado) | https://sede.segovia.es/sta/CarpetaPrivate/Login?APP_CODE=STA&PAGE_CODE=EXPEDIENTES_FULL |

## Cómo se listan expedientes / proyectos

### Web Drupal (`segovia.es`)

- CMS **Drupal** con sección `/area/urbanismo/` de noticias por actuación (convenios, aprobaciones, correcciones PGOU, licencias, planes parciales).
- Páginas semilla de planeamiento con enlaces a PDFs del PGOU/PEAHIS y modificaciones.
- Ejemplo sector: `/area/urbanismo/plan-parcial-del-sector-uzd-r-16-h-prado-del-hoyo`.
- Listado en HTML estático; el adapter extrae rutas `/area/urbanismo/*` y PDFs PGOU de las semillas.

### Sede STA (`sede.segovia.es`)

- Plataforma **STA** (mismo patrón que Salamanca).
- **Tablón:** JSON embebido `var dataset_PTS2_TABLON = [...]` (~200 filas) con campos `dboid`, `descriptionProc`, `externString`, `pubDateIni`, `pubDateFin`.
- Detalle: `doEvent?APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`.
- **Catálogo:** `var dataset_CATSERV = [...]` (~130 trámites); ~29 relacionados con urbanismo/obras.
- Detalle trámite: `doEvent?APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=CATALOGO`.
- No hay dataset público de concesiones de licencia con dirección; el tablón actual tiene pocos anuncios de urbanismo (mayoría administrativos).

## Licencias de obra

- **No** hay listado público tabular de licencias concedidas (como Madrid Open Data).
- Trámites informativos en catálogo STA: «URBANISMO- Solicitud de licencia urbanística de obras», «Declaración responsable de actos de uso del suelo (incluye OBRA MENOR)», «licencia ambiental», etc.
- Alguna noticia en `/area/urbanismo/` menciona concesión de licencia (p. ej. «concesion-de-licencia-al-proyecto-basico…»).
- El adapter devuelve trámites del catálogo + anuncios del tablón filtrados por regex de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores`, `plau_cyl_planes_parciales`, `plau_cyl_instrumentos_ambito` (filtro `n_mun='Segovia'`, `srsName=EPSG:4326`)
  - Visor SiuCyL regional: https://www.jcyl.es/plau/
  - Gemelo Digital ArcGIS Hub municipal: https://gemelo-digital-aytosegovia.hub.arcgis.com/ (modelo 3D/catastro; sin enlace a expedientes STA)
- **Estrategia:** query WFS JCyL por municipio; polígonos en `geom_geojson` + centroide. Anuncios tablón/web sin match GIS → geocode con centroide + jitter.
- **Limitaciones:** El ayuntamiento no expone FeatureServer enlazado al tablón; geometría parcelaria de licencias no disponible. `opendata.segovia.es` no responde desde algunos entornos cloud.

## Limitaciones técnicas

- Dominios `segovia.es` y `sede.segovia.es` pueden bloquear conexiones desde algunos entornos cloud (connection reset). El adapter reintenta vía **Wayback Machine** (`web.archive.org/web/20250712100341/…`) cuando falla el acceso directo; en red local usa el portal en vivo.
- Expedientes de seguimiento requieren certificado / Cl@ve en sede privada.
- Tablón STA mezcla anuncios generales (pleno, tributos); filtro regex para urbanismo/licencias.
- SSL sede: `sede_insecure_ssl: true` por compatibilidad (patrón Salamanca).

## Referencia de implementación

- Adapter: `municipio/adapters/segovia.py` — patrón Salamanca (STA JSON embebido) + crawl Drupal `/area/urbanismo`.
