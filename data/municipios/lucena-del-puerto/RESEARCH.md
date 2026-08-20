# Lucena del Puerto — investigación portal ayuntamiento

Municipio: **Lucena del Puerto** (`lucena-del-puerto`)  
Provincia: Huelva · CCAA: Andalucía · INE: **21047** · Boletín: BOJA

## URLs base y páginas semilla

| Recurso | URL | Notas |
|---------|-----|-------|
| Sede electrónica (espublico gestiona) | https://lucenadelpuerto.sedelectronica.es | Portal principal operativo |
| Tablón de anuncios | https://lucenadelpuerto.sedelectronica.es/board/ | HTML tabla Wicket, ~7 anuncios visibles |
| Catálogo de trámites | https://lucenadelpuerto.sedelectronica.es/dossier | Requiere cookie jar (redirect a dossier.0) |
| Transparencia | https://lucenadelpuerto.sedelectronica.es/transparency/ | Sección «URBANISMO Y OBRAS PÚBLICAS (20)» vía AJAX |
| Consulta expedientes | https://lucenadelpuerto.sedelectronica.es/expedientes | Requiere identificación |
| SITUA búsqueda | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento autonómico |
| SITUA PGOU municipio | https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf?municipiosSeleccionados=21047&codigosMunicipios=21047 | Documentación PGOU/NNSS |
| VITUA visor | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ | Visor territorial autonómico |
| Web corporativa | https://www.lucenadelpuerto.es | **No resuelve** (sin DNS en 2026-08) |

## Cómo se listan expedientes / proyectos

- **Tablón sede (`/board/`)**: tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces a `/preview-document/{uuid}`. Pocos anuncios urbanísticos recientes (mayoría empleo, tributos, normativa no urbanística).
- **Catálogo trámites (`/dossier`)**: listado de procedimientos espublico con enlaces `/catalog/t/{uuid}`. Incluye licencias de obra mayor/menor, actividad, declaraciones responsables, modificaciones de planeamiento, etc. Sin histórico de concesiones publicadas.
- **Transparencia**: árbol Wicket con sección «URBANISMO Y OBRAS PÚBLICAS (20)»; documentos en `/preview-document/` (carga parcial en HTML estático, resto vía AJAX).
- **Planeamiento PGOU**: documentación en **SITUA** (modificaciones puntuales 5–8 tramitadas vía BOJA; expedientes en sede durante IP). No hay listado público de expedientes urbanísticos sin login.
- **CMS web municipal**: no disponible.

## Cómo se publican licencias

- **No hay dataset ni listado histórico** de licencias concedidas.
- Concesiones de licencias de obra/actividad deberían publicarse en el **tablón de anuncios** de la sede; actualmente sin entradas urbanísticas recientes.
- **Trámites informativos** en catálogo sede: solicitud licencia obra mayor/menor, licencia actividad, comunicación previa / declaración responsable, licencia ocupación, etc.
- Consulta de expedientes requiere **certificado / Cl@ve** en `/expedientes`.
- Diputación de Huelva ofrece Licyt@l para contratación, no para licencias urbanísticas de particulares.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - VITUA (visor autonómico): consulta por municipio, sin enlace por código de expediente del tablón sede.
  - SITUA: documentación PDF/planos del PGOU, sin API GeoJSON por expediente municipal.
  - No hay visor urbanístico municipal, ArcGIS local, WFS ni datos abiertos georreferenciados.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`centroid: [37.3089, -6.7289]`).
- **Limitaciones:** tablón solo PDFs/anuncios sin coordenadas; transparencia con documentos no georreferenciados; PGOU en SITUA sin geometría descargable por expediente del adapter.

## Limitaciones

- Web corporativa caída (sin DNS).
- Tablón con pocos anuncios y escaso contenido urbanístico reciente.
- Transparencia urbanismo requiere interacción Wicket/AJAX para listar los 20 documentos.
- `/dossier` devuelve redirect loop sin cookie jar (el adapter usa sesión HTTP).
- Sin listado público de licencias concedidas ni geometría enlazable.
