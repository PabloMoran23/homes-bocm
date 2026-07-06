# El Molar — investigación portal ayuntamiento

**Municipio:** El Molar (Comunidad de Madrid)  
**Fecha:** 2026-07-06  
**BOCM regional (referencia):** 20 avisos

## Resumen

El Molar publica urbanismo en web corporativa WordPress (`elmolar.org`) y sede electrónica eHome/espublico gestiona (`elmolar.sedelectronica.es`):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Normas subsidiarias | `https://elmolar.org/tramites/normas-subsidiarias/` | WordPress acordeón + PDFs | Proyectos (10 expedientes, ~56 PDFs) |
| Documentación trámites | `https://elmolar.org/tramites/documentacion/` | WordPress + instancias PDF | Licencias (formularios informativos) |
| Tablón sede | `https://elmolar.sedelectronica.es/board` | eHome Wicket | Proyectos/licencias (anuncios vigentes) |
| Transparencia sede | `https://elmolar.sedelectronica.es/transparency` | eHome AJAX | Sección «URBANISMO» (27 docs; carga dinámica) |
| Trámites urbanismo | `https://elmolar.sedelectronica.es/citizen-service/cb07ecfa-a5b4-4a85-9bc9-d133fc07a33f` | Catálogo sede | Informativo |
| Noticias urbanismo | `https://elmolar.org/noticias/category/urbanismo/` | WordPress REST | Proyectos complementarios |
| Ordenanzas | `https://elmolar.org/tramites/ordenanzas/` | PDFs normativa | Descartado (fiscal/tributario) |

## Fuentes detalladas

### 1. Web corporativa — Normas subsidiarias (WordPress)

- **URL:** `https://elmolar.org/tramites/normas-subsidiarias/`
- **Contenido:** 10 expedientes de planeamiento en acordeón Visual Composer:
  - `R-50785_NNSS_2002` (Normas Subsidiarias 2002)
  - `R-53111_CCond SAU 4_5_11_12_13_E`, `R-62245_CCond SAU 21` (condiciones SAU)
  - `R-64228_MP Catalogo`, `R-70802_MP SG EG-2`, `R-71448_MP Dotacional Norte`, `R-74144_MP SG QG-01`, `R-77984_MP NS Zona Norte`, `R-78363_MP NS Peña de la Pala`, `R-80370_MP El Charcón` (modificaciones puntuales)
- **Documentos por expediente:** ACUERDO, EXPTE. ADMVO, MEMORIA, NORMAS URBANISTICAS, PLANOS, CATALOGO, etc.
- **Mecanismo:** HTML estático con `vc_tta-panel` y enlaces `/wp-content/uploads/2019/02/*.pdf`.

### 2. Web corporativa — Documentación / licencias

- **URL:** `https://elmolar.org/tramites/documentacion/`
- **Contenido:** Instancias PDF para trámites (obra mayor/menor, terrazas, parcelación, ocupación vía pública, etc.).
- **Limitación:** Son formularios de solicitud, no concesiones publicadas con fecha ni ubicación.

### 3. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://elmolar.sedelectronica.es/board`
- **Plataforma:** espublico gestiona (Wicket/YUI), mismo patrón que Humanes/Brunete.
- **Formato:** Enlaces `preview-document/{uuid}` con atributo `title`.
- **Estado (jul 2026):** ~8 anuncios vigentes (plenos, oposiciones); pocos de urbanismo activos.
- **Histórico:** No hay archivo público indexable.

### 4. Portal de transparencia sede

- **URL:** `https://elmolar.sedelectronica.es/transparency`
- **Sección:** «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (27 documentos).
- **Limitación:** Contenido cargado vía `wicketAjaxGet`; no aparece en HTML inicial sin sesión JS.

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `elmolar.org/gobierno-abierto/datos-abiertos/` | Página informativa sin datasets GeoJSON/WFS |
| Mapa Google en home (`maps.googleapis.com`) | Mapa genérico municipio, sin capas urbanísticas |
| SIT Comunidad de Madrid | Sin enlace desde portal ni campo expediente |
| Consulta expedientes `/expedientes` | Requiere Cl@ve/certificado |
| BOCM re-parse | Ya en pipeline regional |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor urbanístico municipal (ArcGIS, WFS, GeoJSON). El tema WordPress `city2` incluye Google Maps para mapa corporativo sin capas de planeamiento ni enlace a expedientes.
- **Estrategia:** El orquestador aplicará centroide municipal + jitter vía geocode.
- **Limitaciones:** PDFs de planeamiento sin georreferencia; tablón sin coordenadas; transparencia sin API pública.

## Estrategia de ingesta

- **proyectos.jsonl:** Expedientes normas subsidiarias (10) + PDFs asociados + tablón sede filtrado + noticias urbanismo/obras.
- **licencias.jsonl:** Formularios trámites documentación + tablón sede (licencias) + página tablón informativa.
- **IDs:** `el-molar-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (≥10 expedientes planeamiento + noticias).
- `licencias`: partial (formularios informativos; sin concesiones con coordenadas).
- `with_geometry`: 0 (geometry_status unavailable).
