# Ingenio — investigación portal ayuntamiento

Municipio: **Ingenio** (`ingenio`) — Canarias, provincia Ingenio (Gran Canaria). Boletín: `boc_canarias` (7 avisos BOCM).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal | https://ingenio.es |
| Urbanismo | https://ingenio.es/urbanismo/ |
| Plan General de Ordenación (PGO) | https://ingenio.es/plan-general-de-ordenacion-urbana/ |
| Catálogo arquitectónico | https://ingenio.es/catalogo_arquitectonico/ |
| Sede electrónica | https://ingenio.sedelectronica.es |
| Tablón de anuncios | https://ingenio.sedelectronica.es/board |
| Trámites (dossier) | https://ingenio.sedelectronica.es/dossier |
| Información pública (sede) | https://ingenio.sedelectronica.es/info |
| Archivo planeamiento Canarias | https://www3.gobiernodecanarias.org/aplicaciones/archivoplaneamientopt/pages/consulta/islaMunicipio.jsp?municipio=11&provincia=35 |
| Transparencia | http://transparencia.ingenio.es/ |

## Cómo se listan expedientes / planeamiento

- **CMS:** WordPress con tema Divi (`ingenio.es`); PDFs en `/wp-content/uploads/`.
- **PGO vigente:** página dedicada con ~40 PDFs (memorias, normas, planos por zona: núcleo urbano, costa, periferia).
- **Noticias urbanismo:** categoría `/category/noticias/urbanismo/` y posts sobre revisión PGO, agenda urbana 2030, actuaciones urbanísticas.
- **Sede espublico gestiona:** tablón `/board` con tabla HTML (`class_name`, `class_folderCode`, `class_folderName`, `class_description`, `class_dateFrom`) y enlaces `preview-document/{uuid}`.
- **Archivo Canarias:** 13 instrumentos de planeamiento general + 1 de desarrollo; consulta por formulario JSP, sin API REST.
- **No hay** listado público de expedientes urbanísticos individualizados con código enlazable (consulta expedientes requiere identificación en sede).

## Licencias de obra

- **Sin dataset** de licencias concedidas publicado en web.
- **Formularios PDF** en `/urbanismo/`: ordenanzas licencias, solicitud certificado/informe urbanístico, modificación planeamiento.
- **Trámites informativos** en sede `/dossier` (licencias obra, segregación, comunicaciones previas, etc.).
- El tablón puede incluir edictos de licencias cuando se publican; en la investigación predominan anuncios administrativos (plenos, subvenciones, personal).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **Portal municipal:** sin visor urbanístico ni enlace a ArcGIS/GeoJSON en datos abiertos.
  - **Archivo planeamiento Gobierno de Canarias:** instrumentos y documentos PDF; sin WFS/GeoJSON por expediente.
  - **IDECanarias / Grafcan:** sin capa WFS accesible para ámbitos de Ingenio desde el entorno de CI.
  - **PDFs PGOU:** planos rasterizados (PDF), no geometría vectorial parseable de forma determinista.
- **Estrategia:** no hay query por código de expediente ni descarga GeoJSON/WFS municipal. El orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** planeamiento solo en PDF; sede `/info` lenta o vacía en CI; sin API GIS pública.

## Limitaciones generales

- Sede `/info` (información pública) con timeouts intermitentes; el tablón `/board` responde correctamente.
- Sin licencias concedidas en listado abierto; solo trámites informativos y formularios.
- Revisión/modificación sustancial del PGO documentada en BOCM 2021; expediente accesible vía sede con cita previa.
- Posts de noticias mezclan actuaciones urbanísticas con contenido no planeamiento (cross urbano, huertos); el adapter filtra por keywords.
