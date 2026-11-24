# El Masnou — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.elmasnou.cat |
| Informació urbanística | https://www.elmasnou.cat/informacio-oficial/informacio-urbanistica |
| Documents en exposició pública | https://www.elmasnou.cat/informacio-oficial/informacio-urbanistica/documents-en-exposicio-publica |
| Planejament urbanístic | https://www.elmasnou.cat/temes/urbanisme/planejament-general |
| Planejament derivat / vigent | https://www.elmasnou.cat/temes/urbanisme/planejament-derivat |
| Anuncis / edictes | https://www.elmasnou.cat/informacio-oficial/anuncis-edictes |
| Seu electrònica (AOC) | https://seu-e.cat/ca/web/elmasnou |
| Catàleg tràmits (legacy) | https://cataleg.elmasnou.cat/ |
| e-TAULER | https://tauler.seu.cat/inici.do?idens=811890004 |
| Repositori media (DIBA) | https://elmasnou.webmunicipal.diba.cat/media/repository/urbanisme/ |
| Geoportal municipal | https://www.elmasnou.cat/guia-del-municipi/geoportal |

## Cómo se listan expedientes / planeamiento

- **CMS webmunicipal (Diputació de Barcelona)**: páginas PHP con menú `/informacio-oficial/` y `/temes/urbanisme/`; documentación en **PDF** bajo `/media/repository/urbanisme/` (exposición pública, MPPGO, edictes BOPB, certificats d'alcaldia, projectes anonimitzats).
- **Exposición pública**: listado plano de enlaces PDF agrupados por carpetas (`expo_publica_*`, `Casinet`, etc.) con códigos tipo `X2026019177` en el nombre del fichero.
- **Planejament general**: PDFs normativos (`normativa_urbana_sitca`, MPPGO1–5, plans d'ordenació).
- **e-TAULER**: enlaces desde la portada (`pagDetall.do?idEdicte=…&idens=811890004`); aplicación React SPA sin API RSS pública scrapeable de forma determinista (solo enlaces embebidos en HTML del ayuntamiento).
- **Seu-e**: trámites Liferay (`/-/tramits/tramit/…`); no listado público de expedientes urbanísticos con metadatos tabulares.

## Licencias de obra

- No hay tablón público de licencias concedidas con dirección o coordenadas.
- Tramitación vía **seu-e** (instància genèrica, catàleg) y app **Tràmit**; carta de serveis URB/2024.01 describe tipos de llicències però sin publicación de resoluciones en listado scrapeable.
- Edictos de suspensión u otros anuncios pueden aparecer en **e-TAULER** (mismo patrón que municipios AOC vecinos).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - MUC Generalitat: https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08125 — cartografía de planeamiento (capas normativas), sin enlace estable expediente→polígono.
  - RPUC: https://dtes.gencat.cat/rpucportal/ (`municipiSel=08125`) — consulta interactiva, sin API batch para el adapter.
  - Geoportal municipal enlaza al estándar MUC / descarga municipal Gencat; no visor ArcGIS propio con query por código de expediente.
- **Estrategia:** ingestar metadatos PDF + enlaces e-TAULER; geocode con centroide municipal (`manifest.config.centroid`).
- **Limitaciones:** PDFs sin georreferencia; e-TAULER SPA; sin WFS municipal enlazado al código X20… del expediente.

## Limitaciones generales

- Muchos PDFs (>100) en exposición pública; fechas inferidas de código expediente o año en ruta.
- Sin boletín regional asociado en cola (`bocm_count: 0`).
- `bustiaetica.seu-e.cat` es GlobaLeaks (bústia ètica), no sede administrativa.
