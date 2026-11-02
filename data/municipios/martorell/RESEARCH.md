# Martorell — investigación portal ayuntamiento

## URLs base y semillas

| Fuente | URL | Notas |
|--------|-----|--------|
| Web municipal (iDisc) | https://www.martorell.cat | CMS iDisc; planificación en regidoria |
| Planificación urbanística | https://www.martorell.cat/ajuntament/regidories/planificacio-urbanistica.htm | Contacto servicio; enlace transparencia |
| Tràmits web (Obres i Urbanisme) | https://www.martorell.cat/seu-electronica/tramita-amb-nosaltres.htm?fcat_221=46 | Catálogo informativo → seu-e |
| Seu electrònica (AOC) | https://seu-e.cat/ca/web/martorell | Liferay; govern obert + tràmits |
| Urbanisme (transparència) | …/accio-de-govern-i-normativa/urbanisme | Subsecciones planejament, normativa, info geogràfica |
| Tauler d'edictes | …/tauler-d-edictes-i-anuncis | Portlet AOC (contenido dinámico) |
| Catàleg tràmits urbanisme | …/tramits/classificacio/urbanisme | 1 tràmit scrapeable (informe urbanístic) |
| Noticias municipales | https://martorelldigital.cat | Sitemap con actuaciones urbanísticas recientes |
| eAdministració | https://martorell.eadministracio.cat | Presentación telemática (302) |
| Sitemap web | https://www.martorell.cat/media/site1/sitemap.xml | Crawl-delay 60 s |

## Expedientes / planeamiento

- **Transparencia seu-e:** páginas descriptivas del PGOU y documentación de planeamiento (HTML estático en `<p>`).
- **RPUC:** https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08113 (formulario; sin listado JSON).
- **WFS MUC sectores:** `PLANEJAMENT:MUC_PDERIVAT_SECTOR` filtrado `CODI_INE='08113'` — **9 sectores** con polígono y metadatos (`NOM_PLA`, `EXPEDIENT`, `ESTAT_PLANEJAMENT`).
- **Noticias:** martorelldigital.cat publica aprobaciones PGOU, PMU Can Valls, reurbanizaciones, etc.

## Licencias

- Catàleg seu-e **urbanisme** muy reducido (informe urbanístic); la mayoría de trámites de obras se presentan vía **eAdministració** o fichas informativas web.
- No hay dataset público de licencias concedidas con dirección/coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS Generalitat `https://sig.gencat.cat/ows/PLANEJAMENT/wfs` capa `MUC_PDERIVAT_SECTOR` (CODI_INE 08113); visor MUC https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08113
- **Estrategia:** metadatos de sector (NOM_PLA, EXPEDIENT) vía WFS; **no** se publica `geom_geojson` porque los polígonos devueltos caen fuera del límite IGN de Martorell (centroides ~41,73 vs término ~41,45–41,50).
- **Limitaciones:** licencias sin geometría; edictes en portlet JS; WFS requiere User-Agent tipo navegador (filtro GeoServer).

## Limitaciones generales

- `bocm_count: 0` — sin boletín regional asociado en cola.
- Rate limit ocasional (HTTP 429) en catàleg complet de tràmits seu-e.
- Contenido transparencia cargado por portlets AOC; scrape limitado a párrafos y títulos.
