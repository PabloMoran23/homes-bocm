# Cebreros — investigación portal ayuntamiento

**Municipio:** Cebreros (Castilla y León, Ávila)  
**Fecha:** 2026-08-27

## URLs base y páginas semilla

| Fuente | URL | Contenido |
|--------|-----|-----------|
| Web corporativa (Ziddea) | https://www.cebreros.es | Portal activo (CMS custom Ziddea Diseño Web Ávila) |
| Urbanismo | https://www.cebreros.es/ayuntamiento/urbanismo | Enlace al archivo PlanPublica JCyl |
| Anuncios y bandos | https://www.cebreros.es/ayuntamiento/anuncios-y-bandos | Bandos y convocatorias (pocas urbanísticas) |
| Noticias | https://www.cebreros.es/noticias | Noticias municipales (sin urbanismo activo relevante) |
| PlanPublica PLAU (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=057 | ~14 instrumentos (NUM, PERI, PAU, ED, PORN) |
| PlanPublica PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=05&municipio=057 | Planeamiento en exposición pública |
| Sede electrónica (espublico gestiona) | https://cebreros.sedelectronica.es/board | Tablón de anuncios (~4 filas visibles) |
| Catálogo trámites | https://cebreros.sedelectronica.es/dossier | Trámites sede (respuesta lenta >50s en CI) |

## Cómo se listan expedientes

- **Web Ziddea:** página urbanismo con enlace externo a PlanPublica JCyl; sin PDFs locales ni visor propio.
- **PlanPublica:** tabla HTML con columnas Libro, Instrumento, Fecha publicación, Fecha acuerdo, Título; enlaces `openDocuIndice.do?cDocId=…`.
- **Tablón sede:** HTML tabla espublico con `preview-document`. Columnas: documento, expediente, procedimiento, categoría, descripción, fecha. Actualmente mayoría anuncios fiscales/contratación.
- **Sin visor de expedientes** ni API JSON de listado histórico en sede.
- **BOCYL:** publicaciones referenciadas en instrumentos PlanPublica (`f_bocyl` en WFS).

## Cómo se publican licencias

- No hay dataset histórico de concesiones de licencia de obra.
- Tablón actual sin licencias urbanísticas individuales.
- Trámites en sede `/dossier` (acceso lento); sin listado scrapeable de concesiones.
- Estrategia adapter: páginas informativas de trámites (urbanismo, tablón, dossier) + tablón si aparece licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `c_mun = '05057'` (Cebreros, Ávila)
  - 1 instrumento NUM + 39 sectores + 2 planes parciales con polígono
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas PlanPublica/tablón por coincidencia de nombre de sector o código en título.
- **Limitaciones:**
  - Sin visor ArcGIS municipal ni enlace expediente→geometría.
  - Licencias de obra sin georreferencia.
  - Tablón sede solo muestra anuncios recientes.
  - `/dossier` muy lento en CI.
  - Geometría WFS solo para ámbitos PLAU CyL, no para licencias individuales.

## Limitaciones generales

- Sede `/info` redirige pero responde vacío/lento; tablón `/board` accesible con `insecure_ssl`.
- Municipio pequeño (~4.500 hab.); volumen bajo de publicaciones urbanísticas activas.
- Boletín regional: BOCYL (`boletin_source_id: bocyl`, 2 entradas en CSV).
