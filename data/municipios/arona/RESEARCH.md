# Arona — investigación portal ayuntamiento

Municipio: **Arona** (`arona`) — Canarias, provincia Santa Cruz de Tenerife. Boletín: `boc_canarias` (10 avisos BOCM).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal principal | https://www.arona.org |
| Urbanismo (DNN) | https://www.arona.org/Areas-Municipales/Urbanismo |
| Convenios urbanísticos | https://www.arona.org/Areas-Municipales/Urbanismo/Convenios-urbanisticos |
| Proyectos de urbanización | https://www.arona.org/Areas-Municipales/Urbanismo/Proyectos-de-urbanizaci%C3%B3n |
| Plan Especial Puerto Las Galletas | https://www.arona.org/Areas-Municipales/Urbanismo/Plan-Especial-de-Ordenacion-del-Puerto-de-Las-Galletas |
| PGOU 1992 | https://www.arona.org/Areas-Municipales/Urbanismo/Plan-General-de-Ordenacion-Urbana-1992/PGOU |
| Consulta pública PG | https://www.arona.org/Areas-Municipales/Urbanismo/Consulta-Publica-Plan-General |
| Trámites urbanismo | https://www.arona.org/Areas-Municipales/Urbanismo/Tramites |
| Sede electrónica | https://sede.arona.org |
| Tablón STA | https://sta.arona.org/sta/CarpetaPublic/doEvent?APP_CODE=STA&PAGE_CODE=TABLON |
| Urbamap (visor) | http://emapext.arona.org/emap/emapWebView01.aspx?prjid=URBAMAP_P&cfg=urbamap&scope=CATASTRO&lang=3 |

## Cómo se listan expedientes / planeamiento

- **CMS:** DotNetNuke en `arona.org` (`/Portals/0/documentos/`, `/Portals/0/adjuntos/`, `/RecursosWeb/DOCUMENTOS/`).
- **Documentos:** enlaces HTML con título + PDF (memorias, anuncios BOP/BOC, convenios, planos PGOU, proyectos de urbanización).
- **Noticias urbanismo:** `/Areas-Municipales/Urbanismo/Noticias/ctl/Ver/mid/529?id=…` (artículos con texto, sin API).
- **Tablón sede:** STA T-Systems embebe `var dataset_TABLON = […]` en el HTML del tablón (mismo patrón que Getafe/Fuenlabrada pero `PAGE_CODE=TABLON`). Durante la investigación el servicio devolvió **503** de forma intermitente; el adapter reintenta y continúa con DNN.
- **No hay** listado público de expedientes urbanísticos individualizados con código enlazable (carpeta ciudadana requiere login en `sta.arona.org`).

## Licencias de obra

- **Sin dataset** de licencias concedidas publicado en web.
- **Trámites informativos** en `/Areas-Municipales/Urbanismo/Tramites`: códigos 100–121A (obra mayor, actividades, comunicaciones previas, etc.) enlazando a `/Tramites/ctl/Ver/mid/1190?id=…`.
- Sede `sede.arona.org/Tramites` lista trámites generales (no solo urbanismo).
- El tablón STA puede incluir edictos de licencias cuando el servicio está operativo.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **Urbamap** (`emapext.arona.org`): visor TAO eMap/WebMapViewer para consulta catastral y planeamiento; interfaz web con iframes, sin REST/ArcGIS/WFS descubierto (`MapService.ashx` vacío, rutas `/emap/R/xPROJ/` → 403).
  - **IDECanarias / Grafcan:** WFS no accesible desde el entorno de CI (404/502).
- **Estrategia:** no hay query por código de expediente ni descarga GeoJSON/WFS municipal. Los PDFs/planos PGOU no incluyen geometría vectorial parseable de forma determinista.
- **Limitaciones:** visor interactivo sin API pública; expedientes no georreferenciados en el listado; el orquestador aplicará centroide municipal + jitter.

## Limitaciones generales

- Tablón STA con disponibilidad intermitente (503).
- Dominio legacy `ayuntamientodearona.es` con problemas SSL.
- Miles de planos históricos TIF/PDF PGOU — el adapter filtra ruido (indicadores estadísticos, multimedia) y prioriza documentos con keywords urbanísticas.
- Sin licencias concedidas en listado abierto; solo trámites informativos.
