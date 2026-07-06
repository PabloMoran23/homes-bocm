# Cártama — investigación portal ayuntamiento

**Municipio:** Cártama (Málaga, Andalucía)  
**Slug:** `cartama`  
**Boletín:** BOJA (`boja`, 30 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.cartama.es | **Bloqueada en CI** — CloudFront WAF (HTTP 405 captcha) |
| Sede electrónica | https://cartama.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://cartama.sedelectronica.es/board/ | **Operativa** — tabla HTML con preview-document |
| Portal transparencia | https://cartama.sedelectronica.es/transparency | **Operativa** — categoría «8. URBANISMO…» (929 docs) |
| Catálogo trámites | https://cartama.sedelectronica.es/dossier | Redirección en bucle desde CI |
| Consulta expedientes | https://cartama.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Planes especiales | https://www.cartama.es/4140/planes-especiales | WAF (referencia procedimiento) |
| Planes parciales | https://www.cartama.es/4141/planes-parciales | WAF |
| Innovaciones PGOU | https://www.cartama.es/4136/innovaciones-plan-general | WAF |
| Proyectos urbanización | https://www.cartama.es/11116/proyectos-urbanizacion-procedimiento | WAF |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Coín, Humanes, Algete.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}` (PDF embebido en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página (~10 filas).
- **Procedimientos urbanísticos observados** (histórico tablón, may 2026): «Licencias de Actividad», «Planificación y Ordenación» (no urbanismo), edictos BOPM/BOPMA.

### Ejemplos urbanísticos (referencia tablón)

| Expediente | Procedimiento | Descripción |
|------------|---------------|-------------|
| 2661/2026 | Licencias de Actividad | Calificación ambiental nave comercial (exposición pública) |
| — | Planeamiento | Anuncios BOPMA de aprobaciones iniciales/definitivas (cuando publicados) |

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor.
- Las licencias publicadas aparecen en el tablón como edictos o «Licencias de Actividad».
- Trámites informativos en sede `/dossier` (acceso con certificado digital).

## Proyectos / planeamiento

- **Tablón:** edictos de información pública, licencias de actividad con trámite ambiental, anuncios BOPMA.
- **Web corporativa:** secciones de procedimiento de instrumentos de planeamiento (planes especiales, parciales, innovaciones PGOU, urbanización) — contenido informativo, no listado de expedientes.
- **Transparencia:** categoría 8 con ~929 documentos; navegación Wicket AJAX (no determinista sin sesión completa).
- **PGOU vigente:** Adaptación Parcial LOUA aprobada 2009, innovaciones 2011 y 2013 (documentación en contratación pública / departamento urbanismo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - El ayuntamiento exige zonificación vectorial/GIS para incorporación al «Sistema Geográfico Municipal» interno (páginas de procedimiento).
  - No hay visor urbanístico público propio ni enlace ArcGIS/WFS desde el tablón o transparencia.
  - Diputación de Málaga / PRP Málaga (`gis.prpmalaga.es`) tiene visores para otros municipios de la provincia; no se localizó endpoint REST público para Cártama enlazable a expediente.
- **Estrategia:** sin query GIS por código de expediente; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Tablón y transparencia publican PDF sin georreferencia.
  - Web corporativa bloqueada por WAF impide extraer enlaces cartográficos.
  - Sin WFS/GeoJSON público por expediente.

## Limitaciones generales

- Web `cartama.es` no scrapeable (CloudFront WAF captcha).
- Tablón paginado con AJAX Wicket (solo primera página en adapter).
- Transparencia urbanismo requiere navegación Wicket no reproducible de forma estable.
- Consulta de expedientes requiere login.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.cartama:CartamaAyuntamientoAdapter`
- Fuentes: tablón sede + páginas informativas de trámites + procedimientos de planeamiento.
- IDs: `cartama-lic-*` / `cartama-proy-*` (sha256[:14]).
