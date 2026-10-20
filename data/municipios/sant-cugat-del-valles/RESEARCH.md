# Sant Cugat del Vallès — investigación portal ayuntamiento

## Fuentes principales

| Recurso | URL | Formato |
|---------|-----|---------|
| Seu electrònica (tabló) | https://seu.santcugat.cat/seu/Tablon.aspx?id_grupo=18 | ASP.NET GridView, `DetalleTablon.aspx?id=` |
| Índice tablones | https://seu.santcugat.cat/seu/TablonBox.aspx | HTML |
| Tràmits obres | https://seu.santcugat.cat/seu/Procedimientos.aspx?id_grupo=507 | HTML (grup FUE) |
| Guia informació urbanística | https://seu.santcugat.cat/seu/Procedimiento_ver_doc.aspx?plantilla=6221 | PDF guía |
| Projectes (web) | https://www.santcugat.cat/web/obres-en-projecte | CMS municipal (timeout frecuente en cloud) |
| Geoportal | https://geociutat.santcugat.cat/ | Visor Mapia (SPA) |
| GeoServer (legacy) | https://geo.santcugat.cat/geoserver/ | WFS/WMS (GetCapabilities público; GetFeature 401) |

## Proyectos / expedientes

- El grupo **T101 Urbanisme** (`id_grupo=18`) lista anuncios de aprobaciones, suspensiones de licencias, memorias técnicas e información pública.
- Cada fila enlaza a `DetalleTablon.aspx?id=<n>` con descripción, fechas de publicación/fin IP y adjuntos en `Tablon_ver_doc.aspx?id=&fichero=`.
- Los expedientes aparecen en el texto (p. ej. `Exp. 34342/2025`).
- No hay API JSON; el adapter parsea HTML determinista.

## Licencias

- No hay dataset público de concesiones de licencia de obra (solo anuncios puntuales en tablón, p. ej. suspensiones).
- Trámites: grupo 507 «Llicències d'obres particulars» en la seu.
- El adapter devuelve filas informativas de trámites + anuncios de tablón con palabras clave de licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** GeoServer `stcugatgufons:PLANOL_MUNICIPIS_G5`, capas de planeamiento `stcugatgpwms:TER_PLANEJAMENTQUALIF`, Geoportal Sant Cugat (geociutat).
- **Estrategia:** El adapter intenta WFS `GetFeature` del límite municipal (`PLANOL_MUNICIPIS_G5`) para enriquecer si la respuesta es GeoJSON; en el entorno del agente `GetFeature` devuelve **HTTP 401 Unauthorized** (Tomcat). El visor web no expone consulta por código de expediente sin sesión.
- **Limitaciones:** Sin enlace GIS expediente↔polígono en fuentes abiertas; PDFs del tablón sin georreferencia; `www.santcugat.cat` con timeouts SSL desde cloud. El orquestador usará centroide municipal + jitter.

## Otras limitaciones

- Paginación: el tablón urbanismo actual ~36 filas en una página.
- Certificados: la web corporativa puede no responder en el tiempo límite del scraper cloud; la seu es estable.
