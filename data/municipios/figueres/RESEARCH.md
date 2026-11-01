# Figueres — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL | Notas |
|---------|-----|--------|
| Web municipal (Plone) | https://www.figueres.cat | Temática urbanisme, tràmits |
| Planejament urbanístic | https://www.figueres.cat/temes/urbanisme/planejament-urbanistic | RSS con acuerdos, PEUs, modificaciones POUM |
| Projectes urbanisme | https://www.figueres.cat/temes/urbanisme/projectes | RSS (~20 ítems), códigos GSUR* |
| POUM | https://www.figueres.cat/temes/urbanisme/poum | Documentación planeamiento vigente |
| Tràmits licencias | https://www.figueres.cat/tramits/tramits-i-gestions/llicencies-dobres | Enlaces a tramitación |
| Sede expedientes | https://tramit.figueres.org/OAC/SegExpStandalone.jsp?idioma=ca&useValid=true&ddlo=true&_UNITREE=CARP& | Consulta expedientes (Java OAC) |
| Planols / planejament | https://www.figueres.cat/figueres/planols/planejament-municipal | Enlaces a cartografía |
| Visor GIS municipal | https://wgis.figueres.org/v/index.html?visor=afectacions | Obras/afectaciones vía pública (capas internas) |

`seu.figueres.cat` redirige al portal Plone principal (no sede Liferay independiente).

## Listado de expedientes / proyectos

- **Plone RSS:** `planejament-urbanistic/rss.xml` y `projectes/rss.xml` (Atom/RSS 2.0) con título, enlace y cuerpo HTML en CDATA.
- **Crawl HTML:** listados bajo `/temes/urbanisme/planejament-urbanistic/*` y `/temes/urbanisme/projectes/*` (incl. `projectes-en-exposicio-publica`).
- **Metadatos:** `DC.date.modified` en ficha Plone; PDFs adjuntos en “Fitxers relacionats”.
- **tramit.figueres.org:** árbol de consulta de expedientes; requiere identificador de expediente (no listado masivo anónimo scrapeable sin credenciales).

## Licencias

- No hay dataset abierto de licencias concedidas con coordenadas.
- **Trámites informativos:** páginas `llicencies-dobres`, `llicencies-urbanistiques`, `llicencies-destabliments` bajo `/tramits`.
- **Consulta sede:** enlace desde planejament a `tramit.figueres.org` (SegExpStandalone).
- RSS de planejament incluye acuerdos de suspensión de licencias (filas informativas, no concesiones unitarias).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** `wgis.figueres.org` (visor propietario; sin endpoint ArcGIS REST `/rest/services` accesible desde el entorno del agente). Planols en PDF/imagen en Plone.
- **Estrategia:** el adapter no puede enlazar código GSUR/POUM a polígono vía API pública; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** Figueres fuera del ámbito AMB (no capa `geoportal.amb.cat` de expedientes); polígonos de suspensión solo en PDF; visor wgis orientado a afectaciones de obra, no a expedientes de planeamiento.

## Limitaciones generales

- CloudFront puede devolver 403 sin User-Agent de navegador en algunas rutas; el adapter usa `poc-bocm-figueres/1.0` (aceptado en RSS/HTML probado).
- Sin `boletin_source_id` local (municipio sin filas BOCM en este repo).
- Sync Supabase: requiere `SUPABASE_DB_URL` en el entorno de ejecución.
