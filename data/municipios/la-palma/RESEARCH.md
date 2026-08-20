# La Palma — investigación portal (Cabildo Insular)

Municipio en cola: **La Palma** (`la-palma`) — Canarias, provincia Santa Cruz de Tenerife (isla de La Palma). Boletín: `boc_canarias` (3 avisos). **Nota:** no existe un ayuntamiento llamado "La Palma"; la entrada de cola corresponde al **Cabildo Insular de La Palma** (gobierno insular), cuyos avisos de planeamiento aparecen en BOC Canarias con municipio "La Palma".

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal Cabildo | https://www.cabildodelapalma.es |
| Planeamiento Insular (PIOLP) | https://www.piolp.es |
| Plan Insular de Ordenación | https://www.piolp.es/index.php/plan-insular-de-ordenacion/ |
| Planes territoriales especiales | https://www.piolp.es/index.php/planes-territoriales-especiales/ |
| Planes territoriales parciales | https://www.piolp.es/index.php/planes-territoriales-parciales/ |
| Ordenanzas / otros instrumentos | https://www.piolp.es/index.php/ordenanzas/ , `/otros/` |
| Portal Transparencia — planeamiento | https://transparencia.cabildodelapalma.es/ordenacion-del-territorio/plan-de-ordenacion/ |
| Sede electrónica | https://sedeelectronica.cabildodelapalma.es |
| Tablón de anuncios (STA) | `.../doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON` |
| Gobierno abierto | https://lapalmasmart-open.lapalma.es |
| Archivo planeamiento Canarias | https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/ |

## Cómo se listan expedientes / planeamiento

- **PIOLP (WordPress):** ~112 PDFs en secciones PIO, PTE, PTP, ZEC, ordenanzas y otros; actas de pleno, consultas previas, anuncios IAE (información pública ambiental).
- **Transparencia (Django):** 56+ documentos en `/media/r/ordenacion-del-territorio/plan-de-ordenacion/` (certificados, memorias, proyectos por año).
- **Sede STA (T-Systems):** tablón público con `var dataset_PTS2_TABLON = [...]` embebido (~286 anuncios); 55+ relacionados con evaluación ambiental / planeamiento; 6 con línea `Plan: "..."` explícita (modificaciones PIO, PTE El Remo, PGOU El Paso, etc.).
- **Consulta expedientes:** requiere identificación Cl@ve/certificado (`PAGE_CODE=EXPEDIENTES_FULL`).
- **Archivo Canarias:** formulario JSP por isla/municipio; sin API REST.

## Licencias de obra

- **Sin dataset** de licencias concedidas publicado por el Cabildo.
- **Trámites informativos** en catálogo sede (`PAGE_CODE=CATALOGO`): licencias de obra, actividad clasificada (competencia insular en vías y equipamientos).
- El tablón no publica licencias municipales (competencia de los 14 ayuntamientos de la isla).
- El adapter devuelve páginas informativas de trámites + cualquier anuncio del tablón que mencione licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **PIOLP ArcGIS Styler:** `lapalma.maps.arcgis.com/apps/Styler/...` — visor interactivo de alternativas EAE; sin API queryable por expediente/código.
  - **GEOBDP Grafcan:** datos por municipio (38014–38027), no capa insular PIO consultable por título de expediente Cabildo.
  - **PDFs planeamiento:** planos rasterizados, sin GeoJSON embebido.
  - **SITCAN CKAN:** sin paquete específico del Cabildo insular en opendata.sitcan.es.
- **Estrategia:** sin fuente GIS pública enlazable por expediente insular; el orquestador aplicará centroide isla `[28.66, -17.86]` + jitter.
- **Limitaciones:** planeamiento insular solo en PDF; visor ArcGIS es presentación EAE, no descarga WFS; expedientes sede requieren login.

## Limitaciones generales

- "La Palma" en BOC Canarias = avisos del Cabildo Insular, no de un municipio concreto.
- Los 14 municipios de la isla tienen adapters propios (`el-paso`, `santa-cruz-de-la-palma`, etc.).
- Tablón STA tarda ~40s en responder; dataset JSON embebido en HTML.
- Sin licencias concedidas en listado abierto a nivel insular.
