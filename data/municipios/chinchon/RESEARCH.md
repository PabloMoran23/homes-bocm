# Chinchón — investigación portal ayuntamiento

**Municipio:** Chinchón (Comunidad de Madrid)  
**Fecha:** 2026-08-06  
**BOCM regional (referencia):** 7 avisos

## Resumen

Chinchón publica urbanismo en web corporativa PHP (`ciudad-chinchon.com`) y sede electrónica eHome (espublico gestiona). No hay visor urbanístico propio; el planeamiento vigente se consulta en el Visor SIT de la Comunidad de Madrid (3 unidades de actuación UA).

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://www.ciudad-chinchon.com/ayuntamiento/concejalias/servicios-urbanisticos/presentacion.php` | PHP estático | Informativo licencias + trámites |
| Descarga impresos | `https://www.ciudad-chinchon.com/ayuntamiento/ayto/descarga-impresos.php` | PDFs | Formularios licencia/obra |
| Tablón sede | `https://chinchon.sedelectronica.es/board/` | HTML tabla eHome | Proyectos/licencias (anuncios vigentes) |
| Sede trámites | `https://chinchon.sedelectronica.es/` | espublico gestiona | Informativo presentación telemática |
| Sede legacy | `https://chinchon.sedemunicipa.es/` | sedemunicipa | Catálogo trámites (enlace en web) |
| Visor SIT CM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/WFS | Ámbitos UA con polígono |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Geometría ámbitos (`DS_MUNICIPIO='CHINCHÓN'`) |

## Fuentes detalladas

### 1. Web corporativa — Servicios Técnicos Urbanísticos

- **URL base:** `https://www.ciudad-chinchon.com/ayuntamiento/concejalias/servicios-urbanisticos/`
- **Subpáginas:** tramitacion-licencias, obras-mayores, obras-menores, licencias-ocupacion
- **Contenido:** Documentación requerida para licencias (obras mayores/menores, primera ocupación). PDF Ley del Suelo CAM.
- **Sin listado** de expedientes ni concesiones con coordenadas.

### 2. Descarga de impresos — Formularios

- **URL:** `https://www.ciudad-chinchon.com/ayuntamiento/ayto/descarga-impresos.php`
- **PDFs urbanismo:** instancia_obras, licencia_funcionamiento, licencia_apertura, licencia_instalacion
- **Uso:** Trámites informativos de licencia (no concesiones publicadas).

### 3. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://chinchon.sedelectronica.es/board/`
- **CMS:** espublico gestiona (Wicket/YUI). Requiere `insecure_ssl: true` (cadena certificado).
- **Formato:** Tabla Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.
- **Enlaces:** `preview-document/{uuid}`.
- **Estado ago 2026:** ~10 anuncios vigentes (subvenciones, IAE, empleo). Sin anuncios urbanísticos activos en tablón.
- **Bandos:** La web remite al tablón de sede para consulta de bandos.

### 4. Planeamiento y geometría — SIT Comunidad de Madrid

- **Visor:** `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **WFS capa:** `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='CHINCHÓN'`
- **Ámbitos detectados (3):** UA-1 VAGUADA, UA-2 COOPERATIVA SAN ROQUE, UA-3 LAS CRUCES
- **Campos:** `DS_NOMB_AMB`, `DS_FIG_DES`, geometría polígono EPSG:4326.

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `www.chinchon.es` / `chinchon.es` | Sin respuesta DNS/HTTP |
| `/dossier` sede | Catálogo trámites sin listado expedientes |
| `/transparency/` sede | Sin documentación urbanística indexable |
| BOCM re-parse | Ya en pipeline regional |
| Expedientes sede | Requiere identificación Cl@ve |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `sitcm:VPLA_V_AMBITO` (`DS_MUNICIPIO='CHINCHÓN'`, `DS_NOMB_AMB`), Visor SIT CM
- **Estrategia:** Semillas de ámbitos UA desde WFS con `geom_geojson` completo; enriquecimiento por código en título (tablón) vía ILIKE
- **Limitaciones:** Sin visor municipal propio; tablón sin coordenadas ni anuncios urbanísticos vigentes; licencias solo formularios PDF; sin enlace expediente→polígono en sede

## Estrategia de ingesta

- **proyectos.jsonl:** 3 ámbitos SIT WFS + folleto Ley del Suelo + tablón filtrado (si hay urbanismo).
- **licencias.jsonl:** Páginas informativas urbanismo/sede + formularios PDF + tablón filtrado.
- **IDs:** `chinchon-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (3 ámbitos SIT + seed normativa).
- `licencias`: partial (formularios y trámites informativos; sin concesiones con coords).
- `with_geometry`: ~3/4 (ámbitos SIT con polígono).
