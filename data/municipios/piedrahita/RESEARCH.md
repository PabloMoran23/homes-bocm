# Piedrahíta — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa | https://www.aytopiedrahita.com | WordPress Avada; tablón de anuncios con PDFs |
| Tablón web | https://www.aytopiedrahita.com/tablon-de-anuncios/ | Listado HTML de enlaces a `/wp-content/uploads/...pdf` |
| Sede electrónica | https://aytopiedrahita.sedelectronica.es | espublico gestiona: `/board`, `/dossier`, `/transparency` |
| Sede (no usar) | https://piedrahita.sedelectronica.es | Página «Sede Electrónica Indeterminada» (sin entidad asignada) |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlauPrint.do?provincia=05&municipio=180 | Documentos de planeamiento (tabla `doOpen`) |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=05&municipio=180 | Información pública planeamiento |
| SIUR JCyL | https://idecyl.jcyl.es/siur/index.html?id=05180 | Visor cartográfico municipal (INE 05180) |

## Expedientes / proyectos

- **Sede `/board`**: tabla HTML con `preview-document` (documento, expediente, procedimiento, categoría, fecha).
- **PlanPublica**: filas con `doOpen(docId, codigo)`; título en columnas de instrumento.
- **IDECyL WFS**: capas `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores` filtradas por `n_mun = 'Piedrahíta'`.
- **Tablón web**: PDFs sin metadatos estructurados; filtro por regex urbanismo/licencias.

## Licencias

- No hay dataset abierto de concesiones.
- Edictos de licencias pueden aparecer en sede `/board` (categoría urbanismo) o tablón web.
- Trámites informativos en `/dossier` y página de impresos.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/ows` — capas PLAU CyL, filtro `n_mun = 'Piedrahíta'`, `outputFormat=application/json`, `EPSG:4326`.
  - SIUR visor JCyL (referencia cartográfica; geometría vía WFS en adapter).
- **Estrategia:** ingestar polígonos WFS por municipio; enriquecer filas PlanPublica/tablón por coincidencia de título.
- **Limitaciones:** 1 instrumento de ámbito (NNSS) en WFS; sin visor ArcGIS municipal propio; licencias sin georreferencia en tablón.

## Limitaciones generales

- Subdominio `piedrahita.sedelectronica.es` no operativo; usar `aytopiedrahita.sedelectronica.es`.
- Tablón web mezcla personal, plenos y urbanismo; filtrado heurístico.
- PlanPublica lista «SIN PLANEAMIENTO GENERAL» como único documento PLAU visible en print.
