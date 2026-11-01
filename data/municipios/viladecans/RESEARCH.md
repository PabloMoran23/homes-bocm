# Viladecans — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web oficial (Drupal) | https://www.viladecans.cat | Planejament en tramitació, tràmits en línia, mapa usos del sòl |
| Seu electrònica STA | https://seuelectronica.viladecans.cat | Catálogo `CATALOGO` / `CATSERV`, tablón `PTS2_TABLON`, normativa |
| Transparència (seu-e) | https://www.seu-e.cat/ca/web/viladecans | Govern obert, enllaços RPUC / normativa urbanística |
| Guia tràmits obres | https://guiat.viladecans.cat/player/ | Assistent permisos d'obres (SPA, sense llistat d'expedients) |
| Plànol municipal | https://viladecans.maps.arcgis.com/apps/webappviewer/index.html?id=d81f969a76b7483586906104b710d5fe | Adreces, equipaments, empreses (FeatureServer ZP1Iw2MU5AMTAddh) |
| AMB Planejament GIS | https://geoportal.amb.cat/geoserveisapp/rest/services/Planejament | Expedients urbanístics metropolitans (INE **08301**) |

## Proyectos / expedientes

- **Listado principal:** `https://www.viladecans.cat/ca/planejament-en-tramitacio` — secciones `<h2>` por PEUP/PMU/modificaciones con PDFs en `/sites/default/files/` y dates d'informació pública al cos del texte.
- **Otras semillas:** `planejament-vigent`, `planejament-supramunicipal-en-tramitacio`, `mapa-dusos-del-sol`.
- **Tablón STA:** `PTS2_TABLON` (dataset JS embebido, si la sede responde).
- **Histórico normativo:** capa AMB **Expedients** (~165 polígonos vigents/històrics amb `NOMEXP`, `DGU`, `URL`).

## Licencias

- No hay listado público masivo de concesiones con coordenadas en el portal.
- **Tràmits en línia** (`/ca/tramits-4`): comunicació d'obres exemptes, llicències d'obra menor (enderrocs, accessibilitat, rehabilitació, etc.) — filas informativas.
- **Catálogo STA** (`PAGE_CODE=CATALOGO`, dataset `CATSERV`): trámites de urbanismo/obras (si accesible).
- Concesiones puntuales pueden publicarse en el **tauler d'edictes** STA.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - `Planejament/Expedients/MapServer/3` (AMB): polígonos por expediente (`CODI_INE=08301`, `NOMEXP`, `DGU`), query `f=geojson`, `outSR=4326`, `returnGeometry=true`.
  - Plànol Viladecans (ArcGIS Online): capas de direcciones/POI — **no** enlazan código de expediente urbanístico.
  - Visor PEPCV (enlace informativo en web de patrimonio) — consulta no normativa.
- **Estrategia:** ingestar todos los expedientes AMB del municipio con geometría; enriquecer filas Drupal/tablon por similitud de título; filas GIS directas como `amb_expedients_gis`.
- **Limitaciones:** Cloudflare en `www.viladecans.cat` bloquea algunos datacenters (403); sede STA puede hacer timeout SSL desde redes externas; PEUP recientes del Drupal no siempre coinciden 1:1 con `NOMEXP` del AMB.

## Limitaciones generales

- Sin boletín regional asociado en cola (`bocm_count: 0`).
- Drupal detrás de Cloudflare — User-Agent de navegador recomendado en CI.
- Sede `seuelectronica.viladecans.cat`: handshake SSL lento o bloqueado fuera de Cataluña en algunos entornos.
- Sync Supabase requiere `SUPABASE_DB_URL` en el entorno de ejecución.
