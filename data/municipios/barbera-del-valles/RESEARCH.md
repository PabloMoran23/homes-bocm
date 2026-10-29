# Barberà del Vallès — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| slug | `barbera-del-valles` |
| INE | 08252 |
| Web | https://www.bdv.cat (Drupal 7) |
| Sede | https://bdv.eadministracio.cat + https://seu-e.cat/es/web/barberadelvalles |
| Comunidad | Catalunya (Barcelona) |

## Fuentes identificadas

### Planeamiento / proyectos

- **Hub urbanístico:** https://www.bdv.cat/es/planeamiento-y-gestion-urbanistica  
  Texto legal art. 23 Decreto 305/2006; enlaces a actuaciones en información pública y acuerdos adoptados.
- **Páginas de actuación** (URLs estables en sitemap): `proyecto-de-*`, `plan-de-mejora-urbana-*`, `plan-especial-*`, `modificacion-puntual-*`, `redaccion-y-aprobacion-*`, `proyectos-de-obras-locales`.
- **Noticias urbanísticas** filtradas en sitemap (reurbanizaciones, aprobaciones iniciales de proyectos, PMUA, etc.).
- **Govern obert — planejament:** https://seu-e.cat/es/web/barberadelvalles/govern-obert-i-transparencia/accio-de-govern-i-normativa/urbanisme/planejament-urbanistic  
  Enlaces a **RPUC** (`municipiSel=08252`) y **MUC visor** (`municipi=08252`).
- **RPUC:** https://dtes.gencat.cat/rpucportal/AppJava/cercaExpedient.do?reqCode=cerca&municipiSel=08252  
  Consulta de expedientes de planeamiento (SPA; sin API JSON pública simple).
- **Urbanismo y obras (Drupal):** https://www.bdv.cat/es/urbanismo-y-obras

### Licencias de obra

- **Directorio trámites Drupal** (taxonomía urbanismo): https://www.bdv.cat/es/tramites/urbanismo-y-obras  
  Fichas informativas (`/es/tramits/solicitud-de-licencia-de-obras`, comunicaciones previas, certificados, etc.).
- **Seu-e trámites urbanisme:** https://seu-e.cat/es/web/barberadelvalles/tramits-i-gestions/-/tramits/classificacio/urbanisme  
  Presentación telemática (IdCAT, certificado); **no** hay tablón público de licencias concedidas con fechas.
- **OAE** (oficina): https://oae.bdv.cat/ambits/urbanisme-i-obres/ — catálogo de trámites, sin dataset de concesiones.

### Listado de expedientes

- No hay OpenSIC / tablón de anuncios urbanístico scrapeable como Sabadell o Sant Cugat.
- Proyectos = páginas Drupal + noticias + referencias RPUC/MUC.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - MUC visor PTOP: http://ptop.gencat.cat/muc-visor/AppJava/home.do?municipi=08252  
  - Página transparencia «Información geográfica de urbanismo» (mapa embebido genérico, sin WFS documentado en HTML).
  - RPUC enlaza cartografía de planeamiento supramunicipal; no expone GeoJSON por expediente al crawler.
- **Estrategia:** ingestión de metadatos desde bdv.cat; geocodificación vía bbox municipal en `manifest.yaml` (centroide + jitter). No se rellena `geom_geojson` por fila (visor no queryable por código de expediente desde el adapter).
- **Limitaciones:** visor MUC requiere interacción humana; licencias sin georreferencia pública; PDFs de planeamiento sin enlace GIS automático.

## Adapter

- Módulo: `municipio/adapters/barbera_del_valles.py`
- Proyectos: sitemap + seeds + validación semántica en HTML.
- Licencias: trámites Drupal + enlaces seu-e / eAdministració (informativos).

## Limitaciones generales

- Sin listado histórico de licencias concedidas.
- Muchas noticias municipales mezclan obras y otros temas; el adapter filtra por URL/patrones urbanísticos.
- `bocm_count: 0` en cola (sin boletín regional asociado en CSV).
