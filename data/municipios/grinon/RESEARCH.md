# Griñón — investigación portal ayuntamiento

**Municipio:** Griñón (Comunidad de Madrid)  
**Fecha:** 2026-06-23  
**BOCM regional (referencia):** 28 avisos

## Resumen

Griñón publica urbanismo en web corporativa WordPress (BeTheme + Elementor) y sede electrónica eHome (espublico gestiona):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://grinon.es/areas/urbanismo` | WordPress + Elementor | Hub de trámites y visores |
| Planeamiento | `https://grinon.es/areas/urbanismo/planeamiento-urbanistico` | WordPress + ~247 PDFs PGOU/PEP | Proyectos (planeamiento) |
| Anuncios urbanísticos | `https://grinon.es/areas/urbanismo/anuncios-urbanisticos` | Elementor (tabla estática) | Proyectos (IP ordenanzas) |
| Tablón sede | `https://grinon.sedelectronica.es/board/` | HTML tabla eHome | Proyectos y licencias vigentes |
| Trámites licencias | `https://grinon.es/areas/urbanismo/tramites-y-servicios/licencias` | WordPress informativo | Licencias (trámites) |
| Sede trámites | `https://grinon.sedelectronica.es/info.0` | eHome catálogo | Informativo licencias |
| Visor urbiGIS | `https://urbigis.com/grinon.maps` | Mapa cloud urbiGIS | Referencia GIS (sin API expediente) |
| Visor SIT CM | `https://idem.madrid.org/cartografia/sitcm/html/visor.htm` | Visor regional | Fuera de alcance adapter |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress)

- **URL base:** `https://grinon.es`
- **Urbanismo:** `https://grinon.es/areas/urbanismo`
- **Planeamiento:** `https://grinon.es/areas/urbanismo/planeamiento-urbanistico` — PGOU, modificaciones puntuales, estudios de detalle, convenios (247 PDFs en `wp-content/uploads/2024/03/`).
- **Anuncios urbanísticos:** tabla Elementor con título, fechas de publicación y plazos (2 filas activas en jun 2026: ordenanzas edificación e ICIO).
- **Trámites licencias:** `tramites-y-servicios/licencias`, `declaraciones-responsables` — páginas informativas con enlace a sede.

### 2. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://grinon.sedelectronica.es/board/`
- **Formato:** Tabla HTML: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación.
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Ejemplo urbanismo (may 2026):** Modificación puntual conjuntos residenciales (exp. 1813/2023, categoría Urbanismo / Planeamiento General).
- **Limitación:** Solo anuncios vigentes (~10 filas); sin archivo histórico indexable.

### 3. Sede electrónica — Trámites y expedientes

- **Catálogo:** `/info.0` — trámites urbanísticos vía sede.
- **Consulta expedientes:** `/expedientes` — requiere identificación Cl@ve/certificado.
- **Sin dataset abierto** de licencias con coordenadas.

### 4. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| urbiGIS API REST | Sin endpoint público por código de expediente |
| BOCM re-parse | Ya cubierto en pipeline regional |
| `www.grinon.es` | Redirige a `grinon.es` |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - urbiGIS: `https://urbigis.com/grinon.maps` (org 5336, map 3386) — capas de planeamiento municipal, WMS/WFS en plataforma cloud sin API REST documentada para consulta por expediente.
  - SIT Comunidad de Madrid: `https://idem.madrid.org/cartografia/sitcm/html/visor.htm` — visor regional, no enlaza expedientes del ayuntamiento.
- **Estrategia:** El adapter no enriquece `geom_geojson` (sin campo expediente enlazable en GIS público). El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:** Visor urbiGIS solo informativo; tablón y PDFs sin georreferencia scrapeable; consulta expedientes requiere login.

## Estrategia de ingesta

- **proyectos.jsonl:** PDFs planeamiento + tablón sede (urbanismo) + anuncios urbanísticos (tabla Elementor).
- **licencias.jsonl:** tablón sede (filtro licencia/obra) + páginas trámites licencias/declaración responsable + sede.
- **IDs:** `grinon-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (247 PDFs planeamiento + tablón + anuncios).
- `licencias`: partial (sin listado de concesiones con coordenadas; trámites informativos).
- `with_geometry`: 0 (geometry_status partial, sin enlace expediente→polígono).
