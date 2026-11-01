# San Sebastián — investigación portal ayuntamiento

Municipio en cola: **San Sebastián** (`san-sebastian`) — etiqueta BOC Canarias *San Sebastián/La Gomera*; municipio INE **San Sebastián de La Gomera** (38036).  
Provincia (claim): San Sebastián/La Gomera · CCAA: Canarias · BOletín: `boc_canarias` (1 entrada en cola).

Implementación compartida con slug canónico `san-sebastian-de-la-gomera` (adapter `san_sebastian_de_la_gomera.py`, merge PR #518).

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web corporativa | https://sansebastiangomera.org/ | WordPress (Kadence); área Obras y Servicios |
| Sede electrónica | https://eadmin.sansebastiangomera.org/ | Galileo GIYS |
| Tablón edictos | https://eadmin.sansebastiangomera.org/publico/tablon | Listado ASP.NET con enlaces `/publico/edictos/{id}` |
| RSS edictos | https://eadmin.sansebastiangomera.org/publico/sindicacion/edictos/RSS | Sindicación XML |
| Procedimientos | https://eadmin.sansebastiangomera.org/publico/procedimientos | Categoría URBANISMO |
| Info territorial | https://eadmin.sansebastiangomera.org/publico/territorio/informeurbanistico | Informe urbanístico (trámite) |
| Localización expedientes | https://eadmin.sansebastiangomera.org/publico/territorio/cexp | Búsqueda expedientes (login posible) |
| Transparencia | https://transparencia.sansebastiangomera.org/ | Portal aparte |
| SITCAN planeamiento | https://opendata.sitcan.es/dataset/planeamiento-urbanistico-de-san-sebastian-de-la-gomera | CKAN, 42 recursos / 15 instrumentos |
| IDE Canarias PGO | https://www.idecanarias.es/resources/PLA_ENP_URB/URB_PLA/LG/SSGo/PGO/indice.html | Documentación normativa PGO |
| GeoBDP municipio | https://geobdp.grafcan.es/core/municipios/38036/ | INE 38036; visor polígonos por documento |

## Expedientes / proyectos

- **Tablón sede:** edictos HTML con título, fecha y resumen (ordenanzas urbanísticas, aprobaciones). RSS ~50 ítems; filtro por palabras clave urbanísticas en el adapter.
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-san-sebastian-de-la-gomera` con PGO, modificaciones puntuales, estudios de detalle, plan parcial SAPU; recursos enlazan IDE Canarias y GeoBDP.
- **WordPress:** noticias esporádicas; sin sección fija de urbanismo en menú principal.

Formato: HTML tablón + CKAN JSON API + PDFs en IDE Canarias.

## Licencias de obra

- **No hay listado público de licencias concedidas** con coordenadas.
- Trámites informativos en sede (URBANISMO): licencias de obra, comunicaciones previas, informe urbanístico.
- Edictos RSS/tablón pueden publicar licencias puntuales (regex en adapter).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GeoBDP GRAFCAN: `https://geobdp.grafcan.es/core/documentos/{doc_id}.html` — `App.Map.zoomToExtent({FeatureCollection})` en UTM28N, reproyectado a WGS84 en adapter.
  - Catálogo municipal: `https://geobdp.grafcan.es/core/municipios/38036/`
  - IDECanarias WMS: `https://idecan2.grafcan.es/ServicioWMS/Planeamiento` (sin enlace directo a expediente del tablón)
- **Estrategia:** emparejar título SITCAN ↔ doc_id GeoBDP; extraer polígono del visor embebido. Tablón/edictos sin GIS enlazable.
- **Limitaciones:** geometría solo para instrumentos de planeamiento en SITCAN/GeoBDP; licencias y edictos del tablón sin delimitación.

## Limitaciones generales

- Sede Galileo sin API JSON para tablón (scrape HTML + RSS).
- Sin visor urbanístico municipal propio; polígonos vía GRAFCAN/SITCAN.
- SSL estándar en sede.
- Slug `san-sebastian` es alias del nombre abreviado en BOC; portal único con `san-sebastian-de-la-gomera`.
