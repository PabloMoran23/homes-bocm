# Ciudad Rodrigo — investigación portal ayuntamiento

**Municipio:** Ciudad Rodrigo (`ciudad-rodrigo`)  
**Provincia:** Salamanca · **CCAA:** Castilla y León · **Boletín:** BOCYL

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal (WordPress) | https://www.ciudadrodrigo.es/ayuntamiento/ | Noticias, normativa urbanística, PGOU |
| Área urbanismo | https://www.ciudadrodrigo.es/ayuntamiento/area-de-urbanismo-y-obras/ | Enlaces a categorías y trámites |
| PGOU vigente | https://www.ciudadrodrigo.es/ayuntamiento/plan-general-de-ordenacion-urbana-municipal/ | Documentos PDF del planeamiento |
| Trámites / impresos | https://www.ciudadrodrigo.es/ayuntamiento/tramites-y-gestiones-impresos/ | Formularios licencias (PDF) |
| Informes seguimiento | https://www.ciudadrodrigo.es/ayuntamiento/informes-seguimiento-actividad-urbanistica/ | Memoria anual urbanismo (PDF) |
| Sede electrónica (espublico) | https://ciudadrodrigo.sedelectronica.es/ | Tablón de anuncios |
| Tablón anuncios | https://ciudadrodrigo.sedelectronica.es/board | Edictos recientes (Wicket/HTML) |
| Transparencia sede | https://ciudadrodrigo.sedelectronica.es/transparency | Portal transparencia espublico |

## Cómo se listan expedientes / proyectos

1. **WordPress REST API** (`/ayuntamiento/wp-json/wp/v2/posts?categories=<id>`):
   - `normativa-urbanistica-de-aplicacion-planeamiento` (~32 posts): PGOU, modificaciones, estudios de detalle, planes parciales
   - `normativa-urbanistica-de-aplicacion-gestion` (~8): proyectos de actuación, urbanización, reparcelación
   - `normativa-urbanistica-en-tramitacion-planeamiento` (~5): modificaciones en curso, PECH
   - `urbanismo-autorizaciones-de-uso-excepcional` (~77): autorizaciones suelo rústico
   - Cada post tiene `title`, `date`, `link` y PDFs embebidos en `content.rendered`

2. **Tablón sede espublico** (`/board`): tabla HTML Wicket con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Solo ~10 filas visibles sin paginación pública evidente. Incluye licencias urbanísticas y autorizaciones recientes.

3. **PGOU estático**: página WordPress con tablas de PDFs por sector/documento (no expedientes individuales con metadatos).

## Cómo se publican licencias

- **Tablón sede**: categorías `Licencias Urbanísticas`, `Licencias de Actividad` (algunas con ubicación en título).
- **No hay dataset público** de concesiones históricas ni listado masivo de licencias de obra.
- **Trámites**: página de impresos con formularios PDF (solicitud licencia obra, declaración responsable, ocupación vía pública, etc.) — informativos, no concesiones.
- **Consulta expedientes** en sede requiere autenticación Cl@ve.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - Web municipal: sin visor urbanístico ni enlaces ArcGIS/WFS/GeoJSON
  - Sede espublico: tablón solo PDF/HTML, sin mapa
  - Junta CyL IDE / catastro: no hay enlace desde portal municipal a capas consultables por expediente
  - PGOU publicado como PDFs/planos raster, no servicios SIG enlazables
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [40.5986, -6.5332]`)
- **Limitaciones:** planeamiento y licencias sin polígono georreferenciable en fuentes públicas scrapeables

## Limitaciones generales

- Sede espublico requiere `insecure_ssl: true` (certificado no verificable desde algunos entornos).
- Tablón sede muestra solo anuncios recientes (~10 filas).
- Sin API de expedientes abiertos; histórico en WordPress categorías.
- Contenido mayoritariamente PDF sin extracción automática de metadatos.

## Patrón de adapter

WordPress REST (categorías urbanismo) + tablón espublico + trámites informativos. Similar a El Molar / Humanes (espublico board) con capa WordPress como en adapters con `wp-json`.
