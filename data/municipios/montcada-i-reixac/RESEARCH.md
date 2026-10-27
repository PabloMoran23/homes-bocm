# Montcada i Reixac — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.montcada.cat |
| Planejament urbanístic | https://www.montcada.cat/ajuntament/planejament |
| Gestió urbanística | https://www.montcada.cat/ajuntament/gestio-urbanistica |
| Urbanisme i llicències | https://www.montcada.cat/temes/urbanisme |
| Anuncis / edictes (exposició pública) | https://www.montcada.cat/ajuntament/anuncis-edictes |
| Normativa urbanística | https://www.montcada.cat/ajuntament/normativa/normativa-urbanistica |
| Seu electrònica (AOC) | https://www.seu-e.cat/ca/web/montcadaireixac |
| e-TAULER (edictes) | https://tauler.seu.cat/inici.do?idens=812520002 |
| Tràmits obres / expedients | https://www.montcada.cat/serveis-i-tramits/tramits-i-gestions/ |

## Cómo se listan expedientes / planeamiento

- **CMS propio** (PHP, Bootstrap): páginas `.html` bajo `/ajuntament/planejament/` y `/ajuntament/gestio-urbanistica/` con título H1, bloque «Documents» y PDFs en `/media/repository/publicacions/…` y `/media/repository/anuncis_i_edictes/…`.
- **Índices**: las secciones planejament/gestió y urbanisme enlazan fichas de proyecto (p. ej. `…/projecte-de-reparcellacio-del-pau-santa-feexp-32024pu.html`) con código expediente en el título (`Exp. 3/2024/PU`).
- **Sitemap**: `https://www.montcada.cat/sitemap.xml` → `media/sitemap/contents_*.xml` (URLs de contenido).
- **e-TAULER**: enlace desde anuncis-edictes (`idens=812520002`); SPA React sin feed RSS/API pública scrapeable de forma determinista.
- **`/pdflist/`**: genera un PDF combinado (dompdf), no un listado HTML útil para scraping fila a fila.

## Licencias de obra

- No hay tablón público de licencias concedidas con dirección/coordenadas.
- Trámites informativos en `/temes/urbanisme` y `/serveis-i-tramits/tramits-i-gestions/` (placa d'obra, consulta expedients àrea territorial, instància genèrica).
- Publicación de edictos vía **e-TAULER** (mismo patrón que L'Hospitalet, Badalona, Sant Boi).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - MUC Generalitat: http://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08124 — cartografía de planeamiento, sin enlace estable expediente→polígono para el adapter.
  - RPUC: https://dtes.gencat.cat/rpucportal/ (municipiSel=08124) — consulta interactiva, sin API batch.
  - Geoportal AMB Planejament/Expedients MapServer/3 — consulta `CODI_INE='08124'` devuelve 0 features en esta investigación.
  - Geoportal planejament AMB (enlace desde web): https://geoportalplanejament.amb.cat/ — visor regional, no join por expediente municipal.
  - `/el-municipi/planol` — mapa callejero Leaflet/OSM, sin capas de expedientes.
- **Estrategia:** ingestar metadatos HTML/PDF del CMS; el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** sin WFS/ArcGIS municipal enlazado al código de expediente; e-TAULER y sede no exponen geometría en listados scrapeables.

## Limitaciones generales

- e-TAULER requiere navegación SPA (no implementado).
- Muchos PDFs bajo `/media/repository/` con nombres técnicos; fechas inferidas de expediente o año en URL.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
