# Blanes — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `blanes` |
| INE | 17023 |
| Web | https://www.blanes.cat |
| Sede | https://seu.blanes.cat |
| CMS | Lotus Domino / Notes (`oiapdocs.nsf`, rutas `/docweb/…`) |
| Edictes | e-Tauler (https://www.blanes.cat/edictes → SPA Consorci AOC) |

## URLs base y semillas

- Urbanisme: https://www.blanes.cat/urbanisme
- Planejament (índice): https://www.blanes.cat/docweb/urbanisme.planejament
- Projectes aprovats: https://www.blanes.cat/docweb/urbanisme.projectes.aprovats
- PGOU / planejament vigent: https://www.blanes.cat/docweb/urbanisme.novigent
- Llicències (AMIC): https://www.blanes.cat/docweb/amic_urbanisme
- Sede — consulta expedientes: `PAGE_CODE=PTS_EXPEDIENTES`
- Sede — catálogo trámites: `PAGE_CODE=CATALOGO` (dataset `CATSERV`, familia URBANISME)
- RPUC Blanes: https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=17023

## Proyectos / expedientes

- **Listado principal:** página *Projectes Aprovats* con bloques `<h2>` (título + fecha aprobación en catalán) y enlace PDF en Domino (`/oiapdocs.nsf/.../$FILE/*.pdf`). ~29 proyectos scrapeables.
- **Planejament en tràmit:** subpáginas `docweb/urbanisme.*` enlazadas desde el índice (PMU, delimitaciones, planes parciales, etc.) con PDFs embebidos.
- **Sede STA:** `PTS_EXPEDIENTES` es consulta por código de expediente (no listado público masivo). No hay `dataset_PTS2_TABLON` como en otros ayuntamientos.
- **Edictes:** redirección a e-Tauler; sin API JSON descubierta en el entorno del agente.

## Licencias

- No hay dataset público de concesiones de obra en tablón.
- Catálogo STA filtra trámites con keyword `URBANISME` (obras, licencias, habitatge turístic, etc.) — fichas informativas.
- AMIC urbanisme describe procedimiento de licencias sin listado histórico.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - `https://ruyra.blanes.cat/` — dominio sin contenido (Plesk default).
  - RPUC / MUC visor Generalitat (`ptop.gencat.cat`) — SPA; `muc-visor` no accesible por TLS desde el entorno cloud.
  - AMB ArcGIS — Blanes (17023) fuera del ámbito metropolitano de Barcelona.
- **Estrategia:** el adapter no enlaza expediente web → polígono; el orquestador usará `centroid` del manifest + jitter.
- **Limitaciones:** solo PDFs y texto en Domino; sin WFS/ArcGIS municipal público.

## Limitaciones generales

- Codificación histórica `latin-1` en parte del HTML Domino.
- Cookiebot en portada (no bloquea rutas docweb).
- Tiempos de respuesta altos (~15–35 s) en algunas páginas; `request_delay_s` 0.35 y timeout 90 s.
