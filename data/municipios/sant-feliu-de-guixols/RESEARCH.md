# Sant Feliu de Guíxols — portal ayuntamiento

## Fuentes

| Recurso | URL | Formato |
|---------|-----|---------|
| Web municipal | https://www.guixols.cat | Joomla 4 + SP Page Builder |
| Seu electrònica (ciutadania) | https://ciutadania.guixols.cat | PHP custom + DataTables/AJAX |
| OAC / Carpeta ciutadana | https://ciutada.guixols.cat | JSP (PDF download UUID) |
| Expedients exposició pública | https://ciutadania.guixols.cat/expedients | JSON `POST …/agafar_expedients` (`pag_num`) |
| POUM | https://ciutadania.guixols.cat/poum , `/poum/vigent` | HTML + enlaces OAC |
| Catàleg tràmits | https://ciutadania.guixols.cat/tramits | HTML (256 URLs `/tramit/…_id`) |
| e-TAULER AOC | https://tauler.seu.cat/inici.do?idens=1716090004 | SPA React (iframe desde tauler-edictes) |
| Transparència (seu-e) | https://seu-e.cat/web/santfeliudeguixols | Liferay AOC |
| RPUC (Gencat) | https://dtes.gencat.cat/rpucportal/…&municipiSel=17160 | Angular SPA |
| Visor MUC | https://ptop.gencat.cat/muc-visor/…&municipi=17160 | Java visor estatal |

**Nota:** `www.santfeliu.cat` correspon a **Sant Feliu de Llobregat** (Barcelona), no a este municipio.

## Expedientes / planeamiento

- Listado público en `ciutadania.guixols.cat/expedients` cargado vía `POST /administrar/pagina/agafar_expedients` con `pag_num` (≈18 páginas, 9 ítems/página).
- Campos JSON: `ID`, `NOM`, `NUM_EXPEDIENT`, `DATA_INICIAL`, `DATA_FINAL`.
- Detalle: `https://ciutadania.guixols.cat/expedient/{ID}` con documentos en `ciutada.guixols.cat/OAC/download/{uuid}`.
- Noticias urbanísticas en Joomla (`/noticies/…`, p. ej. modificació POUM sector Huguet).

## Licencias

- No hay listado público de licencias concedidas (solo trámites informativos).
- Catàleg filtrable: trámites de l'Àrea **Urbanisme** (llicències d'obres, comunicacions prèvies, etc.) enlazados desde `/tramits`.
- e-TAULER publica edictos pero es SPA sin API JSON scrapeable en esta iteración.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** RPUC + visor MUC (Generalitat) para cartografía de planeamiento del término INE `17160`; POUM en PDF vía OAC; no hay visor municipal ArcGIS/WFS con enlace directo por código de expediente.
- **Estrategia:** metadatos desde API expedients + referencias RPUC/MUC; sin query automática por expediente en el adapter.
- **Limitaciones:** e-TAULER y RPUC son SPA; geometría por proyecto requeriría reverse-engineering o PDF georreferenciado. El orquestador aplicará centroide municipal + jitter.
