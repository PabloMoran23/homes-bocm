# San Martín de Valdeiglesias — investigación portal ayuntamiento

**Municipio:** San Martín de Valdeiglesias (Comunidad de Madrid)  
**Fecha:** 2026-08-01  
**BOCM regional (referencia):** 13 avisos

## Resumen

San Martín de Valdeiglesias publica urbanismo en web corporativa WordPress y sede electrónica eHome (espublico gestiona). No hay visor urbanístico propio; el planeamiento vigente (NNSS 1999 y ámbitos UE/SAU) se consulta en el Visor SIT de la Comunidad de Madrid (código municipio 133).

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://www.sanmartindevaldeiglesias.es/areas/obras-urbanismo/` | WordPress | Informativo licencias + formularios PDF |
| Normativa municipal | `https://www.sanmartindevaldeiglesias.es/ayuntamiento/normativa-municipal/` | PDFs BOCM | Proyectos (ordenanzas, UE-25) |
| Tablón sede | `https://sanmartindevaldeiglesias.sedelectronica.es/board` | HTML tabla eHome | Proyectos/licencias (anuncios vigentes) |
| Transparencia sede | `https://sanmartindevaldeiglesias.sedelectronica.es/transparency/` | espublico | Sin documentación urbanística indexable |
| Sede trámites | `https://sanmartindevaldeiglesias.sedelectronica.es/` | espublico gestiona | Informativo presentación telemática |
| Visor SIT CM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=133` | ArcGIS/WFS | Ámbitos UE/SAU con polígono |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Geometría ámbitos (`DS_MUNICIPIO='SAN MARTÍN DE VALDEIGLESIAS'`) |

## Fuentes detalladas

### 1. Web corporativa — Obras y Urbanismo (WordPress)

- **URL:** `https://www.sanmartindevaldeiglesias.es/areas/obras-urbanismo/`
- **Contenido:** Trámites de licencia urbanística, declaración responsable, cédula urbanística, mesas y sillas. Enlaces a autoliquidación y sede electrónica.
- **Formularios PDF:** `Sol_lurb-r.pdf`, `Sol_declurb.pdf`, `solicitud-mesas-sillas.pdf`, ordenanzas de licencias.
- **Visor normativa:** Enlace al Visor SIT CM con `municipio=133` y matriz NNSS 25/09/1999.

### 2. Normativa municipal — Publicaciones BOCM

- **URL base:** `https://www.sanmartindevaldeiglesias.es/wp-content/uploads/ayuntamiento/normativa-municipal/`
- **Documentos relevantes:** UE-25 Dotacional Ermita Ecce Homo, Ordenanza 11 licencias apertura, ordenanzas comercial y vivienda (BOCM 13/11/2020).
- **Uso:** Semillas de proyectos con enriquecimiento geométrico por código UE en título.

### 3. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://sanmartindevaldeiglesias.sedelectronica.es/board`
- **CMS:** espublico gestiona (Wicket/YUI). Requiere `insecure_ssl: true` (cadena certificado).
- **Formato:** Tabla Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.
- **Enlaces:** `preview-document/{uuid}`.
- **Estado ago 2026:** ~10 anuncios vigentes; al menos 1 licencia de actividad (centro equino, polígono 15 parcela 191).
- **Limitación:** Solo anuncios vigentes; sin histórico indexable.

### 4. Planeamiento y geometría — SIT Comunidad de Madrid

- **Visor:** `https://www.madrid.org/cartografia/sitcm/html/visor.htm?municipio=133`
- **WFS capa:** `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='SAN MARTÍN DE VALDEIGLESIAS'`
- **Ámbitos detectados (49):** UE-01A … UE-34, SAU-01 … SAU-12 (unidades de ejecución y sectores de actuación urbanística).
- **Campos:** `DS_NOMB_AMB`, `DS_FIG_DES`, geometría polígono EPSG:4326.
- **NNSS:** Matriz 25/09/1999; modificaciones publicadas en BOCM (p. ej. UE-25 en 2020).

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `/expedientes` sede | Requiere identificación Cl@ve |
| `/transparency/` sede | Sin documentación urbanística indexable en HTML |
| BOCM re-parse | Ya en pipeline regional |
| Licencias con coordenadas | No publicadas en dataset abierto |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `sitcm:VPLA_V_AMBITO` (`DS_MUNICIPIO='SAN MARTÍN DE VALDEIGLESIAS'`, `DS_NOMB_AMB`), Visor SIT CM municipio 133
- **Estrategia:** Semillas de ámbitos UE/SAU desde WFS con `geom_geojson` completo; enriquecimiento por código en título (tablón, normativa BOCM) vía ILIKE
- **Limitaciones:** Sin visor municipal propio; tablón sin coordenadas; licencias solo formularios PDF; sin enlace expediente→polígono en sede

## Estrategia de ingesta

- **proyectos.jsonl:** 49 ámbitos SIT WFS + referencia NNSS + PDFs normativa BOCM + tablón filtrado.
- **licencias.jsonl:** Páginas informativas urbanismo/sede + formularios PDF + tablón filtrado.
- **IDs:** `san-martin-de-valdeiglesias-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (49 ámbitos SIT + seeds normativa).
- `licencias`: partial (formularios y trámites informativos; tablón con pocas licencias).
- `with_geometry`: ~49+ (ámbitos SIT con polígono; normativa UE-25 con geometría).
