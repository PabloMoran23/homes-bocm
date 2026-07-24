# Chapinería — investigación portal ayuntamiento

**Municipio:** Chapinería (Comunidad de Madrid)  
**Fecha:** 2026-07-23  
**BOCM regional (referencia):** 14 avisos

## Resumen

Chapinería publica urbanismo en web corporativa WordPress (`chapineria.madrid`) y sede electrónica eHome (espublico gestiona). No hay visor urbanístico propio del ayuntamiento; el planeamiento vigente (NNSS 2000 y ámbitos de desarrollo) se consulta en el Visor SIT de la Comunidad de Madrid.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://chapineria.madrid/urbanismo/` | WordPress | Informativo licencias + referencia NNSS |
| Área descargas | `https://chapineria.madrid/area-de-descargas-del-ayuntamiento-de-chapineria/` | PDFs 04.xx | Licencias (formularios trámite) |
| Tablón sede | `https://chapineria.sedelectronica.es/board/` | HTML tabla eHome | Proyectos/licencias (anuncios vigentes) |
| Sede trámites | `https://chapineria.sedelectronica.es/` | espublico gestiona | Informativo presentación telemática |
| Visor SIT CM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/WFS | Ámbitos UE/S con polígono |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Geometría ámbitos (`DS_MUNICIPIO='CHAPINERÍA'`) |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress)

- **URL:** `https://chapineria.madrid/urbanismo/`
- **Contenido:** Descripción competencias (licencias, declaraciones responsables, cédulas). Remite al Visor SIT para NNSS aprobadas en 2000.
- **Sin PDFs** de expedientes ni planeamiento en curso en la página.
- **API REST:** `wp-json/wp/v2/pages/1107` disponible.

### 2. Área de descargas — Formularios urbanismo

- **URL:** `https://chapineria.madrid/area-de-descargas-del-ayuntamiento-de-chapineria/`
- **Serie 04.xx:** Obra mayor (04.08), declaración responsable (04.09), primera ocupación (04.10), cédula urbanística (04.12), parcelación (04.13), etc.
- **Uso:** Trámites informativos de licencia (no concesiones publicadas con coordenadas).

### 3. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://chapineria.sedelectronica.es/board/`
- **CMS:** espublico gestiona (Wicket/YUI). Requiere `insecure_ssl: true` (cadena certificado).
- **Formato:** Tabla Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.
- **Enlaces:** `preview-document/{uuid}`.
- **Estado jul 2026:** 3 anuncios vigentes (empleo, bando limpieza parcelas/incendios, jurado). El bando de parcelas encaja como aviso urbanístico.
- **Limitación:** Solo anuncios vigentes; sin histórico indexable.

### 4. Planeamiento y geometría — SIT Comunidad de Madrid

- **Visor:** `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **WFS capa:** `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='CHAPINERÍA'`
- **Ámbitos detectados (35):** UE-01 … UE-25, UE-V 01 VALQUIGOSO, S-01 … S-10 (sectores residenciales y unidades de ejecución).
- **Campos:** `DS_NOMB_AMB`, `DS_FIG_DES`, geometría polígono EPSG:4326.
- **NNSS:** Aprobadas definitivamente 25/05/2000, vigentes desde 11/07/2000 (referencia en web urbanismo).

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `www.chapineria.es` | Dominio inactivo (sin DNS) |
| `/dossier` sede | Timeout en CI |
| `/transparency/` sede | Sin documentación urbanística indexable |
| BOCM re-parse | Ya en pipeline regional |
| Expedientes sede | Requiere identificación Cl@ve |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `sitcm:VPLA_V_AMBITO` (`DS_MUNICIPIO='CHAPINERÍA'`, `DS_NOMB_AMB`), Visor SIT CM
- **Estrategia:** Semillas de ámbitos UE/S desde WFS con `geom_geojson` completo; enriquecimiento por código en título (tablón) vía ILIKE
- **Limitaciones:** Sin visor municipal propio; tablón sin coordenadas; licencias solo formularios PDF; sin enlace expediente→polígono en sede

## Estrategia de ingesta

- **proyectos.jsonl:** 35 ámbitos SIT WFS + referencia NNSS + tablón filtrado (bando parcelas).
- **licencias.jsonl:** Páginas informativas urbanismo/sede + formularios 04.xx descargas + tablón filtrado.
- **IDs:** `chapineria-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (35 ámbitos SIT + seeds).
- `licencias`: partial (formularios y trámites informativos; sin concesiones con coords).
- `with_geometry`: ~35/36 (ámbitos SIT con polígono).
