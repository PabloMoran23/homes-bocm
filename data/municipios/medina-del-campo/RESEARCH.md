# Medina del Campo — investigación portal ayuntamiento

**Municipio:** Medina del Campo (`medina-del-campo`)  
**Comunidad:** Castilla y León (`castilla-y-leon`)  
**Boletín:** BOCYL (`bocyl`, 9 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Sede electrónica | https://sede.medinadelcampo.es | STA (T-Systems/TAO) | Tablón, catálogo trámites, expedientes |
| Tablón anuncios | `.../doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON&KEY=all` | HTML + JSON embebido `dataset_PTS2_TABLON` | Anuncios publicados (~18 filas visibles) |
| Catálogo trámites | `.../doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO` | JSON embebido `dataset_CATSERV` | Trámites urbanismo (keyword `PTS_PC_012`, 34 trámites) |
| Portal web (referencia) | http://www.ayto-medinadelcampo.es/ | — | Enlazado desde cabecera sede; **inaccesible** desde red del agente (timeout) |
| PLAI JCYL | https://servicios.jcyl.es/PlanPublica/ | HTML | Sin documentos indexados para este municipio en pruebas |

## Cómo se listan expedientes

- **Tablón STA:** variable JavaScript `var dataset_PTS2_TABLON = [...]` en el HTML inicial. Campos: `descriptionProc`, `externString` (código/expediente), `pubDateIni`, `remitent.description`, `dboid`.
- **Remitentes urbanismo:** p. ej. «Servicio de Urbanismo» / anuncios con «finca urbana», «rectificación de cabida», exposición pública.
- **Catálogo:** 34 trámites con keyword `PTS_PC_012` (Urbanismo y vivienda): aprobación PGOU/planes parciales, licencias, declaraciones responsables, convenios, etc. Páginas informativas sin dataset de concesiones.

## Cómo se publican licencias

- No hay listado tabular público de licencias concedidas con dirección/coordenadas.
- El tablón publica ocasionalmente anuncios relacionados con obras/instalaciones (p. ej. autorización eléctrica con referencia municipal).
- El catálogo STA expone trámites (`Licencia urbanística (obra)`, `Licencia de obra menor`, `Declaración responsable de uso del suelo`, etc.) — el adapter los incluye como filas informativas (patrón Aranda/Pozuelo).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — filtro `n_mun='Medina del Campo'`, campo sector `n_num_sect` (p. ej. `SUR-D S30`, sectores PGOU).
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — planes parciales municipales (mismo filtro `n_mun`).
  - No se encontró visor ArcGIS municipal ni enlace expediente→polígono en la sede STA.
- **Estrategia:** si el título del expediente incluye código de sector (`SUR-D S30`, `SU-NC`, etc.), consultar WFS SIUCyL y rellenar `geom_geojson` + centroide.
- **Limitaciones:**
  - Portal web municipal inaccesible; sin transparencia/PGOU scrapeable.
  - Tablón con pocos anuncios de urbanismo; mayoría de filas son trámites informativos del catálogo.
  - WFS aporta polígonos de sector PGOU, no del expediente individual ni de licencias de obra.
  - PLAI JCYL sin resultados verificados para Medina del Campo.

## Limitaciones

- Tablón mezcla tráfico, tributos, subvenciones y urbanismo; filtrado por remitente + regex.
- Sin API de licencias concedidas; catálogo aporta trámites informativos.
- Portal `ayto-medinadelcampo.es` no responde en el entorno de scraping (documentado; sede es la fuente operativa).

## Referencia de implementación

Patrón STA tablón + catálogo: `municipio/adapters/aranda_de_duero.py`  
Geometría WFS SIUCyL: `municipio/adapters/salamanca.py`
