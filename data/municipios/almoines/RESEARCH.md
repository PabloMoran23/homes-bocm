# Almoines — investigación portal ayuntamiento

**Municipio:** Almoines (Valencia, Comunitat Valenciana)  
**INE:** 46012  
**Boletín:** DOGV (`dogv`)

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.almoines.es |
| API DigitalValue | https://api.digitalvalue.es/almoines/collections/articulos |
| Sede electrónica | https://almoines.sedelectronica.es |
| Tablón de anuncios | https://almoines.sedelectronica.es/board |
| Normes urbanístiques | https://www.almoines.es/pagina/normes-urbanistiques |
| Text consolidat PGOU | https://www.almoines.es/pagina/text-consolidat-del-planejament-urbanistic-vigent |

## CMS y tecnología

- **Drupal 10** con tema `portalesmunicipales` (DigitalValue / portalesmunicipales.es).
- **API REST pública** en `api.digitalvalue.es/almoines/collections` (artículos, ficheros).
- **Sede electrónica** espublico gestiona (`almoines.sedelectronica.es`).
- URLs de artículos estables vía nodo Drupal: `/node/{rel}`.

## Proyectos / planeamiento

### Fuentes

1. **API DigitalValue** — noticias y páginas con expedientes de evaluación ambiental, PGOU, PMUS, Agenda Urbana, Pla Conviure, etc.
2. **ICV WFS** — inventario de sectores SU/SUZ del planeamiento valenciano (14 polígonos para INE 46012).
3. **Tablón sede** — edictos urbanísticos cuando se publican (actualmente sin entradas de urbanismo).

### Listado

- Artículos paginados en API (`limit`/`offset`); filtro por regex en título/slug.
- Sectores WFS: paginación `STARTINDEX` sobre `ms:InventarioSuSuz`, filtro cliente `cod_ine_mun=46012`.
- Documentos PDF adjuntos en `filesGroup` de la API.

## Licencias de obra

- **No hay registro público** de concesiones de licencias (como en Altea/Quart de Poblet).
- El catálogo de trámites (`/dossier`) redirige en bucle sin sesión.
- Fuentes usadas:
  - Páginas informativas (normes urbanístiques, tablón, sede).
  - Artículo API «Llicència ambiental, taller reparació» (información pública).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS ICV: `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Capa: `ms:InventarioSuSuz` (sectores SU/SUZ)
  - Campo municipio: `cod_ine_mun` = `46012`
  - Campos enlace: `pp`, `ue`, `denominaci`, `f_aprob`
- **Estrategia:** paginar WFS, filtrar por INE, extraer `gml:Polygon` → GeoJSON WGS84. En artículos API, intentar match por tokens UE/sector en título.
- **Limitaciones:**
  - Solo geometría de sectores del inventario ICV (no expedientes individuales del tablón).
  - Artículos de planeamiento sin polígono propio dependen del match textual con WFS.
  - No hay visor ArcGIS municipal propio.

## Limitaciones generales

- SSL intermitente en `www.almoines.es` (timeouts); adapter usa reintentos.
- Slug canónico Drupal ≠ slug API; se usa `/node/{rel}` como URL estable.
- Tablón sede sin licencias urbanísticas en el momento de la investigación.
- `/dossier` no accesible sin autenticación (redirect loop).
