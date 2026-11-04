# Olesa de Montserrat — portal ayuntamiento

Municipio: **Olesa de Montserrat** (`olesa-de-montserrat`)  
Provincia: Barcelona · CCAA: Catalunya · INE: **08154**

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Drupal 10) | https://www.olesademontserrat.cat |
| Urbanisme | https://www.olesademontserrat.cat/urbanisme |
| POUM (PDFs) | https://www.olesademontserrat.cat/urbanisme/pla-dordenacio-urbanistica-municipal |
| Pla especial catàleg patrimoni | https://www.olesademontserrat.cat/urbanisme/cataleg-i-pla-especial-urbanistic-de-proteccio-de-patrimoni-historic-arquitectonic-i |
| Projectes (índex) | https://www.olesademontserrat.cat/urbanisme/projectes |
| Seu-e (Liferay) | https://seu-e.cat/ca/web/olesademontserrat |
| Tauler d'edictes | https://seu-e.cat/ca/web/olesademontserrat/govern-obert-i-transparencia/accio-de-govern-i-normativa/accio-de-govern-i-grups-politics/tauler-d-edictes-i-anuncis |
| Normativa urbanística (transparència) | https://seu-e.cat/ca/web/olesademontserrat/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/normativa-d-urbanisme |
| Tràmits | https://seu-e.cat/ca/web/olesademontserrat/tramits-i-gestions |
| Geoportal / assistent tràmits | https://geoportal.olesademontserrat.cat/info-urbanistica/inici |
| RPUC (08154) | https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08154 |

## Cómo se listan expedientes / planeamiento

- **POUM y PE:** decenas de PDFs estáticos en `/sites/default/files/` enlazados desde páginas Drupal de urbanismo (memorias, planols, índices).
- **Projectes:** página índice con enlaces a subsecciones (POUM, ORPIME, normativa); no hay visor de expedientes con código propio en HTML estático.
- **Tauler d'edictes (seu-e):** portlet AOC transparència + DataTables; filas cargadas dinámicamente (no scrapeable sin API interna).
- **Tràmits urbanístics:** catálogo FS-00…FS-22 en web + seu-e; ORPIME simplifica comunicaciones vs licencias.

## Licencias de obra

No hay dataset público de concesiones (como Madrid SIGMA). La ciudadanía tramita vía:

- Assistent geoportal (`geoportal.olesademontserrat.cat`)
- Seu-e (formularios de llicència / comunicació prèvia)
- BPM OAC (`bpm.olesademontserrat.cat`) para instancias

El adapter expone **páginas informativas** de trámites (patrón Pozuelo/Cerdanyola).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** Geoportal **Enmapa** (Mapia Technologies) en `geoportal.olesademontserrat.cat` — OpenLayers, capas WMS/GeoServer referenciadas en bundle Angular (`/getmapfile`, `geoserver_url` con token). Visor guía: `/visor/guia/`. Enlace externo Mapia Streets con token.
- **Estrategia:** Los metadatos scrapeados (PDF POUM/PE, Liferay) **no incluyen** código de expediente enlazable al visor. RPUC/MUC (08154) sirven como referencia de planeamiento autonómico, no join 1:1 con filas del adapter.
- **Limitaciones:** Certificado TLS del geoportal no encadenado con CA públicas (`insecure_ssl` en manifest). Capas WMS requieren sesión/token Enmapa; tauler edictes sin HTML estático. Sin WFS/ArcGIS público por código de expediente municipal.

## Limitaciones generales

- Tauler edictes: Liferay + JS (sin listado en HTML inicial).
- Geoportal: SSL propio; geometría no automatizable desde listados actuales.
- Sin entradas BOCM regionales para este municipio en la cola (`bocm_count: 0`).
