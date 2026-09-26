# La Rinconada — investigación portal ayuntamiento

Municipio: **La Rinconada** (`la-rinconada`) — Provincia de Sevilla, Andalucía.

## URLs base y páginas semilla

| Fuente | URL | Tipo |
|--------|-----|------|
| Web municipal | https://www.larinconada.es/es/ | Corporativa (PHP/OpenCMS) |
| Portal transparencia | http://transparencia.larinconada.es/es/transparencia/ | OpenCMS SAGA (tema Diputación Sevilla) |
| Sede electrónica | https://larinconada.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón anuncios | https://larinconada.sedelectronica.es/board | HTML tabular (`class_name`, etc.) |
| Transparencia sede | https://larinconada.sedelectronica.es/transparency | Carpetas documentales |
| Trámites | https://larinconada.sedelectronica.es/dossier | Catálogo procedimientos |
| PGOU ZIP | http://larinconada.es/contenidos/pgou/pgou-la-rinconada.zip | Descarga planos PGOU |
| Carpeta ciudadano | http://carpeta.larinconada.es/ | Documentos IP (enlaces en BOP) |
| Urbano La Rinconada | http://urbanolarinconada.com/ | Bloqueado Cloudflare (403) |

### Indicadores transparencia (urbanismo)

- PGOU y planos: `/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00007/`
- Convenios urbanísticos: `/es/transparencia/indicadores-de-transparencia/indicador/Convenios-urbanisticos-del-Ayuntamiento-y-de-las-actuaciones-urbanisticas-en-ejecucion-00007/`
- Normativa gestión urbanística: `/es/transparencia/indicadores-de-transparencia/indicador/Normativa-vigente-en-materia-de-gestion-urbanistica-00007/`
- Agenda Urbana 2030: `/es/transparencia/indicadores-de-transparencia/indicador/Agenda-Urbana-La-Rinconada-2030/`

Galerías PDF en `/export/sites/larinconada/es/transparencia/.galleries/IND-53-/` (información pública BOP) e `IND-54-/` (convenios).

## Listado de expedientes / proyectos

- **Tablón sede**: filas HTML con documento, expediente, procedimiento, categoría, fecha. Procedimientos urbanísticos bajo «Actuaciones Urbanísticas». Preview en `/preview-document/{uuid}`.
- **Portal transparencia**: listado por indicadores con galerías de PDFs (convenios, avances PRI, reparcelaciones, BOP). Sin API JSON; scrape de enlaces `.pdf` en HTML.
- **Información pública**: decretos y avances publicados en BOP con enlaces a carpeta ciudadano (`carpeta.larinconada.es/GDCarpetaCiudadano/...`).
- **Consulta expedientes sede**: `/expedientes` requiere identificación; no hay listado público indexable.

## Licencias de obra

- No hay dataset público de licencias concedidas en el portal municipal.
- Trámites de licencia/comunicación previa en catálogo `/dossier` (presentación vía sede).
- Tablón puede publicar edictos de licencias puntuales (filtro por texto).
- No se encontró enlace LicytalPub Diputación Sevilla en web municipal (Tomares usa portal provincial; La Rinconada no expone CIF en web).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - SITUA / SituaDIFusión Junta de Andalucía: https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf — planeamiento digitalizado (raster/escaneado), consulta por municipio.
  - PGOU ZIP municipal (`pgou-la-rinconada.zip`) — planos/cartografía descargable, no API.
  - `urbanolarinconada.com` — visor urbanístico municipal referenciado en web pero **inaccesible** desde agente (Cloudflare 403).
- **Estrategia:** documentar SITUA como referencia PGOU; no hay WFS/ArcGIS público enlazable por código de expediente. El orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** sin polígonos por expediente en portal; carpeta ciudadano y sede sin geometría; visor municipal bloqueado; SITUA no expone GeoJSON por sector vía API simple.

## Limitaciones

- Certificado SSL sede electrónica con cadena incompleta → `insecure_ssl: true`.
- `urbanolarinconada.com` bloqueado por Cloudflare.
- Transparencia sede tiene pocas carpetas urbanismo indexadas (principal fuente: portal transparencia Dipusevilla).
- Licencias históricas no publicadas en listado abierto.

## Referencias de adapter

- Patrón tablón espublico: `municipio/adapters/tomares.py`
- Patrón transparencia OpenCMS Dipusevilla: `municipio/adapters/almensilla.py`
