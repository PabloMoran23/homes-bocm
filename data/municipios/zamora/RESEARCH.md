# Zamora — investigación portal ayuntamiento

## Resumen

| Campo | Valor |
|-------|-------|
| Slug | `zamora` |
| Provincia | Zamora |
| CCAA | Castilla y León |
| Boletín | BOCyL (`bocyl`) |
| Web | https://www.zamora.es (ASP.NET, IIS) |
| Sede | https://zamora.sedelectronica.es (espublico gestiona) |

## Fuentes del portal

### Web corporativa (ASP.NET)

- **Urbanismo:** https://www.zamora.es/contenidos.aspx?id=32477
- **Planeamiento vigente (PGOU, PEPCHA, DR):** https://www.zamora.es/contenidos.aspx?id=309
- **Planeamiento de desarrollo:** https://www.zamora.es/contenidos.aspx?id=32474
- **Planes de actuación:** https://www.zamora.es/contenidos.aspx?id=32637
- **Planos PGOU:** https://www.zamora.es/contenidos.aspx?id=555
- **Planos PECH-A:** https://www.zamora.es/contenidos.aspx?id=32470
- **Consultas urbanísticas:** https://www.zamora.es/contenidos.aspx?id=156
- **Transparencia urbanismo:** https://www.zamora.es/contenidos.aspx?id=31409

Listado de documentos en HTML estático con enlaces a PDF (`/ficheros/`, `/img/cargadas/`). Sin API JSON. PMUS en SharePoint externo (no scrapeable).

### Sede electrónica (espublico)

- **Tablón de anuncios:** https://zamora.sedelectronica.es/board
- **Transparencia:** https://zamora.sedelectronica.es/transparency
- Tabla HTML `<tbody>` con columnas: documento, expediente, procedimiento, categoría, descripción, fechas.
- Enlaces PDF vía `preview-document/{uuid}`.
- `/dossier` e `/info` responden con timeout en CI (no usados).

### PlanPublica Junta de Castilla y León

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=49&municipio=275` (5 docs: PP sectores, PEPCHA)
- Información pública: `searchVPubDocMuniPlai.do?provincia=49&municipio=275`

### Licencias (páginas informativas de trámite)

No hay dataset público de concesiones. Páginas de procedimiento en web:

| Trámite | URL |
|---------|-----|
| Licencia abreviada (obra menor) | contenidos.aspx?id=152 |
| Licencia ordinaria (obra mayor) | contenidos.aspx?id=153 |
| Licencia ambiental | contenidos.aspx?id=148 |
| DRO | contenidos.aspx?id=155 |
| Modificación licencia ambiental | contenidos.aspx?id=149 |
| Licencia segregación | contenidos.aspx?id=21044 |

## Cómo se listan expedientes

| Fuente | Formato | Notas |
|--------|---------|-------|
| Sede board/transparency | HTML tabla + preview-document | 10 filas visibles por página; sin paginación AJAX detectada |
| Web planeamiento | HTML + PDFs directos | PGOU consolidado, estudios de detalle, anuncios BOP |
| PlanPublica | HTML tabla JCyL | Índice documental histórico |
| IDECyL WFS | GeoJSON features | Sectores SU-NC, planes parciales, ámbito instrumento |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 95 polígonos (c_mun 49275)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 9 polígonos
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono (ámbito PGOU)
  - Endpoint: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs?CQL_FILTER=n_mun='Zamora'`
- **Estrategia:** descarga WFS por municipio; enriquecimiento por coincidencia título/sector_id en anuncios del tablón y PDFs web.
- **Limitaciones:**
  - No hay visor urbanístico municipal público (Consultas Urbanísticas es trámite informativo, sin mapa ArcGIS).
  - PMUS/planos en SharePoint (`aytozamora-my.sharepoint.com`) no accesibles sin login.
  - Geometría disponible a nivel sector/plan parcial, no por expediente individual de licencia.

## Limitaciones generales

- Sede `/dossier` e `/info` inestables (timeout >60s).
- Tablón actual mayormente administrativo (JGL, tráfico, empleo); pocos anuncios urbanísticos recientes.
- Licencias: solo páginas de trámite, sin listado de concesiones.
- SSL sede: válido; no requiere `insecure_ssl`.
