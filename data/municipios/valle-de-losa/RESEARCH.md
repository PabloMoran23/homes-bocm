# Valle de Losa — investigación portal ayuntamiento

**Municipio:** Valle de Losa (`valle-de-losa`)  
**Comunidad:** Castilla y León (`castilla-y-leon`)  
**Provincia:** Burgos (INE `09008`)  
**Boletín:** BOCYL (`bocyl`, 2 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Web municipal | https://www.valledelosa.es | Drupal 10 (tema Toools) | Información general, enlace a PLAU |
| Sede electrónica | https://valledelosa.sedelectronica.es | espublico gestiona | Tablón, trámites, transparencia |
| Tablón anuncios | `/board` | HTML tabla + `preview-document/{uuid}` | Anuncios planeamiento (NUM, etc.) |
| Catálogo trámites | `/dossier` | espublico catálogo | Trámites licencia/urbanismo (requiere sesión) |
| Transparencia | `/transparency` | Wicket | Sección 7 «Urbanismo» vacía (0 docs) |
| PlanPublica PLAU | `searchVPubDocMuniPlau.do?provincia=9&municipio=908` | JSP tabla HTML | 9 instrumentos aprobados |
| PlanPublica PLAI | `searchVPubDocMuniPlai.do?provincia=9&municipio=908` | JSP | Sin documentos activos (sep 2026) |
| SiUR visor | https://idecyl.jcyl.es/siur/index.html?id=09008 | Mapa JCyL | Visor regional de planeamiento |

## Cómo se listan expedientes

- **Tablón `/board`:** tabla con documento, expediente, procedimiento, categoría, descripción, fecha. Enlaces relativos `preview-document/{uuid}`.
- **PlanPublica (PLAU):** tabla `#listado` con tipo (PU/NUM/PP/ED…), fechas y `openDocumento.do?cDocId={id}`.
- **Web Drupal:** redirige planeamiento a PLAU JCyL; noticias sin expedientes urbanísticos recientes.

## Cómo se publican licencias

- No hay listado público de concesiones de licencia de obra georreferenciadas.
- Tablón publica licencias de transporte (auto-taxi) pero no licencias urbanísticas de obra.
- Catálogo `/dossier` expone trámites informativos (licencia urbanística, comunicación previa, etc.).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (2), `plau_cyl_sectores` (6+)
  - Filtro efectivo: `CQL_FILTER=n_mun='Valle de Losa'` (`srsName=EPSG:4326`)
  - Nota: `c_mun='09008'` devuelve 0 features; usar nombre municipal.
- **Estrategia:** ingestión WFS con polígonos de sectores/planes; enriquecimiento PLAU/tablón por coincidencia de título o subtipo NUM.
- **Limitaciones:** WFS cubre ámbitos de planeamiento, no licencias puntuales ni expedientes de tablón sin sector. Sin visor municipal propio. `/dossier` requiere warm-up de sesión vía `/board`.

## Limitaciones

- Transparencia sección urbanismo vacía.
- `/info` puede ser lento; tablón `/board` es fiable.
- Licencias de obra solo como páginas de trámite, no concesiones publicadas.
- Sede requiere `insecure_ssl` en algunos entornos.

## Referencia de implementación

Patrón espublico + PLAU + WFS: `municipio/adapters/valverdon.py`, `municipio/adapters/arcos_de_la_llana.py`
