# Las Tres Villas, Macael, Cuevas del Almanzora y Vera — investigación portal ayuntamiento

**Entrada de cola compuesta:** cuatro municipios de Almería (Andalucía) agregados en un único registro BOJA.  
**Slug:** `las-tres-villas-macael-cuevas-del-almanzora-y-vera`  
**Boletín:** BOJA (`boja`, 1 entrada agregada en histórico)

| Municipio | INE | Web | Sede |
|-----------|-----|-----|------|
| Las Tres Villas | 04045 | https://www.lastresvillas.es | https://lastresvillas.sedelectronica.es |
| Macael | 04061 | https://www.macael.es | https://macael.sedelectronica.es |
| Cuevas del Almanzora | 04049 | https://www.cuevasdelalmanzora.es | https://sede.cuevasdelalmanzora.es |
| Vera | 04102 | https://www.vera.es | https://vera.sedelectronica.es |

> **Nota:** Vera tiene adapter propio (`vera`) en cola separada. Esta entrada compuesta refleja un artículo BOJA que mencionó los cuatro municipios.

## URLs base y páginas semilla

### Las Tres Villas

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.lastresvillas.es | **Timeout CI** — CMS Diputación Almería (Lotus Domino/cmsdipro) |
| Sede electrónica | https://lastresvillas.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://lastresvillas.sedelectronica.es/board/ | **Operativa** — ~2 anuncios vigentes (sep 2026) |
| Tablón DipAlmería | https://www.lastresvillas.es/Servicios/cmsdipro/index.nsf/tablon_view.xsp?p=LasTresVillas | **Timeout CI** — portal provincial |

### Macael

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.macael.es | **Timeout CI** |
| Sede electrónica | https://macael.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://macael.sedelectronica.es/board/ | **Operativa** — ~10 anuncios; licencias de ocupación fiestas |

### Cuevas del Almanzora

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.cuevasdelalmanzora.es | **Operativa** — Drupal/FluidUI |
| Sede electrónica | https://cuevasdelalmanzora.sedelectronica.es | **Inactiva** — página de selección de sede |
| Sede DipAlmería | https://sede.cuevasdelalmanzora.es | **Timeout CI** — cmsdipro tablón |
| Tablón DipAlmería | https://sede.cuevasdelalmanzora.es/Servicios/cmsdipro/index.nsf/tablon_view_categoria123.xsp?p=SedeCuevasdelAlmanzora | **Timeout CI** |

### Vera

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.vera.es | **Operativa** — CMS propio |
| Sede electrónica | https://vera.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://vera.sedelectronica.es/board/ | **Operativa** — ~10 anuncios |
| Ordenanzas | https://www.vera.es/ayuntamiento/index.php?page=ordenanzas | **Operativa** — PDFs normativa urbanística |
| Geoportal | https://qgis.vera.es | Inventario municipal (sin planeamiento enlazable) |

## Cómo se listan expedientes

- **Las Tres Villas / Macael / Vera:** tablón espublico gestiona (tabla HTML Wicket, `preview-document/{uuid}`). Sin paginación amplia en primera página.
- **Cuevas del Almanzora:** tablón provincial cmsdipro (Lotus Domino XSP) enlazado desde web Drupal; sede espublico inactiva.
- **Planeamiento regional:** SITUA/Difusión Junta de Andalucía (`search.jsf`) para consulta PGOU por municipio.

## Licencias de obra

- No hay dataset histórico público de concesiones con coordenadas en ninguno de los cuatro municipios.
- Macael publica pliegos de licencias de ocupación (fiestas) en tablón sede.
- Trámites de solicitud vía sede (`/dossier`); consulta de expedientes requiere identificación.
- Adapter incluye páginas informativas de tablón, trámites y SITUA por municipio.

## Proyectos / planeamiento

- **Tablones sede:** edictos, ordenanzas, licencias de ocupación, disposiciones normativas.
- **Vera:** ordenanzas urbanísticas (Normas Urbanísticas, OMD, protección espacio urbano) en PDF.
- **WFS Diputación:** sectores/ámbitos urbanísticos por `cod_ine` (6 LTV, 0 Macael, 25 Cuevas, 33 Vera).
- **SITUA:** planeamiento general aprobado a nivel regional.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Diputación Almería: `https://app.dipalme.org/geoserver/urbanismo/ows`
  - Capa: `urbanismo:v_siu_ambitos_o_sectores` (`CQL_FILTER=cod_ine='XXXXX'`, `outputFormat=application/json`, `srsName=EPSG:4326`)
  - Visor GIS: `https://app.dipalme.org/visor-gis/`
  - SITUA Junta de Andalucía: planeamiento aprobado (sin geometría por expediente)
- **Estrategia:** descargar sectores WFS por INE; emparejar por código sector en títulos de tablón cuando sea posible; filas WFS como proyectos con polígono.
- **Limitaciones:**
  - Macael: 0 sectores en WFS Diputación (geometry unavailable para este municipio).
  - Tablones espublico: solo primera página HTML.
  - `www.lastresvillas.es` y `www.macael.es` timeout en CI (sede accesible).
  - Cuevas sede cmsdipro timeout en CI.
  - Sin enlace expediente-tabla → geometría en filas de tablón es rara.

## Adapter implementado

- `municipio.adapters.las_tres_villas_macael_cuevas_del_almanzora_y_vera:LasTresVillasMacaelCuevasDelAlmanzoraYVeraAyuntamientoAdapter`
- Fuentes: tablón espublico (LTV, Macael, Vera) + ordenanzas Vera + WFS Diputación sectores + SITUA + páginas informativas trámites.
