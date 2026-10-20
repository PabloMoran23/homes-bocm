# Cáceres — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web corporativa | https://www.ayto-caceres.es |
| Sede electrónica (STA / T-Systems) | https://sede.caceres.es |
| Tablón electrónico (STA) | `PAGE_CODE=PTS2_TABLON` — requiere `KEY=all` para dataset embebido |
| Catálogo trámites | `PAGE_CODE=CATALOGO` — dataset `CATSERV`, urbanismo `PTS_PC_012` |
| Comunicación previa obras | `PAGE_CODE=PTS2_CPO` |
| Plan General Municipal (web) | https://www.ayto-caceres.es/ayuntamiento/plan-general-municipal/ |
| Tablón (enlace web) | https://www.ayto-caceres.es/ayuntamiento/tablon-de-anuncios-y-edictos-electronicos/ |
| SIG / planeamiento | https://sig.caceres.es/planea/planeamiento_web.php |
| Instrumentos vigentes (HTML) | `planeamiento_actual.php?tipo=30|31|40|41|50` |
| Visor por instrumento | `https://sig.caceres.es/serweb/planea/?cx=…&cy=…&iden=<id_tabla_p>` |
| Open Data / IDE | http://ide.caceres.es (GeoServer `PGM2010`) |

**Nota DNS:** `www.aytocaceres.es` no resuelve en este entorno; el dominio operativo es `www.ayto-caceres.es`.

## Listado de expedientes / proyectos

1. **Tablón STA (`PTS2_TABLON`, `KEY=all`)** — JSON embebido `dataset_PTS2_TABLON` (~215 filas). Campos: `descriptionProc`, `remitent.description`, `pubDateIni`, `dboid`, `externString`. Sin paginación AJAX en modo `KEY=all`.
2. **SIG `planeamiento_actual.php`** — tablas HTML por tipo de instrumento (PP, EDU, exposición pública, etc.) con expediente, denominación, situación, PDFs y enlace al visor (`iden`).
3. **PGM en web** — PDFs de modificaciones del PGM en `wp-content/uploads/` y documentos históricos en `sig.caceres.es/planes_publico/`.
4. **Catálogo sede** — trámites de urbanismo/licencias (informativos, no concesiones).

## Licencias de obra

- No hay dataset abierto de concesiones con dirección/coords.
- **Tablón:** anuncios puntuales si mencionan licencia/obra (filtro textual).
- **Catálogo:** trámites «Licencia de Obra Mayor», «Comunicación Previa de Obra Menor», etc. (páginas de tramitación).
- **Comunicación previa:** formulario `PTS2_CPO` en sede.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor Leaflet SIG: capa WMS `PGM2010:alteraciones_plan` en `ide.caceres.es/geoserver` con `CQL_FILTER=id_tabla_p=<iden>` (mismo `iden` que enlaces `serweb/planea`).
  - WFS: `PGM2010:alteraciones_plan`, filtro `id_tabla_p`, `EPSG:4326`, `outputFormat=application/json`.
  - Centro aproximado del visor: parámetros `cx`/`cy` en URL del mapa (punto, no polígono).
- **Estrategia adapter:** al parsear instrumentos SIG, guardar `iden` y consultar WFS; si falla, usar `lat`/`lon` del enlace al visor.
- **Limitaciones:**
  - `sig.caceres.es` e `ide.caceres.es` usan certificados que requieren `sig_insecure_ssl` en el agente.
  - `ide.caceres.es` puede no ser alcanzable desde algunos entornos cloud (timeout); el orquestador aplicará centroide municipal + jitter si no hay polígono.
  - Tablón y licencias no enlazan geometría por expediente.

## Limitaciones generales

- Tablón mezcla asuntos no urbanísticos (empleo, tributos); filtro por remitente «URBANISMO» y regex.
- `KEY=all` en tablón tarda ~25 s.
- Exposición pública (`tipo=50`) puede devolver «sin resultados» según momento.
