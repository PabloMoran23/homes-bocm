# Santa Úrsula — investigación portal ayuntamiento

Municipio: **Santa Úrsula** (`santa-ursula`)  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias  
BOC: `boc_canarias` (1 entrada en `projects.json`)

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web corporativa | https://www.santaursula.es/ | WordPress; área Obras y Servicios |
| Sede electrónica | https://sede.santaursula.es/ | Galileo GIYS (galileoiys.es) |
| Tablón edictos | https://sede.santaursula.es/publico/tablon | Listado ASP.NET, enlaces `/publico/edictos/{id}` |
| RSS edictos | https://sede.santaursula.es/publico/sindicacion/edictos/RSS | Sindicación XML (~12 ítems recientes visibles) |
| Procedimientos | https://sede.santaursula.es/publico/procedimientos | Categoría URBANISMO (2 trámites) |
| Informe urbanístico | https://sede.santaursula.es/publico/territorio/informeurbanistico | Visor mínimo + trámite |
| Localización expedientes | https://sede.santaursula.es/publico/territorio/cexp | Búsqueda por mapa (sin API pública) |
| Transparencia | https://transparencia.santaursula.es/ | Portal aparte |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-santa-ursula | CKAN, 38 recursos |
| IDE Canarias (ej.) | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/TF/SUrs/ | Documentación normativa por instrumento |
| GeoBDP municipio | https://geobdp.grafcan.es/core/municipios/38040/ | INE 38040; índice documentos + visor |

## Expedientes / proyectos

- **Tablón sede + RSS edictos:** anuncios de consulta pública, modificaciones del planeamiento, etc. (p. ej. consulta pública MSP del planeamiento, sep. 2026).
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-santa-ursula` con PGO, estudios de detalle, correcciones de errores; recursos enlazan IDE Canarias, FIP y GeoBDP (`/core/documentos/{id}.html`).
- **WordPress:** noticias sobre ordenanzas y movilidad urbana; sin sección dedicada de expedientes IP.

Formato: HTML tablón + CKAN JSON API + PDF/HTML en IDE Canarias.

## Licencias de obra

- **No hay listado público de licencias concedidas** con coordenadas.
- Trámites en sede (URBANISMO): licencias de obra, comunicaciones previas, informe urbanístico.
- Edictos RSS pueden publicar licencias puntuales (filtro regex en adapter).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GeoBDP GRAFCAN: `https://geobdp.grafcan.es/core/documentos/{doc_id}.html` — `App.Map.zoomToExtent({FeatureCollection})` en EPSG:32628 (UTM28N), reproyectado a WGS84 en el adapter.
  - Catálogo municipal: `https://geobdp.grafcan.es/core/municipios/38040/`
  - Sede: visor mínimo en informe urbanístico / callejero (parcelario, sin polígono por expediente del tablón).
  - IDECanarias WMS planeamiento: servicios GRAFCAN (sin enlace directo expediente ↔ polígono del tablón).
- **Estrategia:** emparejar título SITCAN ↔ doc_id GeoBDP (URL en recurso CKAN o índice municipal); extraer polígono del visor embebido. Edictos del tablón sin GIS enlazable.
- **Limitaciones:** geometría principalmente para instrumentos de planeamiento en SITCAN/GeoBDP (~11 enlaces GeoBDP); licencias y edictos sin delimitación; localización de expedientes en sede sin API JSON pública.

## Limitaciones generales

- Sede Galileo sin API JSON para tablón (scrape HTML + RSS).
- Datos abiertos municipales en sede casi vacíos (solo pirámide de edades).
- SSL estándar.
- Sin re-parse BOCM; 1 entrada en `boc_canarias` ya en `projects.json`.
