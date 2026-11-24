# Sant Andreu de la Barca — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL |
|--------|-----|
| Web municipal | https://sabarca.cat |
| Planejament (web) | https://sabarca.cat/planejamentUrbanistic |
| Tema urbanisme | https://sabarca.cat/temes/territori-i-urbanisme |
| Catàleg tràmits web | https://sabarca.cat/tramits |
| Seu electrònica / transparència | https://seu-e.cat/ca/web/santandreudelabarca |
| Urbanisme (transparència) | https://seu-e.cat/ca/web/santandreudelabarca/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme |
| Planejament urbanístic (seu-e) | …/urbanisme/planejament-urbanistic |
| Catàleg tràmits urbanisme | …/tramits-i-gestions/-/tramits/classificacio/urbanisme |
| e-TAULER (edictes) | https://tauler.seu.cat/inici.do?idens=819600000 |
| RPUC (municipi 08196) | https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08196 |
| Visor MUC | https://dtes.gencat.cat/muc-visor/AppJava/home.do?municipi=08196&set-locale=ca |
| Geoportal AMB | https://geoportalplanejament.amb.cat/AppGeoportalPlanejament2/index.html |
| CIDO (DIBA) | https://cido.diba.cat/normativa_local/6584526/planejament-urbanistic-ajuntament-de-sant-andreu-de-la-barca |
| SITMUN idelocals | http://sitmun.diba.cat/idelocals/?mun_ine=08196 |

## Cómo se listan expedientes / planeamiento

- **seu-e (Liferay AOC transparència):** páginas estáticas con párrafos y enlaces a RPUC, MUC, CIDO y documentación del PGOU. Subsecciones descubiertas bajo `/urbanisme/` (planejament, normativa, info geogràfica, plans territorials, EIA).
- **sabarca.cat:** Laravel + Livewire; catálogo de trámites en `/tramits/{id}` con título en `<h3>`. Búsqueda interna enlaza trámites de obras/licencias. Noticias por tema vía Livewire (sin API JSON pública simple).
- **RPUC / MUC:** aplicaciones Angular GenCat; listado de expedientes solo vía UI (SPA), no API REST estable para scrape determinista por municipio.
- **e-TAULER:** SPA React (`tauler.seu.cat`); anuncios/edictes sin endpoint público documentado en esta run.

## Licencias de obra

- No hay tablón ni dataset de **licencias concedidas** con dirección/coords.
- Trámites informativos: catálogo sabarca (`/tramits/13`, `/44`, `/83`, `/149`, `/179`, …) y catálogo seu-e (p. ej. informe urbanístico actividades, id `12692185`).
- Ordenanza de licencias urbanísticas (BOP 2006) referenciada en trámites; tramitación vía instancia genérica seu-e con identificación digital.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Visor MUC GenCat (capas cartografía urbanística municipal INE 08196); geoportal planejament AMB; documentación gráfica en pruebas enlazada desde sabarca.cat/planejamentUrbanistic; SITMUN DIBA (identificación locales).
- **Estrategia:** El adapter registra referencias RPUC/MUC/AMB como proyectos (`referencia_portal`). No hay campo expediente→polígono enlazable en HTML municipal; MUC/RPUC requieren consulta manual en visor SPA.
- **Limitaciones:** Sin WFS/ArcGIS REST público por código de expediente municipal; e-TAULER y RPUC nuevos portales sin API scrapeable; geometría de ámbito de proyecto no automatizable sin login.

## Limitaciones generales

- Carpeta ciudadana y notificaciones requieren idCAT/Certificado/Cl@ve.
- `bocm_count: 0` en cola — sin cruce boletín regional en este municipio.
- Sync Supabase depende de `SUPABASE_DB_URL` en CI/agente.
