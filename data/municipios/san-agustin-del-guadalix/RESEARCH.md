# San Agustín del Guadalix — investigación portal ayuntamiento

**Municipio:** San Agustín del Guadalix (Comunidad de Madrid)  
**Fecha:** 2026-06-22  
**BOCM regional (referencia):** 32 avisos

## Resumen

El ayuntamiento publica planeamiento y documentación urbanística principalmente en el **portal de transparencia** (WordPress Divi en `sanagustindelguadalix.net`). La **sede electrónica** (`sanagustindelguadalix.sedelectronica.es`, espublico gestiona) expone un tablón de anuncios con edictos recientes. No hay visor urbanístico ni dataset de licencias concedidas con coordenadas.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Portal transparencia — urbanismo | `https://sanagustindelguadalix.net/portal-transparencia/normativa-urbanismo/` | WordPress REST + PDFs | Proyectos (PGOU, PERI, convenios, urbanizaciones) |
| Formularios urbanismo | `https://sanagustindelguadalix.net/formularios-solicitudes/#urbanismo` | HTML + PDFs trámite | Licencias informativas |
| Sede electrónica — tablón | `https://sanagustindelguadalix.sedelectronica.es/board/` | HTML tabular (espublico) | Edictos urbanismo/licencias recientes |
| Sede electrónica — trámites | `https://sanagustindelguadalix.sedelectronica.es/dossier` | Catálogo HTML | Trámites urbanísticos informativos |

## Fuentes detalladas

### 1. Portal transparencia (WordPress Divi)

- **Base:** `https://sanagustindelguadalix.net`
- **CMS:** WordPress 6.x + tema Divi (AyuntamientoSanAgustin v4.18)
- **API:** `wp-json/wp/v2/pages` — árbol bajo página `25892` (Normativa urbanismo)
- **Subsecciones relevantes:**
  - PGOU (87 PDFs aprobación inicial 2020)
  - PERI-1 (aprobación inicial)
  - Proyectos de urbanización (SAU-8, convenio Luis Carreño, parcela industrial)
  - Normas subsidiarias y ordenanzas PERIS
  - Carreteras (corredor norte A-1)
- **Total documentos:** ~283 PDFs únicos en el árbol urbanismo
- **Certificado SSL:** cadena incompleta en el dominio `.net` → `insecure_ssl: true`

### 2. Sede electrónica espublico gestiona

- **Base:** `https://sanagustindelguadalix.sedelectronica.es`
- **Tablón:** `/board/` — columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha
- **Documentos:** `preview-document/<uuid>` (PDF descargable)
- **Consulta expedientes:** requiere identificación en Mi carpeta (no pública)
- **Tablón actual (~jun 2026):** mayoría empleo/padrón; edictos urbanismo aparecen esporádicamente

### 3. Licencias de obra

- **Formularios:** página `formularios-solicitudes` con PDFs de solicitud DRU, licencia obra mayor/menor, ocupación vía pública, licencias de actividad
- **No hay** listado público de licencias concedidas con dirección ni coordenadas (a diferencia de Madrid capital)
- Estrategia: filas informativas de trámites + edictos del tablón cuando mencionen licencia

### 4. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `www.sanagustindelguadalix.es` | 503 / no operativo; web activa en `.net` |
| Portal tributario `portaltributos.aytosag.net` | Tributos, no urbanismo |
| Re-parseo BOCM regional | Ya en `web/public/data/projects.json` |
| Pipeline Madrid SIGMA | Fuera de alcance |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes exploradas:**
  - Plugin `wp-mapit` (Leaflet) cargado en el tema, sin API REST pública ni enlace a expedientes
  - Página información castral: solo enlace Google Maps genérico
  - PDFs de planos en transparencia sin georreferencia scrapeable
  - Sede: sin visor GIS ni WFS
- **Estrategia:** el orquestador aplicará centroide municipio + jitter vía `geocode`
- **Limitaciones:** planos en PDF sin polígono vectorial; no hay ArcGIS/WFS/GeoJSON municipal

## Estrategia de ingesta

- **proyectos.jsonl:** BFS páginas WP urbanismo (páginas + PDFs) + tablón sede (filtro urbanismo/edicto)
- **licencias.jsonl:** formularios urbanismo + sede informativa + tablón (filtro licencia)
- **IDs:** `san-agustin-del-guadalix-{lic|proy}-{sha256[:14]}`
- **source:** `ayuntamiento`

## Paridad esperada

- `proyectos`: ok (PGOU, PERI, convenios, ~280+ PDFs)
- `licencias`: partial (trámites informativos; sin concesiones públicas georreferenciadas)
- `with_geometry`: 0 (geometry_status unavailable)
