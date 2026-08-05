# La Cabrera — investigación portal ayuntamiento

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.lacabrera.es | OK (WordPress + Plesk) |
| Sede electrónica | https://lacabrera.sedelectronica.es | **503** (nginx, agosto 2026) |
| Página sede en WP | https://www.lacabrera.es/sede-electronica/ | OK — enlaces a sede + PDFs trámites |
| Ordenanzas | https://lacabrera.sedelectronica.es/transparency | 503 |
| Tablón anuncios | https://lacabrera.sedelectronica.es/board | 503 |
| SITCM WFS ámbitos | https://idem.comunidad.madrid/geoserver3/ows | OK |

No existe sección dedicada `/urbanismo/` en la web. La información urbanística se publica en:
- Noticias WP (bandos desbroce, obras, vivienda social, licitaciones)
- PDFs de trámites en la página de sede electrónica
- Ámbitos de planeamiento en el visor regional SITCM (NNSS 1996)

## Proyectos / expedientes

- **CMS:** WordPress (REST API parcialmente restringida; sitemap XML accesible)
- **Listado:** `wp-sitemap-posts-post-1.xml` + filtro por slug (bando, obras, vivienda, desbroce, plan)
- **Sede espublico gestiona:** tablón `/board` con tabla HTML + `preview-document/{uuid}` — actualmente inaccesible (503)
- **Planeamiento histórico:** 18 ámbitos únicos en SITCM (`DS_NOMB_AMB`: SAU-*, UE-*) aprobados BOCM 1996-08-13 (NNSS)

## Licencias de obra

- No hay dataset ni tablón scrapeable (sede caída)
- Formularios informativos en WP sede:
  - Declaración responsable urbanística de obras (PDF)
  - Declaración responsable actividades (PDF)
  - Instancia general (PDF)
- Sin concesiones publicadas con coordenadas; adapter devuelve páginas de trámite (`min_rows: 0` licencias)

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM `sitcm:VPLA_V_AMBITO` filtro `DS_MUNICIPIO='LA CABRERA'`
  - 20 features (18 ámbitos únicos: SAU-1..7, UE-1A..10)
  - Campo enlace: `DS_NOMB_AMB` (código + nombre sector)
- **Estrategia:** cargar todos los ámbitos SITCM como proyectos con polígono; enriquecer posts WP por matching de código SAU/UE en título
- **Limitaciones:**
  - Sede espublico 503 — sin tablón ni expedientes IP actuales
  - Web sin visor propio ni GeoJSON municipal
  - Posts de noticias (obras calle, asfaltado) sin georreferencia en portal
  - SITCM solo cubre ámbitos de planeamiento aprobados (no licencias puntuales)

## Limitaciones generales

- SSL sede válido pero servicio caído (503)
- Sin paginación en sitemap (91 posts, 1 página)
- User-Agent identificable requerido; sin dependencia de LLM
