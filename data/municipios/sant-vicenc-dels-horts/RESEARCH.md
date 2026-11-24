# Sant Vicenç dels Horts — portal ayuntamiento

Municipio en el área metropolitana de Barcelona (PGM). Código INE: **08263**. NIF ayuntamiento: P0826300F.

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa | https://svh.cat |
| Urbanismo (transparencia) | https://svh.cat/govern-obert-transparencia/accio-de-govern-i-normativa/urbanisme-got/ |
| Hub territorio / urbanismo | https://svh.cat/municipi/per-temes/territori-i-mobilitat/urbanisme/ |
| Noticias urbanismo | https://svh.cat/actualitat/noticies/materia/territori-urbanisme/ |
| Trámites (sitemap) | https://svh.cat/tramits-sitemap.xml |
| Instancia genérica (seu-e) | https://seu-e.cat/tramits/826340003/instancia-generica |
| Carpeta ciudadana | https://carpeta.svh.cat (certificado digital) |
| Geoportal AMB | https://geoportalplanejament.amb.cat/AppGeoportalPlanejament2/index.html |
| Listado PDF expedientes AMB | https://geoportalplanejament.amb.cat/Informacio/Llistats_expedients/b/08263_b.pdf |
| RPUC (08263) | https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08263 |
| Visor MUC | https://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08263&set-locale=ca |

## Cómo se listan expedientes / proyectos

- **CMS:** WordPress (Yoast SEO). Páginas de proyectos de urbanización, modificaciones PGM y PEU enlazadas desde `page-sitemap.xml` y noticias.
- **Fuente autoritativa de planeamiento en trámite/vigente:** capa **Expedients** del Geoportal AMB (`MapServer/3`), filtrable por `CODI_INE='08263'` (~95 polígonos con metadatos `NOMEXP`, `DGU`, `DAPRDEF`, `URL`).
- **RPUC / MUC:** consulta por municipio; no hay API scrapeable de detalle sin navegación Java en el portal, pero enlaces oficiales desde la web del ayuntamiento.
- **PDF AMB:** listado tabular histórico (similar al resto de municipios AMB).

## Licencias de obra

- No hay tablón público scrapeable de licencias **concedidas** (fechas/direcciones).
- El ayuntamiento publica **fichas de trámite** en `svh.cat/tramita/tramits/` (p. ej. `llicencia-urbanistica-dobres`, ocupación vía pública, primera ocupación).
- Presentación telemática vía **instancia genérica** seu-e (`826340003`) y carpeta ciudadana para seguimiento con certificado.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - ArcGIS REST AMB: `https://geoportal.amb.cat/geoserveisapp/rest/services/Planejament/Expedients/MapServer/3` (`returnGeometry=true`, `f=geojson`, `outSR=4326`, `where=CODI_INE='08263'`).
  - Visor MUC / Geoportal AMB (consulta humana; polígonos vía REST en el adapter).
  - WFS Gencat `PLANEJAMENT:MUC_PDERIVAT_SECTOR` con `CODI_INE='08263'`: **0 features** (municipio regido por PGM/AMB, no sectores MUC derivados en WFS).
- **Estrategia:** ingesta masiva desde capa AMB `Expedients`; enriquecimiento por coincidencia de título para páginas WordPress.
- **Limitaciones:** licencias sin georreferencia; PDF AMB no parseado en el adapter (solo enlace); RPUC sin geometría directa en scrape.

## Limitaciones generales

- Sin histórico de licencias en HTML abierto.
- Crawl WordPress limitado a sitemap + semillas (no todas las noticias paginadas).
- `request_delay_s` 0.35 s; User-Agent identificable.
