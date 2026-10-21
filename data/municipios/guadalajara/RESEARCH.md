# Guadalajara — investigación portal ayuntamiento

Municipio: **Guadalajara** (`guadalajara`), provincia Guadalajara, Castilla-La Mancha. INE `19130`.

## URLs base y semillas

| Fuente | URL | Formato |
|--------|-----|---------|
| Web corporativa | https://www.guadalajara.es | CMS municipal propio |
| Tablón RSS (anuncios) | https://www.guadalajara.es/es/cargarTablonRss.do?maxResultadosIniciales=300 | RSS 2.0 (`item` → título, link, pubDate) |
| PGOU / normativa | https://www.guadalajara.es/es/ayuntamiento/normativa/normas-urbanisticas/plan-de-ordenacion-urbana-de-guadalajara/ | HTML + PDFs estáticos |
| Trámites urbanismo (índice) | https://www.guadalajara.es/es/sede-electronica/tramites/tramites-gestion-urbanistica/ | HTML enlaces MOD |
| Sede electrónica (espublico gestiona) | https://sedeelectronica.guadalajara.es | Wicket + tablón `/board`, catálogo `/dossier` |
| Sede legacy (dguadalajara) | https://dguadalajara.sedelectronica.es | Redirige a `/info`; no expone STA tipo Getafe |
| Geoportal | https://www.guadalajara.es/es/ayuntamiento/geoportal/ | Enlaces a ArcGIS Experience (mapa web, solares, movilidad) |
| Mapa web | https://www.guadalajara.es/es/mapa-web/ | Enlaces a visores y sede tablón |

## Expedientes / planeamiento

- **Información pública y actuaciones** aparecen en el **tablón RSS** del portal (títulos con fecha ISO, p. ej. PAU sector AVE, SUE-18, PMUS).
- El **PGOU** se publica como memoria, catálogo y planos PDF en la página de normativa; modificaciones puntuales enlazadas como PDF/HTML.
- La sede **no lista expedientes urbanísticos** sin autenticación (carpeta ciudadana); el tablón `/board` vigente (oct 2026) contiene sobre todo subvenciones y empleo, no planeamiento.
- **Trámites** en `/dossier`: 194 procedimientos; sección `URBANISMO.*` y licencias de actividad/ocupación vía p URLs `/catalog/t/...`.

## Licencias

- No hay dataset público de concesiones (fecha, dirección, coords).
- El adapter ingiere **páginas informativas** de trámites de licencia (obra mayor/menor, comunicación previa, DR, ocupación vía pública, actividades) desde el catálogo de la sede, al estilo Pozuelo/Pelabravo.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Geoportal con experiencias ArcGIS Online (`experience.arcgis.com`, cuenta `aytoguadalajara.maps.arcgis.com`): mapa web, solares sin edificar, movilidad. No se encontró FeatureServer/MapServer REST público con campo de expediente enlazable al tablón o RSS.
- **Estrategia:** El adapter no rellena `geom_geojson`; el orquestador usa `centroid` del manifest + jitter en geocode.
- **Limitaciones:** Planeamiento en PDF; visores GIS no consultables por código de sector/expediente sin API documentada; IDE CLM no respondió desde el entorno cloud en la investigación.

## Limitaciones generales

- Tablón sede sin entradas urbanísticas recientes (dependencia del RSS corporativo para proyectos).
- `dguadalajara.sedelectronica.es` distinto host de `sedeelectronica.guadalajara.es` (producto espublico actual).
- Paginación RSS limitada por `maxResultadosIniciales` (300).
