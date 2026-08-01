# Camarma de Esteruelas — investigación portal ayuntamiento

**Municipio:** Camarma de Esteruelas (Comunidad de Madrid)  
**Fecha:** 2026-07-26  
**BOCM regional (referencia):** 13 avisos

## Resumen

Camarma de Esteruelas publica urbanismo en la web corporativa (Umbraco/Bootstrap) y en la **sede electrónica eHome / espublico gestiona** (Wicket):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Ordenanzas (urbanismo) | `http://www.camarmadeesteruelas.es/ayuntamiento/` | HTML tabs + PDFs `/media/` | Proyectos y licencias (ordenanzas) |
| Tablón sede | `https://camarmadeesteruelas.sedelectronica.es/board` | HTML tabla eHome | Proyectos y licencias (anuncios vigentes) |
| Transparencia sede | `https://camarmadeesteruelas.sedelectronica.es/transparency` | Wicket catálogo | Informativo (152 docs urbanismo) |
| Sede trámites | `https://camarmadeesteruelas.sedelectronica.es/dossier` | eHome catálogo | Informativo licencias |
| Consulta expedientes | `https://camarmadeesteruelas.sedelectronica.es/expedientes` | eHome | Requiere Cl@ve/certificado |
| Sede tributaria | `https://sedetributariacamarma.eadministracion.es` | eAdmin Maggioli | Autoliquidaciones (no licencias) |

## Fuentes detalladas

### 1. Web corporativa — Ayuntamiento / Ordenanzas

- **URL:** `http://www.camarmadeesteruelas.es/ayuntamiento/`
- **Pestañas:** Urbanismo, Obras y Servicios (tabs `#Urbanismo`, `#Obrasyservicios`).
- **Contenido urbanismo:** Ordenanza de construcciones y sus modificaciones, ordenanza servicios urbanísticos, tasas servicios urbanos, instalación de anuncios, apertura establecimientos, licencias autotaxi, plusvalías, dominio público, modificaciones NNSS colegio (`modif_nnss_colegio.pdf`), publicaciones BOCM históricas (2012).
- **Mecanismo:** enlaces directos a `/media/{id}/{nombre}.pdf`.

### 2. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://camarmadeesteruelas.sedelectronica.es/board`
- **Formato:** Tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`data-label`).
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Ejemplos (jul 2026):** convocatorias pleno/JGL, empleo público, presupuesto; históricamente licencias y urbanismo.
- **Limitación:** Solo anuncios vigentes (~10 filas); paginación vía Wicket AJAX («Mostrar más»).

### 3. Sede electrónica — Portal de transparencia

- **URL:** `https://camarmadeesteruelas.sedelectronica.es/transparency`
- **Sección 7:** «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (152 documentos).
- **Limitación:** Navegación Wicket AJAX; no scrapeado en v1 (catálogo dinámico).

### 4. Sede electrónica — Trámites y expedientes

- **Catálogo:** `/dossier` — licencias urbanísticas, actividades, consulta expedientes.
- **Consulta expedientes:** `/expedientes` — requiere identificación electrónica.

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `transparencia.camarmadeesteruelas.es` | HTTP 404 |
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| Visor municipal propio | No existe visor urbanístico municipal público |
| BOCM re-parse | Ya cubierto en pipeline regional |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='CAMARMA DE ESTERUELAS'`.
  - 29 ámbitos disponibles: UE-1 COVIMA, UE-2 LAS VEGAS, UE-3 NUEVO CAMARMA, S-1 MIRALOBUENO, S-3 SUR INDUSTRIAL, PE ENTORNO DE LA IGLESIA S. PEDRO, etc.
  - Ordenanzas PDF: sin georreferencia directa.
  - Sede `/expedientes`: requiere autenticación; no expone geometría pública.
- **Estrategia:** El adapter cruza títulos con códigos UE/S en SITCM vía `resolve_ambito_geometry`. Sin visor municipal enlazado a expediente individual.
- **Limitaciones:** Ordenanzas genéricas y tablón sin sector identificable no obtienen polígono; el orquestador aplica centroide + jitter.

## Estrategia de ingesta

- **proyectos.jsonl:** PDFs ordenanzas urbanismo (ayuntamiento) + tablón sede filtrado (urbanismo, planeamiento, BOCM, IP).
- **licencias.jsonl:** Páginas informativas (ayuntamiento + sede + transparencia) + ordenanzas licencias/construcción + tablón filtrado.
- **IDs:** `camarma-de-esteruelas-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.
