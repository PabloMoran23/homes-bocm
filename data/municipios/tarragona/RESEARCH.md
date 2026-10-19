# Tarragona — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Plone) | https://www.tarragona.cat |
| Sede electrónica STA | https://seu.tarragona.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME |
| Urbanisme (índice sede) | https://seu.tarragona.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_URBANISME |
| Tablón de anuncios (JSON embebido) | `PTS2_TABLON&KEY=all` |
| Planejament general vigent | `PTS2_PLA_GENERAL_VIGENT` |
| Planejament en tràmit | `PTS2_PLANEJAMENT_ATRAMIT` |
| Projectes d'urbanització | `PTS2_PROJECTES_URB` |
| Actualitat urbanisme (RSS RDF) | https://www.tarragona.cat/lajuntament/territori/actualitat-durbanisme/RSS |
| Catálogo trámites | `PAGE_CODE=CATALOGO` (dataset `CATSERV`) |
| Geoportal municipal | https://geoportal.tarragona.cat |

## Cómo se listan expedientes / proyectos

- **Sede STA (TAO):** cada subsección de planejament renderiza un `var dataset_<PAGE_CODE> = [...]` con filas tipo tablón (`descriptionProc`, `pubDateIni`, `externString`, `dboid`). El tablón general (`PTS2_TABLON&KEY=all`) expone ~414 anuncios en un único JSON (~400 KB; respuesta lenta, ~2 min).
- **Detalle:** enlace `DETALLE=<dboid>&PAGE_CODE=PTS2_TABLON`.
- **Noticias:** feed RDF 1.0 de actualitat d'urbanisme (títulos y fechas `dc:date`).

## Licencias

- No hay listado público de concesiones de licencia con dirección/coords.
- El tablón incluye pocas filas explícitas de llicències; el adapter filtra por palabras clave.
- **Trámites informativos** en catálogo STA (`CATSERV`): p. ej. comunicació prèvia d'obres, informe urbanístic.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Geoportal ArcGIS (`geoportal.tarragona.cat`): capas turísticas y `Terme_municpal_Tarragona` (límite municipal, layer id 6). No hay capas de expedientes/PAU enlazables por código.
  - No se encontró WFS/GeoJSON de instrumentos de planeamiento municipal enlazable a cada fila del tablón.
- **Estrategia:** el orquestador usará centroide municipal (`manifest.portal.config.centroid`) + jitter en `geocode`.
- **Limitaciones:** geometría de ámbito solo en PDFs/planos del planejament; visor sin query por expediente.

## Limitaciones generales

- Tablón STA: timeout elevado y payload grande.
- Muchas noticias RSS son obras municipales/licitaciones, no expedientes PGOU; se filtran con regex de planeamiento/urbanismo.
- `PTS2_PLANEJAMENT_DERIVAT` no expone dataset JSON en HTML (solo navegación); no incluido en scrape.
