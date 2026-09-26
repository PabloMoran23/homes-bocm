# Mucientes — investigación portal ayuntamiento

## Fuentes

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web municipal | https://www.mucientes.es | WordPress Divi; noticias y enlace al archivo de planeamiento |
| Archivo planeamiento (WP) | https://www.mucientes.es/archivo-de-planeamiento-urbanistico-y-ordenacion-del-territorio-de-mucientes/ | Redirige al recurso PlanPublica JCyL |
| Sede electrónica | https://mucientes.sedelectronica.es | espublico gestiona (ehome) |
| Tablón de anuncios | https://mucientes.sedelectronica.es/board/ | Tabla HTML con `preview-document` (convocatorias, REVAL, exposiciones) |
| Trámites | https://mucientes.sedelectronica.es/dossier | Catálogo de trámites (Urbanismo y Vivienda); respuesta lenta |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=098 | Documentos de planeamiento del municipio |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=098 | Información pública instrumentos |
| Agenda urbana | https://agendaurbana.ayuntamientomucientes.es | Plan de acción local (no expedientes) |

## Listado de expedientes / proyectos

- **Principal:** tabla HTML en PlanPublica (`searchVPubDocMuniPlau` / `searchVPubDocMuniPlai`) con filas `<tr>` y enlaces `openDocumento.do?cDocId=…`.
- **Complemento:** tablón espublico (6 columnas: documento, expediente, procedimiento, categoría, descripción, fecha).
- **No hay** visor municipal propio ni API JSON de expedientes en la sede.

## Licencias

- No se publican concesiones de licencia de obra en el tablón (solo tributos, plenos, etc.).
- Trámites de licencia urbanística accesibles vía catálogo `/dossier` (sin listado de concesiones).
- El adapter devuelve páginas de trámite del catálogo cuando existen + filas del tablón que coincidan con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `n_mun = 'Mucientes'` (c_mun `47098`)
  - ~5 sectores con polígono en WFS
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas PLAU/tablón con `_attach_geometry` buscando códigos de sector en el texto.
- **Limitaciones:** tablón sin coordenadas; licencias sin GIS; `/dossier` muy lento; no hay visor ArcGIS municipal.

## Limitaciones generales

- Certificado SSL de la sede válido; `insecure_ssl` desactivado por defecto en manifest (adapter permite override).
- Paginación del tablón limitada a la página principal en el scrape actual.
