# El Álamo — investigación portal ayuntamiento

**Municipio:** El Álamo (Comunidad de Madrid)  
**Fecha:** 2026-08-02  
**BOCM regional (referencia):** 11 avisos

## Resumen

El Álamo publica urbanismo en web corporativa WordPress (`ayuntamientoelalamo.org`) con documentación extensa de planeamiento (PGOU, planes parciales, estudios) en PDF. La sede electrónica es Maggioli eAdmin (`elalamo.eadministracion.es`, SPA Angular) sin tablón de anuncios scrapeable. El planeamiento vigente y ámbitos de desarrollo se consultan en el Visor SIT de la Comunidad de Madrid.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://ayuntamientoelalamo.org/oficina-virtual/urbanismo/` | WordPress | PGOU normas + formularios |
| Concejalía urbanismo | `https://ayuntamientoelalamo.org/el-ayuntamiento/concejalias/urbanismo-y-obras/` | WordPress + PDFs | Proyectos/planeamiento (106+ PDFs) |
| Solicitudes | `https://ayuntamientoelalamo.org/solicitudes/` | WordPress + PDFs | Formularios licencias urbanísticas |
| Sede eAdmin | `https://elalamo.eadministracion.es/` | Maggioli SPA | Informativo (sin tablón API) |
| Visor SIT CM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/WFS | Ámbitos UA/SUR/SUI/AA con polígono |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Geometría ámbitos (`DS_MUNICIPIO='EL ÁLAMO'`) |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress)

- **URL:** `https://ayuntamientoelalamo.org/oficina-virtual/urbanismo/`
- **Contenido:** Normas urbanísticas PGOU (Doc III Vol 1), solicitudes generales y formulario urbanismo.
- **PDFs:** Normas subsidiarias, formularios de trámite.

### 2. Concejalía Urbanismo y Obras

- **URL:** `https://ayuntamientoelalamo.org/el-ayuntamiento/concejalias/urbanismo-y-obras/`
- **Contenido:** Documentación de planeamiento en curso y aprobado:
  - Plan Parcial SUR (2025): planos, estudio infraestructuras, documento ambiental
  - UA-3B urbanización (BOCM 2025-12-19 aprobación inicial)
  - Fichas de sectores (Las Flores, etc.)
  - Anuncios BOCM (inicio expediente, aprobaciones)
- **Formato:** Enlaces directos a PDF en `wp-content/uploads/`.
- **Categoría WP:** `concejalia-urbanismo-y-obras` (id 112).

### 3. Solicitudes y trámites — Licencias

- **URL:** `https://ayuntamientoelalamo.org/solicitudes/`
- **Formularios urbanismo:**
  - Solicitud de licencia urbanística (2025)
  - Declaración responsable urbanismo (2025)
  - Solicitud de vado
  - Subrogación expediente licencia
- **Uso:** Trámites informativos (no concesiones publicadas con coordenadas).

### 4. Sede electrónica eAdmin (Maggioli)

- **URL:** `https://elalamo.eadministracion.es/`
- **CMS:** Angular SPA (ATM-Maggioli). Sin tablón HTML scrapeable ni API pública de anuncios.
- **Limitación:** Solo presentación telemática de trámites; sin listado de expedientes/licencias concedidas.

### 5. Planeamiento y geometría — SIT Comunidad de Madrid

- **Visor:** `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **WFS capa:** `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='EL ÁLAMO'`
- **Ámbitos detectados (17 únicos, 36 features):** AA-1/2/3, SUI-1/2, SUR-1…7, UA-3B, UA-7D, UA-14, SAU-III, PE ARROYO LAS VEGAS
- **Campos:** `DS_NOMB_AMB`, `DS_FIG_DES`, geometría polígono EPSG:4326

### 6. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `www.elalamo.es` / `elalamo.es` | Sin DNS activo |
| Tablón sede eAdmin | SPA sin endpoint público |
| BOCM re-parse | Ya en pipeline regional |
| Expedientes sede | Requiere identificación Cl@ve |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `sitcm:VPLA_V_AMBITO` (`DS_MUNICIPIO='EL ÁLAMO'`, `DS_NOMB_AMB`), Visor SIT CM
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson` completo; enriquecimiento por código en título PDF (UA-3B, SUR-5, etc.) vía ILIKE
- **Limitaciones:** Sin visor municipal propio; sede eAdmin sin tablón; licencias solo formularios PDF; PDFs de planeamiento sin georreferencia directa

## Estrategia de ingesta

- **proyectos.jsonl:** 17 ámbitos SIT WFS + PDFs urbanismo filtrados + referencia PGOU.
- **licencias.jsonl:** Páginas informativas urbanismo/sede + formularios solicitudes.
- **IDs:** `el-alamo-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (ámbitos SIT + PDFs planeamiento).
- `licencias`: partial (formularios y trámites informativos; sin concesiones con coords).
- `with_geometry`: ~17/100+ (ámbitos SIT con polígono; PDFs enriquecidos si mencionan código de ámbito).
