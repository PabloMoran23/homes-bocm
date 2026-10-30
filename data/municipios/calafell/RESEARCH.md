# Calafell — investigación portal ayuntamiento

Municipio: **Calafell** (`calafell`), provincia Tarragona, CCAA Catalunya. Código INE **43037**. Sin boletín BOCM asociado en cola.

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa | https://calafell.cat |
| Registre de gestió urbanística | https://calafell.cat/temes-i-serveis/planejament/registre-gestio |
| Planejament en tràmit | https://calafell.cat/temes-i-serveis/planejament/planejament-en-tramit |
| POUM (documentación) | https://calafell.cat/temes-i-serveis/planejament/poum |
| Tauler d'anuncis | https://calafell.cat/ajuntament/anuncis |
| Seu electrònica (seu-e) | https://seu-e.cat/es/web/calafell |
| Normativa urbanisme (transparència) | https://seu-e.cat/es/web/calafell/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme |
| Sede legacy (carpeta ciutadana) | https://seu.calafell.cat |
| RPUC (Generalitat) | https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=43037 |
| Visor MUC | https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=43037&set-locale=ca |

## Expedientes / proyectos

- **CMS:** Drupal custom (`calafell.cat`), bloques `expand-box expand-box--expandable`.
- **Listado:** cada expediente es un `<h2 class="expand-box__heading">` con fecha (`span.small` DD/MM/YYYY) y título en `<b>`, y enlaces a PDFs en `sites/default/files/YYYY-MM/*.pdf`.
- **Registre de gestió:** PMU, PAU, PEU, reparcelaciones (6 bloques visibles oct-2026).
- **En tràmit:** modificaciones POUM, suspensiones de licencias, etc. (misma estructura HTML).
- Algunos anexos apuntan a **SharePoint/OneDrive** del ayuntamiento (no scrapeables de forma estable); el adapter prioriza PDFs en `calafell.cat`.
- No hay API JSON pública ni código de expediente en el HTML del listado.

## Licencias de obra

- No hay tablón público de concesiones de licencias de obra (solo tauler d'anuncis genérico, sin dataset urbanístico estructurado).
- Trámites telemáticos en **seu-e.cat** (código entidad `4303790004`): comunicaciones previas, certificados, etc. — páginas informativas enlazadas en el adapter.
- Consulta de expedientes abiertos requiere **Carpeta Ciutadana** identificada (`seu.calafell.cat` / seu-e).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Mapa interactiu municipal (TecnoGeoWS): enlace en transparència → `citymap.tecnogeows.com/.../HnBDG6PffNgJTR7bo6JTKc` (visor genérico, sin campo expediente).
  - **MUC visor** Gencat `municipi=43037` — cartografía de planeamiento, no enlazada por código de expediente del registro Drupal.
  - **RPUC** — consulta de expedientes de planeamiento autonómicos, sin geometría GeoJSON directa en el adapter.
- **Estrategia:** metadatos + PDFs desde expand-box; geocodificación vía centroide municipal + jitter en pipeline. No hay query ArcGIS/WFS por expediente desde el listado público.
- **Limitaciones:** PDFs sin georreferencia embebida accesible; visor citymap sin API documentada; algunos planos solo en SharePoint.

## Limitaciones generales

- Sin listado machine-readable de licencias concedidas.
- Paginación no aplicable (listados cortos en una página).
- SSL válido en `calafell.cat` y `seu-e.cat`.
