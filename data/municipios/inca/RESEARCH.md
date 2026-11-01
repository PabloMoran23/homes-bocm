# Inca — investigación portal ayuntamiento

Municipio: **Inca** (`inca`) — Illes Balears / INE 07027

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://incaciutat.com |
| Área urbanismo (ES) | https://incaciutat.com/es/ayuntamiento/arees/urbanismo |
| PGOU / normativa | https://incaciutat.com/pgou |
| Sede electrónica | https://incaciutat.sedelectronica.es/ |
| Tablón anuncios | https://incaciutat.sedelectronica.es/board |
| Catálogo trámites | https://incaciutat.sedelectronica.es/dossier |
| Geoportal urbanístic | https://mapes.incaciutat.com/geoportal/ |
| Portal mapas | https://mapes.incaciutat.com/portada/ |
| SIG municipal (Enmapa) | https://sig.incaciutat.com/ |
| Visor planeamiento CAIB | http://muib.caib.es/mapurbibfront/visor_index.jsp |
| WP REST API | https://incaciutat.com/wp-json/wp/v2/posts |

## Proyectos / planeamiento

- **WordPress 6.x**: modificaciones puntuales PGOU (`mp-*-pgou`), supresiones UA, catálogo de elementos, PMUS, etc. en categoría **Urbanisme i patrimoni** (id `62`) y búsquedas `pgou` / `modificació`.
- Entradas recientes (2024–2026): MP-25, MP-20–23, supresión UA-9/UA-10, parc logístic UA-21, modificaciones catálogo.
- **PGOU 2012**: documentación PDF enlazada desde `/pgou` (normativa, planos, BOIB).
- **Tablón sede**: formato espublico gestiona (tabla `class_name`, `class_folderCode`, preview-document). En la primera página (oct 2026) predominan padrón/elecciones/subvenciones; el adapter filtra filas urbanísticas cuando aparecen.
- **Trámites /dossier**: catálogo espublico (enlaces `/catalog/t/...`); requiere sesión cookie para evitar bucles de redirección.

## Licencias de obra

- No hay listado público de concesiones de licencia (solo trámites y formularios).
- Formularios PDF en la página de urbanismo: comunicación previa LUIB, declaración responsable, licencias con/sin proyecto, parcelación, ocupación, rótulos, placas solares.
- Catálogo sede y tablón como fuentes complementarias (como Pozuelo/Piñuécar cuando no hay dataset de concesiones).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Geoportal urbanístic Angular/Cesium: https://mapes.incaciutat.com/geoportal/ (cartografía PGOU municipal; capas cargadas en cliente, sin URL WMS/WFS estable en bundle público).
  - SIG Enmapa: https://sig.incaciutat.com/ (visores temáticos turismo/guía).
  - Visor autonómico MapUrBIB (CAIB): http://muib.caib.es/mapurbibfront/visor_index.jsp
  - Catastro: enlace desde geoportal a OVCBusqueda (muni=27, Inca).
- **Estrategia:** no hay WFS tipo IDELMA `exp_absis` para Inca (probado `M027_URBANISME` → 404). El adapter no rellena `geom_geojson`; el orquestador usará centroide municipal + jitter.
- **Limitaciones:** contrato 2025 para SIG con expedientes georreferenciados aún en despliegue; tablón/PDF sin enlace GIS por expediente.

## Limitaciones generales

- Sin boletín regional asociado en cola (`bocm_count: 0`); datos de planeamiento vía web WP + PDFs.
- Tablón sede muestra solo ~10 anuncios recientes por página (sin paginación HTML obvia).
- `/dossier` puede ser lento (~70s); el adapter usa cookie jar espublico.
