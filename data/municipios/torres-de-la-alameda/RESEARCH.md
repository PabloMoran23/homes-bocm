# Torres de la Alameda — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `torres-de-la-alameda` |
| Comunidad | Comunidad de Madrid |
| Boletín | BOCM (`bocm`) — 13 avisos históricos |
| CMS web | WordPress (`torresdelaalameda.org`) |
| Sede | espublico gestiona (`torresdelaalameda.sedelectronica.es`) |
| Visor regional | SIT Comunidad de Madrid |

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Web corporativa | https://www.torresdelaalameda.org | Dominio `.es` devuelve 403 a bots; usar `.org` |
| Urbanismo — trámites | https://www.torresdelaalameda.org/concejalias/concejalia-de-urbanismo-vias-y-obras/tramites-urbanismo/ | Licencias, DR, comunicaciones, fianzas |
| Urbanismo — licencias | https://www.torresdelaalameda.org/concejalias/concejalia-de-urbanismo-vias-y-obras/licencias/ | Guía de procedimientos |
| Departamento urbanismo | https://www.torresdelaalameda.org/concejalias/concejalia-de-urbanismo-vias-y-obras/departamento-de-urbanismo/ | Enlace al visor SITCM |
| PGOU | https://www.torresdelaalameda.org/pgou-torres-de-la-alameda/ | Post WP (nov 2021) |
| Sede — tablón | https://torresdelaalameda.sedelectronica.es/board | Tablón de anuncios (10 filas visibles) |
| Sede — catálogo urbanismo | https://torresdelaalameda.sedelectronica.es/catalog/t/e5deabcc-f0c5-455a-9bec-47304aa7f36c | Trámites electrónicos |
| Sede — expedientes | https://torresdelaalameda.sedelectronica.es/expedientes | Requiere Cl@ve; sin listado público |
| Visor SITCM | https://www.madrid.org/cartografia/sitcm/html/visor.htm | Planeamiento regional |
| WP REST urbanismo | https://www.torresdelaalameda.org/wp-json/wp/v2/posts?categories=40 | Categoría «Urbanismo» (54 posts) |

## Cómo se listan expedientes / proyectos

1. **SITCM WFS** (`sitcm:VPLA_V_AMBITO`): 9 ámbitos de planeamiento municipal (UA-01…UA-05, SAU-1R…SAU-4I) con polígonos en EPSG:4326. Fuente principal de proyectos con geometría.
2. **Tablón sede** (`/board`): tabla HTML con `preview-document` (documento, expediente, procedimiento, categoría). En la muestra actual predominan actas de pleno y anuncios BOCM administrativos; pocos urbanísticos.
3. **WordPress categoría 40 (Urbanismo)**: noticias de obras, PGOU, participación ciudadana, proyectos Live! Resorts/Cordish. Filtradas por regex de planeamiento/urbanismo.
4. **PGOU**: página dedicada sin PDFs directos enlazados; documentación en visor SITCM.

## Cómo se publican licencias

- **No hay listado público de concesiones** con coordenadas.
- Páginas informativas WP (trámites, licencias) + catálogo sede para presentación telemática.
- Tablón sede puede publicar licencias puntuales (filtro regex); actualmente sin filas de licencia en la página visible.
- Consulta de expedientes en sede requiere autenticación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='TORRES DE LA ALAMEDA'`
  - Campos: `DS_NOMB_AMB` (nombre ámbito, p. ej. `UA-05 CALVARIO`), `DS_COD_AMB`
  - Visor web: SITCM (sin API por expediente individual)
- **Estrategia:** descarga masiva de ámbitos municipales vía WFS; enriquecimiento por código UA/SAU en título del proyecto.
- **Limitaciones:**
  - No hay visor municipal propio ni enlace expediente→polígono.
  - Tablón/PDFs sin georreferencia.
  - Sede requiere `insecure_ssl` (cadena CA).
  - Dominio `.es` bloquea scraping automatizado (403).

## Limitaciones generales

- Sin dataset abierto de licencias concedidas.
- Tablón sede con paginación limitada (10 anuncios visibles).
- Página `/planeamiento/` devuelve 404; PGOU en post histórico.
- SSL sede: usar `insecure_ssl: true` en manifest.
