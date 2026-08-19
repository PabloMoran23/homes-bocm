# El Vellón — investigación portal ayuntamiento

**Municipio:** El Vellón (Comunidad de Madrid)  
**Fecha:** 2026-08-12  
**BOCM regional (referencia):** 4 avisos

## Resumen

El Vellón publica información municipal en portal corporativo DNN (`http://elvellon.es`, skin xcillion). Urbanismo y licencias aparecen como formularios PDF en trámites personales; no hay sección dedicada de planeamiento ni tablón scrapeable. La sede electrónica es Maggioli eAdmin (`sedeelvellon.eadministracion.es`). El planeamiento vigente (NNSS 1976) y reservas urbanas se consultan en el Visor SIT de la Comunidad de Madrid.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Portal trámites | `http://elvellon.es/Ciudadanos/Trámites-Personales` | DNN + PDF `/Portals/4/` | Formularios licencias |
| Noticias | `http://elvellon.es/Ayuntamiento/Noticias` | DNN + PDF | Licitación consultorio médico |
| Pleno | `http://elvellon.es/Ayuntamiento/Pleno` | DNN + PDF actas | Crawl PDFs (filtro urbanismo) |
| Ordenanzas | `http://elvellon.es/Ayuntamiento/Normativa-Municipal/Ordenanzas` | DNN + PDF | Ordenanza vía pública |
| Sede eAdmin | `https://sedeelvellon.eadministracion.es/` | Maggioli SPA | Informativo (sin tablón API) |
| PGOU avance CM | `https://www.comunidad.madrid/transparencia/.../documento_inicial_estrategico_5.pdf` | PDF | Referencia PGOU en redacción |
| Visor SIT CM | `https://www.madrid.org/cartografia/sitcm/html/visor.htm` | ArcGIS/WFS | Reservas urbanas P-5/P-6/P-9 |
| WFS SITCM | `https://idem.comunidad.madrid/geoserver3/ows` | GeoJSON WFS | Geometría (`DS_MUNICIPIO='EL VELLÓN'`) |

## Fuentes detalladas

### 1. Portal corporativo DNN (elvellon.es)

- **URL base:** `http://elvellon.es` (HTTP; HTTPS no operativo en dominio principal).
- **CMS:** DotNetNuke 7 + skin xcillion. Documentos en `/Portals/4/`.
- **Concejalía:** Urbanismo, Obras, Licencias, Turismo y Comercio (sin área web propia; trámites en Ciudadanos).
- **Limitación:** Sin listado de expedientes en información pública ni visor municipal.

### 2. Trámites — Licencias y autorizaciones

- **URL:** `http://elvellon.es/Ciudadanos/Trámites-Personales`
- **Formularios PDF (2023):**
  - Licencia de obras mayores / menores
  - Licencia primera ocupación
  - Licencia urbanística de actividad
  - Acto comunicado
  - Licencia actividad-funcionamiento
- **Uso:** Trámites informativos (no concesiones publicadas con coordenadas).

### 3. Noticias municipales

- **URL:** `http://elvellon.es/Ayuntamiento/Noticias`
- **Urbanismo relevante:** `Licitación_Consultorio.pdf` (obra consultorio médico).
- **Otros PDFs:** empleo, bibliobús, fiestas (excluidos del adapter).

### 4. Sede electrónica eAdmin (Maggioli)

- **URL:** `https://sedeelvellon.eadministracion.es/`
- **CMS:** Angular SPA. Entrada vía `PortalCiudadano/Menus/wfrBienvenida.aspx`.
- **Limitación:** Sin tablón HTML scrapeable ni API pública de anuncios urbanísticos.

### 5. Planeamiento — PGOU en redacción

- **Documento:** Documento Inicial Estratégico PGOU El Vellón (contrato feb. 2022, OMICRON AMEPRO).
- **URL CM:** PDF en transparencia Comunidad de Madrid (`documento_inicial_estrategico_5.pdf`).
- **Vigente:** Normas Complementarias y Subsidiarias 1976 (NNSS 76).

### 6. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `www.elvellon.es` / `elvellon.org` | Dominios no municipales (404 / blog viaje) |
| `el-vellon.sedelectronica.es` | Sede indeterminada espublico |
| Actas de pleno masivas | Sin filtro urbanismo en título; ruido administrativo |
| BOCM re-parse | Ya en pipeline regional |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `sitcm:VPLA_V_AMBITO` (`DS_MUNICIPIO='EL VELLÓN'`), Visor SIT CM
- **Ámbitos detectados (3):** P-5 RESERVA URBANA, P-6 RESERVA URBANA, P-9 RESERVA URBANA
- **Estrategia:** Semillas de ámbitos desde WFS con `geom_geojson` completo; enriquecimiento por código P-N en título
- **Limitaciones:** Sin visor municipal; sede eAdmin sin tablón; licencias solo formularios PDF; PGOU en redacción sin geometría municipal

## Estrategia de ingesta

- **proyectos.jsonl:** 3 ámbitos SIT WFS + referencia PGOU avance + PDFs urbanismo filtrados (licitación consultorio).
- **licencias.jsonl:** Páginas informativas trámites + sede + modelos PDF licencias (sin concesiones publicadas).

## Limitaciones

- Portal solo HTTP en dominio principal.
- Sin geometría en licencias concedidas (no publicadas).
- Planeamiento detallado solo en visor regional SITCM (3 polígonos).
