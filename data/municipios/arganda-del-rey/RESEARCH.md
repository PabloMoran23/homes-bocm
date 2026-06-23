# Arganda del Rey — investigación portal ayuntamiento

**Municipio:** Arganda del Rey (Comunidad de Madrid)  
**Fecha:** 2026-06-23  
**BOCM regional (referencia):** 29 avisos

## Resumen

Arganda del Rey publica planeamiento y urbanismo en tres capas: web corporativa WordPress, sede electrónica STA (tablón y planeamiento) y portal de datos abiertos CKAN con capas GeoJSON del PGOU.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://www.argandadelrey.es/servicios-cpt/urbanismo/` | WordPress + PDFs | Proyectos (PGOU, instrumentos IP, PDFs) |
| Instrumentos en exposición | `.../instrumentos-urbanisticos-en-exposicion-publica/` | WP enlaces | PE.UE024, ED.UE107 |
| Avance PGOU 2023 | `.../avance-2023-para-nuevo-plan-general/` | WP + PDFs | Documentos informativo/normativo/ambiental |
| Sede STA tablón | `https://sedeelectronica.argandadelrey.es/sta/...PAGE_CODE=PTS2_TABLON` | HTML + JSON embebido | Licencias y proyectos del tablón |
| Sede planeamiento | `...PAGE_CODE=PTS2_PLANEA` | HTML + JSON embebido | Convenios/planeamiento sede |
| Datos abiertos convenios | `datosabiertos.ayto-arganda.es` (CKAN JSON) | JSON | 35 convenios urbanísticos históricos |
| Datos abiertos PGOU UE | CKAN GeoJSON `map-8.geojson` | GeoJSON (129 polígonos) | Geometría por código UE |
| Geoportal municipal | `https://geoportal.ayto-arganda.es/` | ArcGIS (EntradaAvisos) | Referencia; bloqueado desde algunos entornos |

## Fuentes detalladas

### 1. Web corporativa WordPress

- **Base:** `https://www.argandadelrey.es`
- **Urbanismo (parent 3568):** páginas hijas descubiertas vía REST API `/wp-json/wp/v2/pages?parent=3568`
- **Instrumentos en exposición pública:** PE.UE024 (Plan Especial Equipamientos), ED.UE107 (Estudio de detalle Manzana 16)
- **Avance PGOU 2023:** subpáginas documento informativo/normativo/ambiental con decenas de PDFs
- **Preavance 2021** y **Plan General vigente** con documentación histórica

### 2. Sede electrónica STA

- **Base:** `https://sedeelectronica.argandadelrey.es`
- **Tablón:** `PTS2_TABLON` — dataset JSON embebido `dataset_PTS2_TABLON` (patrón Getafe)
- **Planeamiento:** `PTS2_PLANEA` — dataset `dataset_PTS2_PLANEA`
- **Catálogo trámites:** `PAGE_CODE=CATALOGO` — trámites informativos de licencias/urbanismo
- **Limitación:** desde entornos cloud automatizados la sede puede responder con TCP reset; el adapter usa fallback WordPress + CKAN

### 3. Datos abiertos CKAN

- **API:** `https://datosabiertos.ayto-arganda.es/api/3/action/package_search`
- **Convenios urbanísticos 1995-2011:** JSON con campos `Objeto`, `Organismo`, `Fecha`, `Pdf`
- **PGOU Unidades de ejecución:** GeoJSON con propiedades `UE`, `NOMBRE`, `ORDENACION`, `TIPO`, `ESTADO` (WGS84)
- **Expedientes disciplina urbanística 1980-2004:** CSV/JSON (histórico, no enlazado a geometría por expediente)

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - GeoJSON CKAN: `Plan General de Ordenación Urbana. Unidades de ejecución. Mapa` (129 polígonos, EPSG:4326)
  - Geoportal: `https://geoportal.ayto-arganda.es/EntradaAvisos` (ArcGIS; no accesible desde CI por reset TLS)
- **Estrategia:** extraer códigos UE del título (`PE.UE024` → `UE-24`, `ED.UE107` → `UE-107`) y cruzar con el índice GeoJSON; rellenar `geom_geojson`, `geometry_source=portal_geojson`, centroide en `lat`/`lon`
- **Limitaciones:**
  - Solo proyectos con código UE explícito en título/convenio reciben polígono
  - Tablón/PDF sin código UE no tienen geometría enlazable
  - Visor ArcGIS en vivo no scrapeable desde este entorno (centroide municipio + jitter vía orquestador)

## Licencias

- No hay dataset abierto de concesiones con coordenadas.
- Anuncios de licencia en tablón sede cuando se publican (si accesible).
- Trámites informativos: catálogo sede + páginas ITE/ordenanzas urbanísticas en web.

## Limitaciones

| Limitación | Impacto |
|------------|---------|
| Sede/geoportal TCP reset en CI | Tablón sede puede quedar vacío; WordPress + CKAN cubren proyectos |
| PDFs sin código UE | Sin `geom_geojson`; geocode aplicará jitter |
| Convenios históricos (1995-2011) | Fechas antiguas; útiles como proyectos de referencia |
| Licencias sin listado público geo | `licencias.jsonl` partial (trámites informativos) |

## Estrategia de ingesta

- **proyectos.jsonl:** WordPress urbanismo + convenios CKAN + tablón/planeamiento sede + enriquecimiento GeoJSON UE
- **licencias.jsonl:** tablón (filtro licencia) + trámites informativos web/sede
- **IDs:** `arganda-del-rey-{lic|proy}-{sha256[:14]}`
- **source:** `ayuntamiento`

## Paridad esperada

- `proyectos`: ok (PGOU, instrumentos IP, convenios, PDFs)
- `licencias`: partial (trámites informativos; sin concesiones geo públicas)
- `with_geometry`: >0 para instrumentos PE/ED y convenios con código UE
