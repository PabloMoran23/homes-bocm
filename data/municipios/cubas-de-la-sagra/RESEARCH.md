# Cubas de la Sagra — investigación portal ayuntamiento

**Municipio:** Cubas de la Sagra (Comunidad de Madrid)  
**Fecha:** 2026-06-23  
**BOCM regional (referencia):** 26 avisos  
**INE municipio (Visualurb):** 28050

## Resumen

Cubas de la Sagra publica planeamiento en la web corporativa (PDFs/ZIP del PGOU) y anuncios en la sede electrónica espublico gestiona (`/board/`). Dispone de visor urbanístico Visualurb (Mencía) enlazado desde el menú principal.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web — urbanismo | `https://aytocubasdelasagra.es/tramites-y-gestiones/urbanismo.php` | HTML + PDF/ZIP | Proyectos PGOU (normas, sectores, modificaciones) |
| Web — documentación obras | `https://aytocubasdelasagra.es/tramites-y-gestiones/documentacion-obras.php` | HTML + PDF | Licencias/trámites informativos |
| Sede — tablón | `https://cubasdelasagra.sedelectronica.es/board/` | HTML tabla (espublico/Wicket) | Proyectos y licencias publicadas |
| Sede — expedientes | `https://cubasdelasagra.sedelectronica.es/expedientes` | Login Cl@ve | No scrapeable sin autenticación |
| Sede — dossier | `https://cubasdelasagra.sedelectronica.es/dossier` | Timeout desde CI | Inaccesible en automatización |
| Visor Visualurb | `https://sig.visualurb.es/visor?org=65afe619-2d89-4adc-af48-9948618f1c1e` | SPA Mapbox + API | Geometría (parcial, ver abajo) |

## Fuentes detalladas

### 1. Web corporativa (Bootstrap custom)

- **Base:** `https://aytocubasdelasagra.es`
- **Urbanismo:** listado estático de documentos PGOU: normas subsidiarias, áreas incorporadas, interpretaciones NNSS, modificación puntual, sectores suelo urbanizable (ZIP), unidades de ejecución (ZIP), planos ordenación (ZIP), catálogo bienes protegidos (ZIP).
- **Documentación obras:** guías y documentación necesaria para licencias (declaración responsable, segregación, primera ocupación, grúa-torre, placas solares, etc.).
- Sin CMS WordPress/Drupal; enlaces directos a `/documentos/urbanismo/` y `/documentos/documentacion-obras/`.

### 2. Sede electrónica espublico gestiona

- **Plataforma:** Wicket + YAHOO.expedientes (mismo patrón que Brunete, Pelabravo, Villalbilla).
- **Tablón público:** `/board/` — tabla con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha; enlaces `preview-document/<uuid>`.
- **Contenido actual (jun 2026):** convocatorias de pleno, empleo público, anuncios genéricos; sin licencias de obra recientes en tablón.
- **Consulta expedientes:** requiere identificación electrónica (Cl@ve); no accesible sin login.

### 3. Visor urbanístico Visualurb (Mencía)

- **URL visor:** `https://sig.visualurb.es/visor?org=65afe619-2d89-4adc-af48-9948618f1c1e`
- **API base:** `https://api-sig.visualurb.es`
- **Código municipio:** `28050` (`GET /urbanismo/municipio/28050` → bbox del término municipal)
- **Capas consultables en visor:** suelo municipio, PMS, obras (según menú SPA).
- **GeoJSON capas:** `GET /MapUrbanismo/layer/suelomunicipio/28050.geojson` → **401 Unauthorized** sin sesión.
- **PMS municipio:** `GET /mapurbanismo/layer/pmsmunicipio/28050.geojson` → sin datos / error.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - Visor Visualurb público (Mapbox) con org UUID `65afe619-2d89-4adc-af48-9948618f1c1e`
  - API REST `api-sig.visualurb.es` — metadatos municipio (bbox) públicos; capas GeoJSON requieren autenticación
  - PGOU en PDF/ZIP sin geometría vectorial scrapeable
- **Estrategia:** adapter intenta `MapUrbanismo/layer/suelomunicipio/{codmuni}.geojson`; si 401, deja `geom_geojson` vacío. Orquestador aplica centroide municipio + jitter vía geocode.
- **Limitaciones:** sin WFS/ArcGIS público; API Visualurb bloqueada sin token; expedientes sede tras login; tablón sin coordenadas.

## Limitaciones

| Limitación | Impacto |
|------------|---------|
| `/dossier` timeout desde CI | Sin catálogo trámites sede; se usan páginas informativas web |
| Expedientes sede con Cl@ve | No listado público de concesiones |
| Visualurb GeoJSON 401 | `with_geometry` probablemente 0 |
| Tablón sin urbanismo reciente | `licencias.jsonl` partial (trámites informativos) |
| PDFs/ZIP sin georref | Proyectos PGOU sin polígono automático |

## Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| BOCM regional re-parse | Ya en `web/public/data/projects.json` |
| Madrid SIGMA (`sector_geometry/madrid_*`) | Solo capital |
| Visor SIT CM | Planeamiento regional; no sustituye expedientes locales |

## Estrategia de ingesta

- **proyectos.jsonl:** tablón sede (plenos, urbanismo) + PDFs/ZIPs PGOU urbanismo
- **licencias.jsonl:** tablón (filtro licencia) + documentación obras (trámites informativos)
- **IDs:** `cubas-de-la-sagra-{lic|proy}-{sha256[:14]}`
- **source:** `ayuntamiento`

## Paridad esperada

- `proyectos`: ok (PGOU + convocatorias pleno)
- `licencias`: partial (documentación trámites; sin concesiones en tablón)
