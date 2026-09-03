# Valencia de Don Juan — investigación portal ayuntamiento

**Municipio:** Valencia de Don Juan (provincia León, Castilla y León)  
**Fecha:** 2026-09-03  
**BOCYL (referencia):** 2 avisos  
**INE:** 24188 | **DIR3:** L01241882

## Resumen

Valencia de Don Juan dispone de **web corporativa WordPress** (`www.valenciadedonjuan.es`) y
**sede electrónica espublico gestiona** (`valenciadedonjuan.sedelectronica.es`). El planeamiento
urbanístico vigente (PGOU revisado + planes parciales + estudios de detalle) está centralizado en
**PlanPublica / SiuCyL** (Junta de Castilla y León). No hay visor urbanístico municipal propio;
la geometría de sectores e instrumentos está disponible en **IDECyL WFS**. No existe listado
público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.valenciadedonjuan.es/ | WordPress + Customizr |
| Urbanismo y obras | https://www.valenciadedonjuan.es/secciones/areas/urbanismo-y-obras/ | Noticias y enlaces |
| Archivo PLAU (enlace WP) | https://www.valenciadedonjuan.es/solicitudes-y-descargas/archivo-de-planeamiento-urbanistico-y-ordenacion-del-territorio-vigente-plau/ | Redirige a PlanPublica JCyL |
| Sede electrónica | https://valenciadedonjuan.sedelectronica.es/ | espublico gestiona (Wicket) |
| Tablón de anuncios | https://valenciadedonjuan.sedelectronica.es/board | Tabla HTML + PDF preview |
| Tablón filtro Urbanismo | https://valenciadedonjuan.sedelectronica.es/board/975963e4-f59b-11de-b600-00237da12c6a/ | Vacío (sep 2026) |
| Catálogo de trámites | https://valenciadedonjuan.sedelectronica.es/dossier/.0 | Requiere cookie de sesión |
| Transparencia | https://valenciadedonjuan.sedelectronica.es/transparency | Sección 7 «Urbanismo, obras públicas y medio ambiente» |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=188 | 14 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=188 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=24188 | Mapa interactivo regional |

**PlanPublica códigos:** `provincia=24` (León), `municipio=188` (Valencia de Don Juan)

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **PGOU** (Plan General de Ordenación Urbana, revisión), aprobación definitiva **22/05/2007** (`cDocId=283314`).
- Modificaciones puntuales nº1 (2009), nº2 (2016), nº3 (2023).
- Planes parciales (sector ULD I-02, sector industrial El Tesoro).
- Estudios de detalle (NC04, PA-C01, Valjunco, etc.).
- PA Integrada UA.1 (2021).

### Listado PlanPublica (PLAU) — cómo se presentan

Página HTML con tabla ordenable. Cada fila incluye:

| Campo | Origen HTML |
|-------|-------------|
| Código expediente | `24188-{PU\|GU\|EU\|SU}-YYYYMMDD-{cDocId}` en `doOpen()` / `doGoBoletin()` |
| Tipo instrumento | PU / GU / EU / SU |
| Subtipo | PGOU, PP, ED, PAU, … |
| Fecha publicación | `DD/MM/YYYY` |
| Enlace PDF | `openDocumento.do?cDocId={id}` |

**Documentos identificados (sep 2026):** 14 instrumentos (PGOU revisión, PP El Tesoro, PP ULD I-02, ED NC04, ED Valjunco, mod. puntuales PGOU, PA Integrada UA.1, etc.)

### Tablón de anuncios

Tabla HTML en sede espublico:

```
tbody > tr
  td: Documento (preview-document/{uuid})
  td: Expediente
  td: Procedimiento
  td: Categoría
  td: Descripción
  td: Fecha (DD/MM/YYYY)
```

Filtro Urbanismo vacío a fecha de investigación; el tablón general puede contener avisos puntuales.

## 3. Licencias de obra

**No hay registro público** de licencias concedidas (sin visor, sin dataset abierto, sin listado buscable).

| Fuente | Qué aporta |
|--------|------------|
| Catálogo trámites sede | Páginas informativas de solicitud (no concesiones) |
| Tablón | Avisos ocasionales; filtro Urbanismo vacío |
| Transparencia §7 | PDFs de proyectos/estudios; no índice de licencias |

Trámites relevantes (UUIDs espublico):

- Solicitud de Licencia o Autorización Urbanística
- Declaración Responsable o Comunicación en Materia Urbanística
- DECLARACIÓN RESPONSABLE DE OBRAS
- Solicitud de Licencia de Ocupación

El adapter devuelve páginas informativas de trámites (patrón Pozuelo/Valverdón).

## 4. Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro CQL: `n_mun='Valencia de Don Juan'` (alt: `c_mun='24188'`)
  - Campos enlace: `c_id_sect`, `n_num_sect`, `c_plan`, `url_doc_info`
- **Estrategia:**
  1. Descargar features WFS en EPSG:4326 (`outputFormat=application/json`)
  2. Para filas PLAU/tablón, cruzar códigos de sector (NC04, ULD I-02, etc.) con WFS sectores
  3. PGOU/NUM: usar polígono de `plau_cyl_instrumentos_ambito`
- **Limitaciones:**
  - Sin geometría por expediente individual de licencia
  - Sin visor municipal ArcGIS
  - Tablón/PDF sin georreferencia enlazable
  - Solo polígonos de sectores e instrumentos de planeamiento

### WFS — capas y features (sep 2026)

| Capa | Features | Campos clave |
|------|----------|--------------|
| `plau_cyl_instrumentos_ambito` | 1 | `c_plan`, `c_instrum=PGOU`, `n_titulo`, `url_doc_info` |
| `plau_cyl_planes_parciales` | 1 | `c_id_sect`, `n_num_sect`, `geometry` |
| `plau_cyl_sectores` | 25 | `c_id_sect` (ej. `24188NC04`), `n_num_sect`, `d_estado`, `geometry` |

**Ejemplo query WFS:**

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeNames=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Valencia de Don Juan'
```

## 5. Limitaciones técnicas

- Sede espublico: requiere cookie jar; primera carga de `/dossier/.0` lenta (~30–50 s)
- SSL sede: certificado válido; `insecure_ssl: true` por compatibilidad con otros adapters CYL
- WordPress: sin API estructurada de urbanismo; solo HTML + PDFs en `/wp-content/uploads/`
- Paginación tablón: Wicket AJAX (solo primera página scrapeada)
- Licencias: solo trámites informativos, sin concesiones publicadas

## 6. Adapter

- **Clase:** `ValenciaDeDonJuanAyuntamientoAdapter`
- **Fuentes:** IDECyL WFS → PlanPublica PLAU/PLAI → tablón sede → catálogo trámites → web WP
- **Patrón:** CYL/León (valverdon, la_robla, villaquilambre)
