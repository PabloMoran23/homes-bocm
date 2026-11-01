# Vic — investigación portal ayuntamiento

Municipio: **Vic** (`vic`) — Catalunya / provincia Barcelona (Osona)  
INE: **08298** — Sin boletín regional asociado en cola BOCM.

## Fuentes

| Recurso | URL | Tecnología | Contenido |
|---------|-----|------------|-----------|
| Web municipal | https://www.vic.cat | Plone | Urbanisme, planejament vigent/en tràmit |
| Planejament vigent (RSS) | https://www.vic.cat/serveis/territori/urbanisme/prova/planejament-i-gestio-urbanistica-vigent-1/planejament-i-gestio-urbanistica-vigent/rss.xml | Plone RSS + CDATA HTML | Tablas POUM, PAU, PMU, PE, reparcelaciones, expropiaciones (~60+ filas) |
| Planejament en tràmit | https://www.vic.cat/serveis/territori/urbanisme/prova/planejament-i-gestio-urbanistica-en-tramit | Plone HTML | Modificaciones POUM, PMU, PEU, PAU en tramitación |
| PIU | http://informaciourbanistica.vic.cat/vicgp/ | Visor propio | POUM consolidado (informativo) |
| Enmapa / guia | https://guia.vic.cat/enmapa/visor/web | Enmapa | Capas urbanísticas municipales (sin join expediente) |
| RPUC Generalitat | https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08298 | SPA | Registro planeamiento Catalunya |
| Sede electrónica | https://seuelectronica.vic.cat | espublico gestiona | Trámites y tablón |
| Tauler d'anuncis | https://seuelectronica.vic.cat/board | Wicket HTML | Anuncios públicos (paginado; pocas filas urbanismo en muestra) |
| Catàleg tràmits | https://seuelectronica.vic.cat/dossier.0 | Wicket (requiere cookies) | ~131 trámites; ~40 relacionados con urbanismo/obras |

## Proyectos / expedientes

1. **Tablas RSS vigent:** filas con año, título, fecha vigencia, código expediente (`AJT/…`, `GPPE …`) y enlace Plone cuando existe.
2. **Tablas en tràmit:** misma estructura + estado de tramitación (aprovació inicial/provisional).
3. **PDFs** de gestión urbanística enlazados desde tablas (expropiaciones, actas).

## Licencias

- **Catálogo dossier.0:** trámites como «Sol·licitud d'una llicència d'obres», comunicaciones previas, ocupación vía pública, certificados urbanísticos (filtrados por patrones de licencia).
- **Tablón /board:** anuncios de expedientes (mayoría padrón en página actual); el adapter filtra filas con keywords de obra/licencia.
- No hay listado público tabular de licencias concedidas con coordenadas (patrón sede informativa + tablón).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PIU `informaciourbanistica.vic.cat/vicgp/` — visor cartográfico del POUM (sin REST/WFS público identificado para query por expediente).
  - Enmapa `guia.vic.cat/enmapa/visor/web` — capas `T2127,T2129,…` en EPSG:25831; sin campo de enlace a código `AJT/…`.
  - AMB `Planejament/Expedients` (INE 08298): **0 features** (Vic no está en ámbito metropolitano AMB con geometría de expedientes).
  - RPUC: consulta web SPA, sin WFS municipal directo en el adapter.
- **Estrategia:** orquestador aplica `centroid` del manifest + jitter; documentado para revisión futura (PIU/Enmapa).
- **Limitaciones:** visores solo informativos; expedientes en tablas HTML sin polígono descargable; tablón sin georreferencia.

## Limitaciones

- `tauler-danuncis` en vic.cat devuelve cuerpo vacío (redirección/iframe no usable por scrape).
- `/dossier` sin cookie jar provoca bucle 302; el adapter usa `dossier.0` con `CookieJar`.
- PIU responde vacío a fetch simple (probable SPA/carga JS).
