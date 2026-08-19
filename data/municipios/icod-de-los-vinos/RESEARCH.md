# Icod de los Vinos — investigación portal ayuntamiento

Municipio: **Icod de los Vinos** (`icod-de-los-vinos`)  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias  
Código INE municipio (Grafcan): `38022`  
Boletín: `boc_canarias` (6 avisos BOCM)

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress + Divi) | https://icoddelosvinos.es/ | Trámites, noticias, planeamiento |
| Trámites urbanismo (WP) | https://icoddelosvinos.es/ayuntamiento/tramites/?tipo=urbanismo | 35+ procedimientos (licencias, cédulas, segregación…) |
| Planteamiento urbanístico | https://icoddelosvinos.es/planteamiento-urbanistico/ | Visor GRAFCAN embebido (PGOU vigente) |
| Sede electrónica (STA T-Systems) | https://sede.icoddelosvinos.es/sta/CarpetaPublic/?APP_CODE=STA&PAGE_CODE=PTS2_HOME | Catálogo, tablón, expedientes (login) |
| Tablón STA | https://sede.icoddelosvinos.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all | `var dataset_PTS2_TABLON = […]` (~302 filas) |
| Catálogo procedimientos sede | https://sede.icoddelosvinos.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO | Trámites electrónicos |
| SITCAN Open Data | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-icod-de-los-vinos | 58 recursos SIPU/PDF/HTML (planeamiento sistematizado) |
| GEOBDP Grafcan | https://geobdp.grafcan.es/core/municipios/38022/ | 15 documentos de planeamiento con visor y geometría |
| Visor GRAFCAN embed | https://visor.grafcan.es/embed/viewer?svc=svcPlaDef&lat=28.36687&lng=-16.71740 | Capas planeamiento vigente (WMS regional) |

## Cómo se listan expedientes / proyectos

- **WordPress REST API:** `https://icoddelosvinos.es/wp-json/wp/v2/tramite` — catálogo de trámites (73 ítems totales, ~35 urbanismo). Sin expedientes individuales en curso.
- **Tablón STA:** JSON embebido en HTML (`dataset_PTS2_TABLON`) con campos `descriptionProc`, `pubDateIni`, `dboid`. Incluye ordenanzas, anuncios tributarios y algunos actos de planeamiento (p. ej. PMUS, disolución OAL Urbanismo).
- **SITCAN CKAN API:** `package_show?id=planeamiento-urbanistico-de-icod-de-los-vinos` — instrumentos de planeamiento (PGO, normas subsidiarias, planes parciales, estudios de detalle) con enlaces PDF/SIPU.
- **GEOBDP:** listado HTML de 15 actuaciones definitivas con geometría en `App.Map.zoomToExtent(FeatureCollection EPSG:32628)`.
- **No hay** visor de expedientes urbanísticos individualizados ni API REST municipal de proyectos en curso (carpeta ciudadana requiere certificado/Cl@ve).

## Cómo se publican licencias

- **Sin dataset** público de licencias concedidas (decreto, coords, tablón filtrado).
- Trámites informativos en WordPress: licencia municipal de obras, comunicación previa, segregación-parcelación, prórroga, cédula urbanística, etc.
- Sede STA: registro electrónico de solicitudes (requiere identificación).
- El tablón puede publicar ordenanzas fiscales de tasas de licencia pero no concesiones nominativas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - **GEOBDP** (`geobdp.grafcan.es/core/documentos/{id}.html`): 15/15 documentos con `App.Map.zoomToExtent({FeatureCollection, crs: EPSG:32628})` — polígonos de ámbitos de planeamiento (PGO, PP, estudios de detalle, modificaciones puntuales).
  - **Visor GRAFCAN embed** en `planteamiento-urbanistico/`: WMS regional `svcPlaDef` (usos/calificación suelo), sin query por expediente.
  - **IDECanarias WMS:** `idecan2.grafcan.es/ServicioWMS/Planeamiento` — capas CCAA, sin WFS público por expediente.
- **Estrategia:** descargar geometría por `documento_id` GEOBDP, reproyectar UTM 28N → WGS84, enlazar por similitud de título con recursos SITCAN/tablón. No aplica a licencias ni expedientes de obra.
- **Limitaciones:** geometría solo para instrumentos de planeamiento aprobados (no licencias de obra); matching título→documento es heurístico; visor municipal no expone REST ArcGIS.

## Limitaciones generales

- Tablón STA mezcla urbanismo con tributos, empleo público y subvenciones — requiere filtrado por keywords.
- Gerencia de Urbanismo disuelta (anuncio tablón 2024); trámites siguen en sede pero sin visor propio de expedientes.
- SITCAN recursos mayoritariamente PDF/SIPU sin geometría embebida (la geometría está en GEOBDP).
- Sin re-parse BOCM; 6 entradas `boc_canarias` ya en `projects.json`.
