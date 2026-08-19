# Corpa — investigación portal ayuntamiento

**Municipio:** Corpa (Comunidad de Madrid)  
**Fecha:** 2026-08-16  
**BOCM regional (referencia):** 3 avisos

## Resumen

Corpa publica planeamiento en web corporativa Neosoft (`ayuntamientocorpa.es`) y anuncios en sede electrónica eHome (espublico gestiona). No hay visor urbanístico propio; el planeamiento vigente (NNSS y ámbitos) se consulta en el Visor SIT de la Comunidad de Madrid.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://www.ayuntamientocorpa.es/urbanismo` | Neosoft HTML + PDF | NNSS, planos ordenación, catálogo |
| Web normativa | `https://www.ayuntamientocorpa.es/normativa` | PDF ordenanzas | Licencias (ordenanzas trámite) |
| Tablón sede | `https://corpa.sedelectronica.es/board` | HTML tabla eHome | Proyectos/licencias (anuncios vigentes) |
| Sede eAdmin | `https://sedecorpa.eadministracion.es/` | Maggioli SPA | Trámites telemáticos |
| Sede espublico | `https://corpa.sedelectronica.es/` | espublico gestiona | Tablón + trámites |
| Visor SIT CM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/WFS | Ámbitos UE/SAU con polígono |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Geometría ámbitos (`DS_MUNICIPIO='CORPA'`) |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (Neosoft)

- **URL:** `https://www.ayuntamientocorpa.es/urbanismo`
- **Contenido:** Normas subsidiarias de planeamiento municipal (INDICE, NORMAS-URBANISTICAS, modificación puntual), catálogo de bienes protegidos, índice de planos y serie `planos-ordenacion-*.pdf`.
- **Enlace al visor SIT:** `http://idem.madrid.org/cartografia/sitcm/html/visor.htm`
- **Listado:** HTML estático con enlaces `/Ficheros/Documentos/*.pdf` y atributo `tittle` en `<a>`.

### 2. Web normativa — Ordenanzas licencias

- **URL:** `https://www.ayuntamientocorpa.es/normativa`
- **Urbanismo:** Ordenanza reguladora tasa licencias y actuaciones urbanísticas, ordenanza primera ocupación, ordenanza vallado y limpieza de solares.
- **Uso:** Trámites informativos (no concesiones con coordenadas).

### 3. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://corpa.sedelectronica.es/board`
- **CMS:** espublico gestiona (Wicket/YUI).
- **Formato:** Tabla Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.
- **Enlaces:** `preview-document/{uuid}`.
- **Estado ago 2026:** Anuncios vigentes mayoritariamente presupuestos, empleo y tributos; sin expedientes urbanísticos activos en tablón.
- **Limitación:** Solo anuncios vigentes; sin histórico indexable.

### 4. Sede Maggioli eAdmin

- **URL:** `https://sedecorpa.eadministracion.es/`
- **Uso:** Presentación telemática de solicitudes; tablón en SPA Angular sin API pública scrapeable.

### 5. Planeamiento y geometría — SIT Comunidad de Madrid

- **Visor:** `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **WFS capa:** `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='CORPA'`
- **Ámbitos detectados (5):** UE-A, UE-B, UE-C, UE-E, SAU-1
- **Campos:** `DS_NOMB_AMB`, geometría polígono EPSG:4326
- **NNSS:** Publicadas en web municipal (normas subsidiarias PDF)

### 6. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `www.corpa.es` | Redirige a corpachef.com (empresa, no ayuntamiento) |
| `ayuntamientodecorpa.es` | Dominio comprometido / redirección spam |
| BOCM re-parse | Ya en pipeline regional |
| Expedientes sede | Requiere identificación Cl@ve |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid IDEM: `https://idem.comunidad.madrid/geoserver3/ows`
  - Capa: `sitcm:VPLA_V_AMBITO`
  - Filtro: `DS_MUNICIPIO='CORPA'`
  - Campo ámbito: `DS_NOMB_AMB` (UE-A, UE-B, UE-C, UE-E, SAU-1)
  - Visor público: `https://www.madrid.org/cartografia/sitcm/html/visor.htm`
- **Estrategia:** Descargar polígonos WFS por ámbito; cruzar títulos de anuncios/PDF con código UE/SAU cuando aparece en el texto.
- **Limitaciones:**
  - Sin visor urbanístico municipal ni ArcGIS por expediente individual.
  - PDFs NNSS/planos sin georreferencia embebida; geometría solo para ámbitos del planeamiento vigente.
  - Tablón actual sin licencias/expedientes urbanísticos vigentes.
  - Sede eAdmin no expone geometría.

## Limitaciones generales

- Municipio pequeño; publicación urbanística concentrada en NNSS/PGOU estático.
- Tablón sede solo muestra anuncios vigentes (presupuestos, empleo).
- Fechas inferidas de nombres de fichero o año en título cuando no hay fecha en HTML.
