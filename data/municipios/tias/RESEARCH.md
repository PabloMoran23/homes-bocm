# Tías — investigación portal ayuntamiento

Municipio: **Tías** (`tias`) — Canarias, provincia Las Palmas (este de Lanzarote, Puerto del Carmen). Boletín: sin entradas en cola (`bocm_count: 0`). INE: **35028**.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal WordPress (Avia) | https://www.ayuntamientodetias.es |
| Concejalía urbanismo | https://www.ayuntamientodetias.es/portfolio-item/concejalia-de-urbanismo-2/ |
| Visor PGO legacy | https://pgo.ayuntamientodetias.es/ |
| Sede electrónica (STA / T-Systems) | https://sede.ayuntamientodetias.es |
| Tablón anuncios | https://sede.ayuntamientodetias.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON |
| Catálogo trámites | https://sede.ayuntamientodetias.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO |
| Consulta expedientes (login) | https://sede.ayuntamientodetias.es/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS_EXPEDIENTES |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-tias |
| IDECanarias PGO | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LZ/Tias/744/indice.html |
| Transparencia | https://transparencia.ayuntamientodetias.es |

## Cómo se listan expedientes / planeamiento

- **CMS WordPress:** noticias y páginas institucionales; sitemap con entradas sobre licencias, convenios urbanísticos y planeamiento (sin listado estructurado de expedientes IP).
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-tias` con 2 instrumentos (adaptación PGO 698 / estudio detalle Los Lirios 1432) enlazados a GEOBDP, IDECanarias y ZIP SIPU.
- **GEOBDP Grafcan:** documentos `698` y `1432` con visor OpenLayers; geometría en `App.Map.zoomToExtent({...})` con CRS **EPSG:32628** (UTM 28N).
- **Visor PGO municipal:** sitio estático `pgo.ayuntamientodetias.es` (normativa, mapas PDF; sin API moderna).
- **Sede STA:** catálogo de trámites con dataset embebido `dataset_CATSERV` en página CATALOGO. **Tablón** `PTS2_TABLON` carga lista vía widget AJAX (`callWidgetEventExecuteOn`); no hay JSON estático en HTML inicial (a diferencia de otros STA).
- Consulta de expedientes: acceso restringido con identificación.

## Licencias de obra

- **Sin dataset** público de licencias concedidas con dirección/coordenadas.
- Catálogo STA incluye trámites: licencia de obra, comunicación previa, cambio de uso, parcelaciones, informe urbanístico, certificación urbanística, etc. (páginas de trámite, no histórico de concesiones).
- Noticias municipales mencionan concesiones puntuales (Lidl, modernización turística); no indexables de forma masiva.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GEOBDP `https://geobdp.grafcan.es/core/documentos/{698,1432}.html` — polígonos UTM28N en `zoomToExtent`
  - SITCAN enlaza cada instrumento a GEOBDP e IDECanarias
  - Visor PGO municipal sin geometría machine-readable
- **Estrategia:** indexar documentos GEOBDP desde recursos SITCAN; emparejar por título normalizado; reproyectar EPSG:32628 → WGS84 (`municipio/geometry.py` / helper UTM en adapter).
- **Limitaciones:** solo 2 instrumentos en GEOBDP; tablón STA sin scrape determinista; sin WFS municipal por expediente; licencias sin georreferencia pública.

## Limitaciones generales

- Tablón sede vía AJAX — no scrapeable sin emular widget STA.
- Sin listado abierto de licencias otorgadas.
- `insecure_ssl: true` para sede STA en CI si aplica.
- BOCM: 0 avisos asociados en cola (no cruza con `projects.json` regional).
