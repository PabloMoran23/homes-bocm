# El Vendrell — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal (Joomla) | https://www.elvendrell.net |
| Edictes urbanisme | https://www.elvendrell.net/ajuntament/edictes/urbanisme |
| RSS edictes | https://www.elvendrell.net/ajuntament/edictes/urbanisme?format=feed&type=rss |
| RSS notícies | https://www.elvendrell.net/?format=feed&type=rss |
| Urbanisme (tema) | https://www.elvendrell.net/informacio-cid-720 |
| Planejament derivat / PGOU | https://www.elvendrell.net/ajuntament/ordenances/ordenances-urbanistiques/ |
| Tràmits obres | https://www.elvendrell.net/res-cerca-tramits-gestions/161-obres |
| Seu electrònica | https://seu-e.cat/ca/web/elvendrell |
| Documentació urbanisme (PDF) | https://docs.elvendrell.net/docs/ajuntament/urbanisme/ |
| Visor GIS municipal | https://www.elvendrell.net/visor-gis?t=101&cc=1 |
| RPUC (expedients) | https://dtes.gencat.cat/rpucportal/...&municipiSel=43123 |
| MUC visor | https://ptop.gencat.cat/muc-visor/...&municipi=43123 |

## Proyectos / expedientes

- **Listado principal:** categoría Joomla `/ajuntament/edictes/urbanisme` con enlaces a artículo + PDFs en `docs.elvendrell.net` codificados como `GURB##########`.
- **Formato:** HTML + RSS 2.0; documentos en PDF (edicto, projecte, plànols).
- **Noticias:** RSS global con actuaciones de planeamiento (modificaciones PGOU, sectores, etc.).
- **No hay** listado scrapeable de expedientes en curso en la sede (seu-e es transparencia/trámites, no tablón de concesiones).

## Licencias

- **No** se publica tablón de licencias concedidas.
- Trámites informativos en `/res-cerca-tramits-gestions/161-obres` (llicències majors/menors, parcelació, etc.) y presentación en seu-e.
- Portal auxiliar `urbanisme.elvendrell.net` enlazado para actuaciones sujetas a licencia (gestión, no listado histórico).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Visor `visor-gis` (OpenLayers + `mpgis.js`): capas de mobilitat y punts d'interès; datos vía POST Joomla Jumi, sin enlace a expediente/GURB.
  - MUC/RPUC Generalitat (43123): visor humano; servicios ArcGIS/WFS de `geoserveis.dtes.gencat.cat` no accesibles de forma fiable desde el entorno del agente para join automático.
  - PDFs de planeamiento con planos raster, sin GeoJSON/WFS municipal enlazado al código GURB.
- **Estrategia adapter:** metadatos + URLs; el orquestador usará `centroid` del manifest + jitter.
- **Limitaciones:** sin polígono por expediente en fuente pública machine-readable.

## Limitaciones generales

- Licencias: solo páginas de trámite, `min_rows` informativo.
- e-Tauler mencionado en noticias pero anuncios urbanísticos efectivos en web Joomla.
- Código INE / MUC: **43123** (Tarragona).
