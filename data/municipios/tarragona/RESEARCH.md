# Tarragona — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.tarragona.cat |
| Territori i urbanisme | https://www.tarragona.cat/lajuntament/territori/territori |
| POUM (web) | https://www.tarragona.cat/poum |
| Sede electrónica | https://seu.tarragona.cat |
| Planejament a tràmit | https://seu.tarragona.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_PLANEJAMENT_ATRAMIT&lang=ES |
| Tablón edictos (todos) | https://seu.tarragona.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all&lang=ES |
| Catálogo trámites | https://seu.tarragona.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO&lang=ES |
| Trámites obres (info) | https://seu.tarragona.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_SOL_OBRES&lang=ES |
| CIS procedimientos | https://cis.tarragona.cat/cataleg/procediments/planejament-urbanistic_71 |
| Geoportal | https://geoportal.tarragona.cat |

## Expedientes / planeamiento

- **Sede STA (T-Systems):** las páginas `PTS2_PLANEJAMENT_ATRAMIT` y `PTS2_TABLON&KEY=all` embeben un JSON JavaScript (`var dataset_PTS2_* = [...]`).
- **Planejament a tràmit:** ~8 expedientes activos (PEU, PMU, avance POUM, modificaciones) con `externString` (código), `descriptionProc` (HTML con enlaces BOPT) y `pubDateIni`.
- **Tablón:** ~413 edictos en `KEY=all`; filtro por remitente/descripción para urbanismo y licencias. La descarga completa tarda ~90–120 s en red del agente.
- **Detalle:** `doEvent?APP_CODE=STA&DETALLE={dboid}&PAGE_CODE=PTS2_TABLON` o `PTS2_PLANEJAMENT_ATRAMIT`.
- **Web Plone:** territorio/POUM son páginas informativas; pocos PDFs directos enlazados en HTML estático.

## Licencias de obra

- No hay listado público de concesiones de licencia con dirección/coordenadas.
- **PTS2_SOL_OBRES** y **CATSERV** documentan trámites (llicència d'obres, comunicació prèvia, declaració responsable, etc.) — páginas informativas, no resoluciones.
- Edictos del tablón pueden incluir anuncios de licencias; se filtran por palabras clave.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Geoportal ArcGIS REST: `https://geoportal.tarragona.cat/server/rest/services` — capas de turismo, hábitats, término municipal (`Terme_municpal_Tarragona`); **sin** capa de expedientes urbanísticos ni parcelas con código de expediente.
  - Hub / Experience Builder (`geoportal-ajuntament-de-tarragona`) — aplicación SPA sin API REST enlazable por código de expediente del tablón.
- **Estrategia:** el orquestador usará `centroid` del manifest + jitter para `lat`/`lon`.
- **Limitaciones:** planeamiento publicado como edictos HTML/PDF y enlaces BOPT; no hay WFS/ArcGIS query por expediente.

## Limitaciones generales

- Tablón `KEY=all` es pesado (~400 KB HTML, >90 s); el adapter usa `tablon_timeout_s: 180`.
- Contenido en catalán/castellano mezclado; fechas en objetos JSON `{year, month, day}`.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
