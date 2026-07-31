# Aranda de Duero — investigación portal ayuntamiento

**Municipio:** Aranda de Duero (`aranda-de-duero`)  
**Comunidad:** Castilla y León (`castilla-y-leon`)  
**Boletín:** BOCYL (`bocyl`, 17 entradas históricas)

## URLs base y páginas semilla

| Fuente | URL | Formato | Uso |
|--------|-----|---------|-----|
| Web municipal | https://www.arandadeduero.es | WordPress | Portal general; enlaces a sede y transparencia |
| Sede electrónica | https://sede.arandadeduero.es | STA (CATSERV) | Tablón, catálogo trámites, expedientes |
| Tablón anuncios | `.../doEvent?APP_CODE=STA&PAGE_CODE=PTS2_TABLON` | HTML + JSON embebido `dataset_PTS2_TABLON` | Licencias y proyectos publicados |
| Catálogo trámites | `.../doEvent?APP_CODE=STA&PAGE_CODE=CATALOGO` | JSON embebido `dataset_CATSERV` | Trámites urbanismo (keyword `PTS_PC_012`) |
| Transparencia urbanismo | https://transparencia.arandadeduero.es/obras-publicas-y-urbanismo/ | WordPress | PGOU, convenios, obras |
| PGOU 2023 | `.../plan-general-de-ordenacion-urbana/` | PDFs (Tomos I–VII) | Planeamiento vigente |
| Convenios urbanísticos | `.../convenios-urbanisticos/` | PDF certificado | Convenios |

## Cómo se listan expedientes

- **Tablón STA:** variable JavaScript `var dataset_PTS2_TABLON = [...]` en el HTML inicial (~188 filas visibles). Campos: `descriptionProc`, `externString` (expediente), `pubDateIni`, `remitent.description`, `dboid`.
- **Remitente urbanismo:** `OBRAS URBANISMO Y SERVICIOS` concentra anuncios de planeamiento, enajenación de suelo, exposición pública de proyectos de urbanización (p. ej. UE 33 San Isidro II).
- **Catálogo:** 91 trámites con keyword `PTS_PC_012` (Urbanismo y vivienda); incluye licencias, declaraciones responsables, aprobaciones de urbanización, etc. Sin dataset de concesiones publicadas.

## Cómo se publican licencias

- No hay listado tabular de licencias concedidas en transparencia.
- El tablón publica ocasionalmente anuncios de información pública de licencias (p. ej. licencia de obras en suelo rústico).
- El catálogo STA expone páginas informativas de trámites (`Licencia urbanistica de obras`, `Declaración responsable de obras`, etc.) — el adapter las incluye como filas informativas (patrón Parla/Pozuelo).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Transparencia menciona «Visor de geo-referenciación catastral» en `obras-publicas-y-urbanismo/seguimiento-y-control-de-la-ejecucion-de-obras/visor-de-geo-referenciacion-catastral/` — la página no expone iframe ArcGIS, WFS ni API pública (contenido vacío / placeholder).
  - PGOU en transparencia: solo PDFs de planos, sin servicio GIS consultable por expediente.
  - Sede STA: metadatos de tablón sin geometría ni enlace a visor.
- **Estrategia:** sin fuente GIS enlazable a expedientes; el orquestador aplicará centroide municipal + jitter.
- **Limitaciones:** visor catastral no operativo públicamente; datos de ámbito solo en PDFs del PGOU.

## Limitaciones

- Tablón mezcla anuncios de personal, tributos y urbanismo; filtrado por remitente + regex.
- Sin API de licencias concedidas; catálogo aporta trámites informativos.
- PGOU PDFs son documentos normativos, no expedientes puntuales con fecha de trámite.
- Sede STA puede requerer `sede_insecure_ssl` en algunos entornos (certificado intermedio).

## Referencia de implementación

Patrón STA tablón: `municipio/adapters/getafe.py`, `fuenlabrada.py`  
Catálogo CATSERV: `municipio/adapters/parla.py`
