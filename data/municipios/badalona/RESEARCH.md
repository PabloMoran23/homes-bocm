# Badalona — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial (Plone) | https://www.badalona.cat | Planejament en tràmit, derivat, convenis, gestió urbanística |
| Sede electrónica STA (TAO) | https://seu.badalona.cat | Catálogo trámites `PTS_CATSERV`; tablón `PTS_TABLON` (vacío en HTML) |
| E-Tauler (tablón metropolitano) | https://tauler.seu.cat/inici.do?idens=801550006 | Edictos/anuncios oficiales (enlace desde sede) |
| Geoportal urbanístico | https://geoportal.badalona.cat/badalona42/visor/geoportal | Visor Nexus/OpenLayers (sin REST público directo en el adapter) |
| AMB Planejament GIS | https://geoportal.amb.cat/geoserveisapp/rest/services/Planejament | Expedientes y sectores PGM (Badalona INE 08015) |

## Proyectos / expedientes

- **Listado principal:** secciones Plone bajo `…/planejament/planejament-en-tramit` con tarjetas Bootstrap (`card-title` + `card-text`) que incluyen número de expediente, NPC/plànol de ciutat y enlaces a subpáginas/PDF.
- **Otras semillas:** `planejament-derivat`, `convenis-urbanistics`, `convenis-i-gestio-urbanistica`, `plans-urbanistics`.
- **Formato:** HTML Plone; PDFs en rutas `@@download/file`; RSS por sección (poco detalle).
- **Expedientes en trámite municipal** usan códigos tipo `8/D2-24`, `2024/36920M`, NPC `808`, etc.

## Licencias

- No hay listado público de concesiones en el tablón local de la sede (`dataset_PTS_TABLON` vacío).
- El **catálogo STA** publica trámites de licencias/obras (obras mayores, comunicaciones previas, enderrocs, etc.) — filas informativas, no concesiones fechadas.
- Anuncios de licencias pueden aparecer en **E-Tauler** (fuera del scrape determinista actual).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - `Planejament/Expedients/MapServer/3` (AMB): polígonos por expediente normativo (`NOMEXP`, `DGU`, `CODI_INE=08015`), `f=geojson`, `outSR=4326`.
  - `Planejament/Sectors/MapServer/0`: sectores PGM (polígonos por `SECTOR` / `NOM_SECT`).
  - Geoportal municipal (`geoportal.badalona.cat`): visor Angular/OpenLayers; no se expone un MapServer documentado en la investigación.
- **Estrategia:** cargar todos los expedientes AMB de Badalona con geometría; enriquecer filas del portal por coincidencia de título/expediente; filas GIS directas como proyectos `amb_expedients_gis`.
- **Limitaciones:** expedientes MPGM recientes del portal no siempre enlazan 1:1 con `NOMEXP` histórico del AMB; tablón sin coords; E-Tauler no integrado.

## Limitaciones generales

- CloudFront bloquea peticiones sin User-Agent identificable (`poc-bocm-badalona/1.0`).
- Consulta de expedientes en sede (`PTS_EXPEDIENTES`) requiere identificación.
- Catálogo STA ~360 trámites; solo subset de licencias/obras.
