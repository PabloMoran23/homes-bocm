# Castellar del Vallès — investigación portal ayuntamiento

**Municipio:** Castellar del Vallès (Barcelona, Catalunya)  
**Slug:** `castellar-del-valles`  
**INE:** 08047  

## Fuentes

| Recurso | URL | Notas |
|---------|-----|--------|
| Web corporativa | https://www.castellarvalles.cat | CMS propio (rutas `/NNNNN/tipo/`) |
| Seu electrònica | https://seu.castellarvalles.cat | Mismo CMS; e-TRAM tràmits |
| Urbanisme | https://www.castellarvalles.cat/19891/ambit/ | Ámbito + enlaces planeamiento |
| Expedients en tramitació | https://www.castellarvalles.cat/55033/descriptiu/ | Listado HTML + fichas `/descriptiu/{id}` |
| Expedients aprovats | https://www.castellarvalles.cat/55055/descriptiu/ | Histórico aprobado |
| POUM | https://www.castellarvalles.cat/31824/plaEstrategic/ | PDFs administrativos + enlace geoportal |
| Normativa en tràmit | https://www.castellarvalles.cat/43956/descriptiu/ | Mayormente ordenanzas (no urbanismo puro) |
| e-TAULER | https://tauler.seu.cat/inici.do?idens=805170005 | SPA React; edictos/licencias vía exposición pública |
| Tràmits urbanisme | https://seu.castellarvalles.cat/33033/tramits/?fil=eyJpZHNBbWJpdCI6IjE0LDMyLDMzIn0= | Catálogo 1-LU.* / CP.* |
| Geoportal planejament | http://geoportal.castellarvalles.cat/urbanisme/ | iframe TecnoGeoWS CityMap |
| RPUC POUM | https://planejamenturbanisme.territori.gencat.cat/rpucportal/#/consulta/detallExpedient/263133 | Expediente 263133 |
| MUC visor Gencat | https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08047&set-locale=ca | Capas normativas municipales |

## Listado de expedientes / proyectos

- **En trámite / IP:** páginas índice `55033/descriptiu/` con enlaces `55033/descriptiu/{id}`; título en atributo `title` o `<h3 class="sense">` en detalle.
- **Documentos:** PDFs en `/arxius/document/{id}/arxiu/*.pdf` (fechas en texto del enlace, p. ej. `03-11-2026`).
- **Aprobados:** mismo patrón en `55055/descriptiu/`.
- **Planes especiales:** páginas estáticas (`46242`, `55066`, `55077`).

## Licencias

- No hay listado histórico público de concesiones (solo trámites e-TRAM y edictos e-TAULER).
- Adapter: catálogo e-TRAM filtrado urbanisme + páginas informativas (e-TAULER, ORPIME).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Geoportal municipal (TecnoGeoWS `citymap.tecnogeows.com`, iframe sin API REST documentada para expedientes); visor MUC/RPUC Generalitat (capas de planeamiento, no enlace 1:1 con fichas `55033`).
- **Estrategia:** ingestar metadatos HTML/PDF; geometría de ámbito no automatizable sin API del visor; orquestador usará centroide municipal + jitter.
- **Limitaciones:** e-TAULER es SPA sin feed RSS scrapeable en esta run; geoportal sin WFS público enlazado al código de expediente municipal.

## Adapter

- `municipio.adapters.castellar_del_valles:CastellarDelVallesAyuntamientoAdapter`
- IDs: `castellar-del-valles-lic-*` / `castellar-del-valles-proy-*`
