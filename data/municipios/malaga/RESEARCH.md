# Málaga — investigación portal ayuntamiento

**Municipio:** Málaga (capital, Málaga, Andalucía)  
**Slug:** `malaga`  
**Boletín:** BOJA (`boja`, 9 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Tecnología | Contenido |
|--------|-----|------------|-----------|
| Web corporativa | `https://www.malaga.eu` | SAGA Suite / OpenCMS | Tablón de edictos, transparencia |
| Tablón de edictos | `https://www.malaga.eu/el-ayuntamiento/tablon-de-edictos/` | SAGA CMS | Edictos con filtro por procedencia |
| Tablón urbanismo | `?procedencia=245` | GET form | **Vivienda y Urbanismo** (~7 edictos vigentes) |
| Portal urbanismo GMU | `https://urbanismo.malaga.eu` | SAGA skin-18 | Normativa, anuncios, trámites |
| Sede electrónica | `https://sede.malaga.eu` | OpenCMS sede | Catálogo trámites urbanismo |
| Trámites urbanismo | `/es/tramitacion/urbanismo/` | OpenCMS | ~50+ páginas de procedimientos |
| Datos abiertos | `https://datosabiertos.malaga.eu` | CKAN | Cartografía edificación (no por expediente) |
| Consulta expedientes | `https://urbanismo.malaga.eu/licencias/como-va-mi-expediente/` | — | Requiere Mi Carpeta (auth) |

**Nota:** `malaga.sedelectronica.es` no es la sede de la capital (página de selección genérica). La sede correcta es `sede.malaga.eu`.

## Cómo se listan expedientes

### Tablón de edictos (malaga.eu)

- Formulario GET con `procedencia` (departamento), `fechaDesde`, `fechaHasta`, `texto`.
- Procedencia **245 = Vivienda y Urbanismo** (Gerencia Municipal de Urbanismo).
- Cada edicto: `<li class="list-element">` con título departamento, descripción del acto, fechas de exposición y enlace `EDIDocumentDisplayer/{id}/{doc}`.
- Ejemplos: aprobación inicial Estudio de Detalle (Expte PL 44/2025), proyectos de expropiación, información pública.
- Sin paginación efectiva en el filtro urbanismo (7 filas actuales).

### Portal urbanismo.malaga.eu

- Secciones estáticas SAGA con PDFs en `/export/sites/urbanismo/.galleries/...`.
- Semillas: PGOM, OMLU, PEPRI, planeamiento de desarrollo, participación pública (p. ej. PERI Sierra de Churriana).
- `/anuncios-de-planeamiento/` enlaza subsecciones pero el listado dinámico no expone HTML scrapeable (contenido vacío en CI).

### Sede electrónica (sede.malaga.eu)

- Catálogo de **procedimientos** (no listado histórico de expedientes concluidos).
- Paginación `?page=N` en `/es/tramitacion/urbanismo/` (~500 entradas de trámites).
- Consulta de expedientes de obra mayor/menor requiere certificado / Mi Carpeta.

### Licencias

- No hay dataset público tabular de concesiones con coordenadas.
- Trámites DR/licencias en sede; consulta estado vía autenticación.
- Edictos de licencia pueden aparecer en tablón urbanismo cuando se publican.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - Visor GIS GMU (`urbanismo.malaga.eu/.../gis-visor-cartografico/`): **cerrado temporalmente** por actualización.
  - Datos abiertos «Sistema de Información Cartográfica - Edificación»: polígonos de edificios, sin campo expediente del tablón.
  - PRP Málaga / SITUA (Junta): planeamiento regional, sin enlace expediente↔polígono del ayuntamiento.
  - Consulta expedientes y Mi Carpeta: requieren autenticación.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter (`centroid: [36.7213, -4.4214]`).
- **Limitaciones:** Sin ArcGIS/WFS público enlazable a códigos de expediente; tablón y PDFs sin GeoJSON embebido.

## Limitaciones generales

- Sede lista procedimientos, no expedientes históricos abiertos.
- Tablón urbanismo: volumen bajo (~7 edictos vigentes) pero alta calidad (descripción + expte + PDF).
- Anuncios de planeamiento en urbanismo.malaga.eu sin HTML listable en CI.
- Visor GIS municipal inactivo.
- Sin geometría por expediente en fuentes públicas.

## Adapter implementado

- `municipio.adapters.malaga:MalagaAyuntamientoAdapter`
- Fuentes: tablón edictos (`procedencia=245`) + semillas urbanismo.malaga.eu + trámites informativos sede.
- IDs: `malaga-lic-*` / `malaga-proy-*` (sha256[:14]).
