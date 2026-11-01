# Castelldefels — investigación portal ayuntamiento

## Fuentes

| Recurso | URL | Formato | Uso |
|---------|-----|---------|-----|
| Web urbanismo (Plone) | https://www.castelldefels.org/es/servicios/urbanismo | HTML / PDF | Planeamiento en trámite, planes aprobados, vigente |
| Sede electrónica STA | https://seu.castelldefels.org/sta/CarpetaPublic/?APP_CODE=STA&PAGE_CODE=PTS2_HOME | TAO STA | Catálogo trámites, tablón |
| Catálogo trámites | `PAGE_CODE=CATALOGO` | `var dataset_CATSERV` embebido | Licencias / trámites obra |
| Tablón edictos | `PAGE_CODE=PTS2_TABLON` | Widget AJAX (`submitAjax.aa`) | Sin dataset en HTML inicial |
| e-Tauler AOC | https://tauler.seu.cat/inici.do?idens=805690004 | SPA React | Tablón oficial (no API JSON pública simple) |
| Geoportal AMB | https://geoportalplanejament.amb.cat/AppGeoportalPlanejament2/index.html | ArcGIS | Visor planeamiento metropolitano |
| Transparencia GIS | https://seu-e.cat/es/web/castelldefels/.../informacio-geografica-d-urbanisme | Enlaces | Puntero al geoportal AMB |
| CIDO Diputación | http://cido.diba.cat/el-meu-municipi/8056/castelldefels | Portal | Documentación municipal (secundario) |

## Proyectos / expedientes

- **Plone:** secciones bajo `planeamiento-y-gestion-urbanistica` con PDFs (p. ej. modificaciones NNUU/OME PGM) y páginas hijas enlazadas.
- **AMB Expedients (ArcGIS):** capa REST `Planejament/Expedients/MapServer/3` filtrada por `CODI_INE='08056'` (~125 expedientes con polígono y metadatos `NOMEXP`, `DGU`, `URL`, `DAPRDEF`).
- No hay listado público de expedientes IP en Drupal como Pozuelo; el registro principal de planeamiento derivado está en el geoportal AMB + documentación Plone.

## Licencias

- No hay dataset público de licencias concedidas (solo trámites informativos en catálogo STA).
- Trámites relevantes: Licencia de obra mayor/menor, comunicaciones previas (CP01.x), certificados urbanísticos.
- Tablón PTS2_TABLON requiere POST AJAX; e-Tauler es SPA sin endpoint JSON documentado en esta run.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:** ArcGIS MapServer `https://geoportal.amb.cat/geoserveisapp/rest/services/Planejament/Expedients/MapServer/3` — campo expediente `DGU`, nombre `NOMEXP`, enlace `URL` (a menudo RPUC o fitxa municipal).
- **Estrategia:** query GeoJSON `where=CODI_INE='08056'`, `returnGeometry=true`, `outSR=4326`; enriquecer filas Plone por coincidencia de título con `NOMEXP`.
- **Limitaciones:** licencias de obra no georreferenciadas en portal; tablón sin scrape determinista en v1; visor AMB es metropolitano (no parcela de licencia individual).

## Limitaciones técnicas

- `www.castelldefels.org` bloquea algunos User-Agent mínimos (CloudFront 403); el adapter envía UA de navegador en peticiones web.
- Sync Supabase depende de `SUPABASE_DB_URL` en el entorno del agente.
