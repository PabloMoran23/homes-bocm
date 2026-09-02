# San Sebastián de La Gomera — investigación portal ayuntamiento

Municipio: **San Sebastián de La Gomera** (`san-sebastian-de-la-gomera`)  
Provincia: Santa Cruz de Tenerife · CCAA: Canarias  
BOCM/BOC: `boc_canarias` (2 entradas en `projects.json`)

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

- **Tablón sede:** edictos HTML con título, fecha, expediente y resumen (p. ej. ordenanzas urbanísticas, aprobaciones). RSS con ~50 ítems recientes; filtro por palabras clave urbanísticas.
- **SITCAN CKAN:** dataset `planeamiento-urbanistico-de-san-sebastian-de-la-gomera` con PGO, modificaciones puntuales, estudios de detalle, plan parcial SAPU; cada recurso enlaza IDE Canarias (HTML/PDF) y GeoBDP (`/core/documentos/{id}.html`).
- **WordPress:** noticias municipales esporádicas (obras, licitaciones); sin sección dedicada de urbanismo en el menú principal.

Formato: HTML tablón + CKAN JSON API + PDFs en IDE Canarias.

## Licencias de obra

- **No hay tablón público de licencias concedidas** con coordenadas ni listado descargable.
- Trámites informativos en sede (categoría URBANISMO): licencias de obra, comunicaciones previas, informe urbanístico.
- Edictos RSS/tablón pueden publicar licencias puntuales (filtro regex en adapter).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - GeoBDP GRAFCAN: `https://geobdp.grafcan.es/core/documentos/{doc_id}.html` — `App.Map.zoomToExtent({FeatureCollection})` en UTM28N, reproyectado a WGS84.
  - Catálogo municipal: `https://geobdp.grafcan.es/core/municipios/38036/`
  - IDECanarias WMS planeamiento: `https://idecan2.grafcan.es/ServicioWMS/Planeamiento` (sin enlace directo a expediente del tablón)
- **Estrategia:** emparejar título SITCAN ↔ doc_id GeoBDP; extraer polígono del visor embebido. Tablón/edictos sin GIS enlazable.
- **Limitaciones:** geometría solo para instrumentos de planeamiento en SITCAN/GeoBDP (~15 polígonos); licencias y edictos del tablón sin delimitación; expedientes individuales en sede no georreferenciados públicamente.

## Limitaciones generales

- Sede Galileo sin API JSON para tablón (scrape HTML + RSS).
- Sin visor urbanístico municipal propio; dependencia de GRAFCAN/SITCAN para polígonos.
- SSL estándar en sede (sin `insecure_ssl`).
- Sin re-parse BOCM; 2 entradas en `boc_canarias` ya en `projects.json`.
