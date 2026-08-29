# La Cistérniga — investigación portal ayuntamiento

**Municipio:** La Cistérniga (Valladolid, Castilla y León)  
**INE:** 47114  
**Fecha:** 2026-08-29  
**BOCYL regional (referencia):** 2 avisos

## Resumen

La Cistérniga combina web corporativa **Drupal 9** (`www.lacisterniga.es`, tema mipueblo) con sede electrónica **espublico gestiona**
(`cisterniga.sedelectronica.es`). El planeamiento histórico está en **PLAI JCYL** (municipio 114, provincia 47) y la cartografía
sectorial en **IDECyL WFS** (`n_mun = 'Cistérniga'`).

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Web municipal | `https://www.lacisterniga.es` | Drupal 9 mipueblo | Urbanismo, documentación descargable |
| Urbanismo | `https://www.lacisterniga.es/urbanismo` | HTML taxonomy | Sección urbanismo (RSS vacío) |
| Documentación urbanismo | `https://www.lacisterniga.es/documentacion?field_category_target_id=75` | Drupal view + PDFs | Planes parciales, IP, proyectos de actuación, formularios licencia |
| Tablón sede | `https://cisterniga.sedelectronica.es/board` | HTML Wicket | Edictos urbanismo (estudio detalle sector 6, PA sector 10, etc.) |
| Trámites sede | `https://cisterniga.sedelectronica.es/dossier` | HTML Wicket | Catálogo trámites (`/catalog/t/{uuid}`) |
| PLAI JCYL | `servicios.jcyl.es/PlanPublica` (mun. 114, prov. 47) | HTML tabla | PGOU, planes parciales, PERI, modificaciones históricas |
| IDECyL WFS | `idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | 8 sectores urbanizables (Sector 5–14, industrial Mora) |
| Sede expedientes | `https://cisterniga.sedelectronica.es/expedientes` | Portal ciudadano | Consulta de expedientes (sin API pública scrapeable) |

## Tablón de anuncios (`/board`)

Tabla Wicket con columnas: documento, expediente, procedimiento, categoría, descripción, fecha.
Enlaces `preview-document/{uuid}` a PDF. Muestra actual (~ago 2026):

- Expediente **932/2024** — Aprobación definitiva Proyecto de Actuación Sector 10
- Expediente **48/2025** — Aprobación inicial estudio de detalle parcela 9 sector 6 (información pública)
- Expediente **1778/2025** — Declaración de ruina (documentado en Drupal)

## Drupal — documentación urbanismo

Vista `/documentacion` filtrada por categoría Urbanismo (`field_category_target_id=75`). Títulos en `views-field-title`, PDFs en `/sites/default/files/documents/`.

Contenido relevante:

- Aprobación inicial PA Plan Parcial modificado Sector 10 (exp. 932/2024)
- Aprobación definitiva Plan Parcial Sector 13 SUD PGOU
- Proyecto urbanístico parques Plaza Junquera y Avda. Velázquez
- Información pública ruina (1778/2025)
- Formularios: primera ocupación, licencia cementerio, planos clasificación suelo

## PLAI JCYL

Código municipio PLAI: **114** (provincia 47, INE 47114). Documentos históricos incluyen:

- PP Sector Industrial nº7, Sector 8 «PROTOS»
- Modificaciones PGOU (sectores industriales SANTIVERI, UE-18/19)
- PERI nº1 C/ Arenillas
- Proyectos de actuación sector SUNC-20

## Licencias

No hay visor georreferenciado municipal de concesiones de obra (sin paridad Madrid DROUS).

- Tablón sede publica edictos urbanísticos pero no concesiones de licencia de obra rutinarias
- Drupal documentación incluye formularios «Solicitud Primera Ocupación», «Licencia Cementerio»
- Catálogo sede aporta trámites informativos de licencias

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_sectores` — 8 polígonos (Sectores 5–14, ampliación industrial La Mora)
  - WFS `urbanismo:plau_cyl_planes_parciales` — planes parciales
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — ámbito instrumento
  - Filtro: `n_mun = 'Cistérniga'`, `outputFormat=application/json`, `srsName=EPSG:4326`
  - Visor SIUCyL: `https://idecyl.jcyl.es/siur/` (sin enlace directo a expediente)
  - Diputación Valladolid LocalGIS/IDEVALL — visores cartográficos sin API pública por expediente
- **Estrategia:** ingestar capas WFS como proyectos con `geom_geojson`; enriquecer filas tablón/Drupal/PLAI
  por coincidencia de número de sector en título (SECTOR 10, SECTOR 13, sector 6, etc.)
- **Limitaciones:**
  - No hay geometría por expediente individual de licencia o estudio de detalle parcela
  - WFS solo cubre sectores del planeamiento, no ámbitos de expedientes concretos
  - PLAI no expone coordenadas; solo PDF/BOCYL
  - No hay visor urbanístico municipal propio con query REST

## Limitaciones generales

- Dossier sede puede tardar en CI (CookieJar + `insecure_ssl`)
- Drupal RSS urbanismo vacío; documentación vía vista HTML
- Expedientes sede requieren autenticación para detalle completo
