# Amposta — investigación portal ayuntamiento

Municipio: **Amposta** (`amposta`), Tarragona, Catalunya. INE **43009**. Sin boletín BOCM asociado en cola.

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal | https://www.amposta.cat |
| POUM (4 pestañas) | `planejament_v1.asp?i=ca&nv1=1..4` |
| Sede STA | https://seu.amposta.cat/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=PTS2_HOME |
| Tablón edictos | `PAGE_CODE=PTS2_TABLON&KEY=all` |
| Catálogo trámites | `PAGE_CODE=CATALOGO` (dataset `CATSERV`) |
| Geoportal urbanístic | https://geoportal.amposta.cat/geoportal/ |
| MUC Generalitat | https://dtes.gencat.cat/muc-visor/AppJava/home.do?municipi=43009&set-locale=ca |
| RPUC Catalunya | http://ptop.gencat.cat/rpucportal/ |

## Expedientes / planeamiento

- **POUM web:** tablas HTML en `planejament_v1.asp` con título, estado y enlaces PDF/ZIP (PEU, PPU, PMU, BOPT). Parser determinista por filas `<tr><td>…</td>`.
- **Tablón STA:** JSON embebido `var dataset_PTS2_TABLON = […]` (~40 anuncios). Incluye reurbanización Av. Santa Bàrbara y avisos urbanísticos puntuales.
- **Expedientes en trámite (SIGMA):** la carpeta ciudadana de expedientes (`EXPEDIENTES_FULL`) exige **VÀLid** o certificado; no scrapeable sin auth.
- **Actes i acords:** tauler públic sin dataset JSON embebido en la portada; no usado como fuente principal.

## Licencias de obra

- No hay listado público de concesiones georreferenciadas.
- **Catálogo SEU:** trámites informativos (consultes urbanístiques, certificats, comunicacions prèvies) vía `CATSERV`.
- **Tablón:** ocasional anuncio de obra/licencia; filtro por regex `llicència|obra|comunicació`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geoportal **enMapa / Nexus Geographics** (`geoportal.amposta.cat`): capas de calificación, ámbitos de gestión/protección y “expedients urbanístics aprovats” por finca; solo UI Angular/Cesium (sin MapServer/WFS descubierto en `main.js`).
  - Dominio legacy `amposta.enmapa.com` responde 403 desde el agente.
  - **MUC** Generalitat: visor estatal de planeamiento por municipio (referencia, no enlaza expediente con polígono vía API simple).
- **Estrategia adapter:** metadatos de proyectos con `geoportal_url` / `muc_visor`; sin `geom_geojson` automático. El orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** geoportal orientado a consulta parcelaria interactiva; PDFs POUM sin georreferencia embebida; sede STA sin geometría.

## Limitaciones generales

- Captcha/bot protection en algunas rutas de `www.amposta.cat` (SG Captcha); las URLs de planejamiento y SEU responden bien con User-Agent identificable.
- HTML POUM mal cerrado (`<ul>` sin `</td>`); el parser tolera filas contiguas.
- Sync Supabase depende de `SUPABASE_DB_URL` en CI/agente.
