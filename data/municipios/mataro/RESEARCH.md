# Mataró — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|--------|
| Slug | `mataro` |
| Web | https://www.mataro.cat |
| CMS | Plone (Zope) |
| Sede | https://seu.mataro.cat (acceso muy lento / timeout desde cloud) |
| Geoportal | http://mapes.mataro.cat → https://serveisweb.mataro.cat/GeoMat/visor/ |

## Fuentes — proyectos / planeamiento

| URL | Contenido |
|-----|-----------|
| https://www.mataro.cat/ca/temes/urbanisme/el-planejament-urbanistic/planejament-en-periode-dexposicio-publica | Listado Plone de instrumentos en exposición pública (CA) |
| https://www.mataro.cat/es/temas/urbanismo/planificacion-urbanistica/planeamiento-urbanistico-en-exposicion-publica | Índice ES + carpeta vigente |
| https://www.mataro.cat/es/temas/urbanismo/planificacion-urbanistica/planeamiento-urbanistico-en-exposicion-publica/documents-en-periode-d2019exposicio-publica-vigent-1 | Subpáginas por expediente (PE, MPG, ED, PMU, etc.) |
| https://www.mataro.cat/ca/lajuntament/projectes-dobres-en-exposicio-publica | Carpeta vacía (“no hi ha elements”) a fecha 2026-10 |
| https://www.mataro.cat/rss.xml | RSS global Plone (filtro urbanismo en adapter) |

**Formato:** HTML Plone por expediente (`<h1>`, meta `DC.date.modified`, enlaces PDF). Sin API JSON pública.

## Fuentes — licencias

| URL | Contenido |
|-----|-----------|
| https://www.mataro.cat/ca/temes/urbanisme/llicencies-dobres-i-activitats | Información y enlaces a trámites |
| https://www.mataro.cat/es/temas/urbanismo/licencias-de-obras-y-actividades | Equivalente ES |
| https://www.mataro.cat/ca/tramits | Catálogo general de trámites |
| https://citaprevia.gestorn.com/llicencies/#nbb | Cita previa licencias (Gestorn) |
| https://seu.mataro.cat | Sede electrónica — tablón no verificado (timeout >60s en entorno agente) |

No hay dataset abierto de licencias concedidas con dirección/coordenadas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** Geoportal municipal (`serveisweb.mataro.cat/GeoMat/visor/`, perfiles `Planol_Mataro`, `Parcellari`, `Limit_Municipal`, etc.) y visor histórico `visorSIG`. Cartografía de referencia y temática; **no** capa consultable por código de expediente ni WFS/ArcGIS REST público enlazado al planeamiento en exposición.
- **Estrategia:** El adapter no enriquece `geom_geojson`; el orquestador usará centroide municipal + jitter (`centroid` en manifest).
- **Limitaciones:** Visor Leaflet propietario sin REST documentado; planeamiento publicado como PDF/HTML en Plone; sede inaccesible para tablón en CI/cloud.

## Limitaciones generales

- Sede `seu.mataro.cat` no responde en tiempo razonable desde el entorno del agente.
- Carpeta “projectes d’obres en exposició pública” sin documentos activos.
- Contenido bilingüe CA/ES: el adapter prioriza semillas CA+ES de exposición pública.
- Paginación RSS amplia; solo se conservan ítems con keywords urbanísticas.

## Adapter

- Módulo: `municipio/adapters/mataro.py`
- Patrón: crawl determinista de URLs de exposición + RSS filtrado; licencias como filas informativas de trámites/RSS.
