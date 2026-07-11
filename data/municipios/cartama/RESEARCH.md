# Cártama — investigación portal ayuntamiento

**Municipio:** Cártama (Málaga, Andalucía)  
**Slug:** `cartama`  
**Boletín:** BOJA (`boja`, 30 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa (raíz) | https://www.cartama.es | **Bloqueada** — CloudFront WAF 403 en CI sin UA de navegador |
| Web corporativa (subpáginas) | https://www.cartama.es/3918/urbanismo-planeamiento-y-gestion-urbanistica | **Operativa** — hosting Diputación Málaga (`static.malaga.es`) |
| Sede electrónica | https://cartama.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://cartama.sedelectronica.es/board/ | **Operativa** — tabla HTML Wicket (~10 filas/página) |
| Portal transparencia | https://cartama.sedelectronica.es/transparency | **Operativa** — categoría 8 URBANISMO (935 docs); navegación Wicket AJAX |
| Catálogo trámites | https://cartama.sedelectronica.es/dossier | **Redirect loop** en CI (10 redirecciones) |
| Consulta expedientes | https://cartama.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |

### Páginas de procedimiento planeamiento (web Diputación Málaga)

| URL | Contenido |
|-----|-----------|
| https://www.cartama.es/3918/urbanismo-planeamiento-y-gestion-urbanistica | Área urbanismo |
| https://www.cartama.es/4135/instrumentos-planeamiento-vigentes-tramitacion | Índice instrumentos en tramitación |
| https://www.cartama.es/4136/innovaciones-plan-general | Innovaciones PGOU |
| https://www.cartama.es/4141/planes-parciales | Planes parciales |
| https://www.cartama.es/4140/planes-especiales | Planes especiales |
| https://www.cartama.es/4135/estudios-detalle | Estudios de detalle |
| https://www.cartama.es/4139/otros-instrumentos-ordenacion-urbanistica-proyectos-actuacion | Proyectos de actuación |
| https://www.cartama.es/11116/proyectos-urbanizacion-procedimiento | Proyectos de urbanización |
| https://www.cartama.es/4134/estatutos-bases-actuacion-aprobacion-constitucion | Estatutos y JC |
| https://www.cartama.es/4142/reparcelacion-abreviada | Reparcelación abreviada |
| https://www.cartama.es/16271/plan-edil | Plan Edil |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Coín, Humanes, Mijas.
- **Listado:** tabla HTML `AdvertisementBoardListPanel` con columnas:
  - `class_name` (documento)
  - `class_folderCode` (expediente)
  - `class_folderName` (procedimiento)
  - `class_boardCategory` (categoría)
  - `class_description`
  - `class_dateFrom` (fecha DD/MM/YYYY)
- **Documentos:** enlace `preview-document/{uuid}` (PDF en visor sede).
- **Paginación:** botón «Mostrar más» vía Wicket AJAX; el adapter parsea la primera página.
- **Primera página (jul 2026):** mayoría anuncios de tesorería (ordenanza fiscal ICIO), empleo público, padrón y presupuesto; sin planeamiento urbanístico en la página visible.

## Licencias de obra

- No hay dataset público de concesiones de obra mayor/menor.
- Las licencias publicadas aparecen en el tablón como edictos o procedimientos de «Licencias de Obra/Actividad» cuando existen.
- Trámites informativos en sede `/dossier` (inaccesible por redirect loop en CI).

## Proyectos / planeamiento

- **Tablón:** anuncios BOP/BOJA de planeamiento cuando se publican (procedimiento «Planeamiento General», etc.).
- **Web:** hojas de procedimiento de instrumentos de planeamiento (innovaciones PGOU, planes parciales/especiales, estudios de detalle, etc.) — contenido normativo/procedimental, no listado de expedientes activos.
- **Transparencia:** categoría «8. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con ~935 documentos; requiere sesión Wicket AJAX para navegar subcategorías.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SGM (Sistema Geográfico Municipal) interno — la web exige presentar zonificación en formato vectorial/GIS al tramitar planeamiento, pero no hay visor público municipal.
  - VITUA (visor territorial Junta de Andalucía): consulta cartográfica provincial, sin enlace por código de expediente del tablón.
  - No se encontró ArcGIS REST/WFS/GeoJSON público enlazable a expedientes del ayuntamiento.
- **Estrategia:** sin query determinista expediente → polígono; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Tablón y transparencia publican PDF sin georreferencia embebida.
  - Web raíz bloqueada por WAF; dossier con redirect loop.
  - Sin campo GIS en metadatos del tablón.

## Limitaciones generales

- `www.cartama.es` raíz bloqueada CloudFront (403); subpáginas Diputación accesibles con UA navegador.
- Tablón paginado AJAX (solo primera página).
- `/dossier` redirect loop en entorno CI.
- Transparencia Wicket no scrapeable de forma determinista sin sesión.
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.cartama:CartamaAyuntamientoAdapter`
- Fuentes: tablón sede + páginas procedimiento planeamiento (web) + páginas informativas trámites.
- IDs: `cartama-lic-*` / `cartama-proy-*` (sha256[:14]).
