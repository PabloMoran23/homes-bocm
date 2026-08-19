# Los Realejos — investigación portal ayuntamiento

Municipio: **Los Realejos** (`los-realejos`)  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias  
Código INE municipio (Grafcan): `38031`

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress / LaStudio) | https://losrealejos.es/ | Área urbanismo, noticias PGO, transparencia |
| Urbanismo | https://losrealejos.es/urbanismo/ | Hub: PGO, gestión urbanística, licencias, trámites |
| Plan General (PGO 2025) | https://losrealejos.es/urbanismo/plan-general-de-ordenacion-2/ | PDFs BOC/BOP, diligencia, RAR PGO |
| IDE Canarias (enlace municipal) | https://losrealejos.es/urbanismo/plan-general-de-los-realejos-ide-canarias/ | Enlace al visor/documentación IDE |
| Gerencia Urbanismo (transparencia) | https://losrealejos.es/portal-de-transparencia/gerencia-de-urbanismo/ | Estadísticas, normativa GMU |
| Documentos gerencia | https://losrealejos.es/urbanismo/documentos-gerencia/ | WP File Download (categorías internas) |
| Trámites GMU | https://losrealejos.es/urbanismo/tramites-gerencia-urbanismo/ | Formularios, PDFs, enlace sede |
| Licencias actividades | https://losrealejos.es/urbanismo/licencias-de-actividades/ | Clasificadas / inocuas / minoristas |
| Sede electrónica (eMiServicio ABSIS) | https://sede.losrealejos.es/ | Trámites, carpeta ciudadano (certificado) |
| Portal urbanismo GMU (legacy) | https://urbanismolosrealejos.es/ | Timeout desde CI; sede alternativa en lr.toools.es histórico |
| SITCAN Open Data | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-los-realejos | 92 instrumentos de planeamiento (SIPU/PDF/HTML) |
| GEOBDP Grafcan | https://geobdp.grafcan.es/core/municipios/38031/ | Visor BDP con polígonos por instrumento |

## Cómo se listan expedientes / proyectos

- **SITCAN / IDE Canarias:** catálogo CKAN con ~92 recursos de planeamiento (PGO, SAPUR, estudios de detalle, modificaciones). Metadatos vía API `package_show`; enlaces HTML a `geobdp.grafcan.es` e `idecanarias.es`.
- **WordPress:** noticias y páginas de PGO (aprobación definitiva dic-2025), planes especiales conjuntos históricos, modificaciones parciales; PDFs en `/wp-content/uploads/` y `/descargar/`.
- **GEOBDP:** cada documento de planeamiento incluye capas «ámbito de ordenación» con GeoJSON embebido en `App.Map.zoomToExtent` (EPSG:32628).
- **No hay** visor de expedientes urbanísticos individuales en curso (tipo TAO/Drupal) ni API JSON del ayuntamiento.

## Cómo se publican licencias

- **No hay** listado público de licencias de obra concedidas (decretos, tablón con coords).
- Trámites documentados en **licencias de actividades** (clasificadas, inocuas, minoristas) y **trámites GMU** (alineaciones, rasantes).
- Sede eMiServicio: catálogo de trámites (`VisorITs`) — inicio telemático con certificado; sin tablón scrapeable de licencias.
- El adapter devuelve filas informativas de trámites; licencias reales publicadas = 0.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP: `https://geobdp.grafcan.es/core/documentos/<id>/` — GeoJSON MultiPolygon en JS (`EPSG:32628`)
  - IDE Canarias WMS planeamiento vigente: `https://idecan2.grafcan.es/ServicioWMS/Planeamiento`
  - Visor Grafcan: `https://visor.grafcan.es/visorweb/` (capas `svcPlaDef_*`)
- **Estrategia:** para recursos SITCAN con enlace GEOBDP, el adapter descarga la página del documento, extrae `App.Map.zoomToExtent`, reproyecta a WGS84 y rellena `geom_geojson`. ~10 documentos GEOBDP listados en el municipio; no todos los 92 recursos SITCAN tienen enlace GEOBDP.
- **Limitaciones:** sin WFS público consultable por código de expediente; geometría solo a nivel de instrumento de planeamiento (ámbito SAPUR/PGO), no licencias ni expedientes administrativos. `urbanismolosrealejos.es` inaccesible desde el entorno del agente.

## Limitaciones generales

- Sede ABSIS/eMiServicio: HTML legacy ISO-8859-1, sin RSS de edictos ni dataset JSON.
- WP File Download en documentos-gerencia: categorías cargadas por JS; no usado directamente (SITCAN más completo).
- Sin re-parse BOCM; 7 entradas en `boc_canarias` ya en `projects.json`.
