# Molins de Rei — investigación portal ayuntamiento

## Fuentes principales

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://molinsderei.cat | WordPress (tema ajmolins). Urbanisme, obres, projectes (p. ej. Llicorelles). |
| Seu electrònica STA | https://www.molinsderei.net/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME | T-Systems STA: tauler, catàleg tràmits, notificacions. |
| Tauler d'anuncis | `…/PAGE_CODE=PTS2_TABLON&KEY=all` | JSON embebido `dataset_PTS2_TABLON` (edictes/ordenances). |
| Catàleg tràmits | `…/PAGE_CODE=CATALOGO` | JSON `dataset_CATSERV` (família Urbanisme + EACAT llicències). |
| RPUC PGOU | https://ptop.gencat.cat/rpucportal/…&codintExp=277777 | Enllaç des de /urbanisme/ al document PGOU registrat. |
| RPUC cerca | https://dtes.gencat.cat/rpucportal/…&municipiSel=08130 | Metadades expedients planejament (SPA). |
| Visor MUC | https://ptop.gencat.cat/muc-visor/…&municipi=08130 | Mapa urbanístic estatal (consulta visual). |
| Geoportal AMB | https://geoportalplanejament.amb.cat/ | Planejament refós àrea metropolitana Barcelona. |
| Visor PEPHA | https://patrimoni.molinsderei.cat/ | Pla especial patrimoni (mapa interactiu municipal). |

**Nota:** No hi ha portal seu-e AOC (`seu-e.cat/ca/web/molins-de-rei` → 404).

## Listado de expedientes / proyectos

- **WordPress:** pàgines estàtiques i notícies amb metadades Yoast (`datePublished`, descripció). PDFs en `/wp-content/uploads/`.
- **STA tablón:** filas con `descriptionProc`, `externString`, fechas `pubDateIni`; detalle vía `DETALLE={dboid}&PAGE_CODE=PTS2_TABLON`.
- **RPUC/MUC:** consulta de instrumentos de planeamiento; no API REST simple enlazada al código de expediente municipal de obra.

## Licencias de obra

- **Catálogo STA:** trámites EACAT (`Llicència d'obra`, comunicaciones previas, certificados urbanísticos) y trámites STAWEB locales (guals, etc.) bajo keyword `URBANISME_ACTIVITATS_MEDI`.
- **No** hay dataset público de concesiones concedidas (solo fichas de trámite + tablón de anuncios esporádico).
- Página informativa: https://molinsderei.cat/quines-obres-requereixen-llicencia/

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - MUC visor (municipi INE **08130**) — clasificación y planeamiento aprobado, sin query por expediente de obra.
  - RPUC — documentos y metadatos, geometría no expuesta como GeoJSON en el adapter.
  - Geoportal AMB — capas de refós; requiere identificador de ámbito AMB, no código expediente ayuntamiento.
  - Visor PEPHA — delimitación patrimonio; no enlazado a expedientes genéricos del tablón.
- **Estrategia implementada:** ingestión de metadatos + referencias GIS; el orquestador aplica centroide municipal (`manifest.config.centroid`) + geocode. No se rellena `geom_geojson` de forma fiable por fila.
- **Limitaciones:** sin WFS municipal público tipo IDEM Madrid; MUC/RPUC son consulta humana o SPA Angular; tablón con pocos anuncios urbanísticos recientes.

## Limitaciones generales

- Tablón STA con volumen bajo (p. ej. ordenanzas de prueba); proyectos estables en web/RPUC.
- Trámites EACAT redirigen a canal externo; no scrape de instancias presentadas.
- SSL y cookies estándar; sede molinsderei.net accesible desde cloud agent.
