# El Palmar de Troya — investigación portal ayuntamiento

**Municipio:** El Palmar de Troya (Sevilla, Andalucía)  
**Slug:** `el-palmar-de-troya`  
**INE:** 41053  
**CIF:** P4100053-J  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.elpalmardetroya.es | **Operativa** — OpenCMS INPRO theme7 |
| Urbanismo | https://www.elpalmardetroya.es/es/urbanismo/ | **Operativa** |
| PGOU/PGOM | https://www.elpalmardetroya.es/es/urbanismo/pgou | **Operativa** — sirve PDF directo (PGOM en redacción) |
| Proyectos de obra | https://www.elpalmardetroya.es/es/urbanismo/proyecto-de-obras/ | **Operativa** — ~77 PDFs (obras municipales, AV. Utrera, etc.) |
| Tablón INPRO | https://www.elpalmardetroya.es/.galleries/enlaces-generales/tablon-de-anuncios | **Operativa** — tablón embebido en dominio propio |
| Sede electrónica | https://sede.elpalmardetroya.es | **Operativa** — GSede OpenCMS (Guadaltel) |
| Transparencia | https://www.elpalmardetroya.es/es/ayuntamiento/transparencia | **Operativa** — indicadores Ley Transparencia (enlaces 404 en algunos indicadores) |
| Búsqueda urbanismo | https://www.elpalmardetroya.es/es/busqueda/?formCategoryFilter=/sites/elpalmardetroya/.categories/temas/urbanismo/&formTypeFilter=pm-noticia | **Operativa** — noticias categoría urbanismo |
| Licyt@l Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4100053J | **Operativa** — contratación local (no licencias de obra) |

## CMS y formato de listados

- **Web:** OpenCMS INPRO (`es.inpro.opencms.*`), galerías en `/export/sites/elpalmardetroya/.galleries/`.
- **Tablón:** INPRO tablón-1.0 embebido; tabla HTML `displaytag` con referencia/asunto/URL servlet; codificación latin-1.
- **Noticias:** Solr vía `/es/busqueda/` con filtros `formCategoryFilter` + `formTypeFilter=pm-noticia`.
- **PGOU:** la ruta `/es/urbanismo/pgou` devuelve un PDF (no HTML); municipio sin PGOU aprobado — en redacción del primer PGOM (licitación adjudicada feb 2024 a Buró 4).

## Tablón electrónico INPRO

- Escudo interno INPRO: `41904` (código Diputación); INE oficial `41053`.
- 9 edictos visibles (sep 2026): RRHH, BOP/cobranza, exposición electoral — **sin edictos urbanísticos** en el histórico actual.
- Documentos: `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...`

## Planeamiento / expedientes

| Tipo | Fuente | Notas |
|------|--------|-------|
| PGOM en redacción | Noticia 24/02/2026 + PDF avance | Exposición pública avance PGOM |
| Proyectos de obra | Galería `documentos-proyectos-de-obra` | Casa del Mayor, guardería, AV. Utrera, piscina, reurbanización |
| Licitaciones obra | Noticias + `/galleries/LICITACIONES/` | Plan Más Sevilla guardería (2025) |
| Licencia actividad ambiental | Noticia 15/01/2020 | Resolución alcaldía + PDF calificación ambiental |

## Licencias de obra

- No hay dataset público de concesiones de licencias urbanísticas.
- Sede GSede: catálogo de trámites sin listado público de expedientes concedidos.
- Licyt@l Diputación: contratación administrativa, no registro de licencias.
- Una licencia de actividad (calificación ambiental, 2020) publicada como noticia con PDF.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal (ArcGIS, gvSIG, etc.).
  - PGOM/PGOU y proyectos de obra solo en PDF raster en galerías OpenCMS.
  - SITUA Junta de Andalucía: sin planeamiento aprobado publicado para este municipio (PGOM en tramitación).
  - Diputación Sevilla: sin WFS/ArcGIS enlazable por expediente.
- **Estrategia:** documentos PDF sin georreferencia; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos y memorias son PDF/imagen, no servicios WFS/GeoJSON.
  - Indicadores transparencia urbanismo (PGOU, convenios) enlazan a rutas 404.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Municipio pequeño sin PGOU vigente; planeamiento en fase inicial (redacción PGOM).
- Tablón sin edictos urbanísticos recientes (mayoría RRHH/administrativo).
- Transparencia: indicador 50 (PGOU) devuelve 404 al acceder directamente.
- Licencias: páginas informativas + 1 noticia histórica de calificación ambiental.

## Adapter implementado

- `municipio.adapters.el_palmar_de_troya:ElPalmarDeTroyaAyuntamientoAdapter`
- Fuentes: tablón INPRO + PGOU PDF + proyectos de obra + noticias urbanismo + páginas informativas licencias.
- IDs: `el-palmar-de-troya-lic-*` / `el-palmar-de-troya-proy-*` (sha256[:14]).
