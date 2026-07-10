# Valdemorillo — investigación portal ayuntamiento

**Municipio:** Valdemorillo (Comunidad de Madrid)  
**Fecha:** 2026-07-10  
**BOCM regional (referencia):** 14 avisos

## Resumen

Valdemorillo combina web corporativa WordPress (Elementor/OceanWP) con sede electrónica eHome (espublico/Wicket):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://aytovaldemorillo.com/urbanismo/` | WordPress + acordeón Elementor | Proyectos (NNSS PDFs) + trámites licencia (enlaces sede) |
| Tablón sede | `https://aytovaldemorillo.sedelectronica.es/board/` | HTML tabla eHome | Proyectos (PGOU avance, bandos IP) |
| Transparencia PGOU | `https://aytovaldemorillo.sedelectronica.es/transparency/4776aa0e-ebd0-438b-b391-6f8671ede0b2/` | eHome carpeta documental | Proyectos (avance PGOU 2026) |
| Catálogo trámites | `https://aytovaldemorillo.sedelectronica.es/catalog/t/{uuid}` | SPA eHome | Licencias (páginas informativas) |
| SIT Comunidad Madrid | `https://idem.comunidad.madrid/geoserver3/ows` | WFS `sitcm:VPLA_V_AMBITO` | Geometría parcial (25 ámbitos NNSS) |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress)

- **URL:** `https://aytovaldemorillo.com/urbanismo/`
- **REST API:** `https://aytovaldemorillo.com/wp-json/wp/v2/pages/31606`
- **Contenido:**
  - Acordeón **FORMULARIOS DE URBANISMO** → ~24 enlaces a catálogo sede (`/catalog/t/{uuid}`): licencias mayor/menor, DR, planeamiento, etc.
  - Acordeón **NORMAS SUBSIDIARIAS** (2022): PDFs (`acuerdo.pdf`, `catalogo.pdf`, `memoria.pdf`, `nurbanisticas_valdemorillo.pdf`, planos 1-18).
  - Sección licitaciones históricas (no urbanismo activo).
- **Noticias PGOU:** posts WP sobre avance PGOU (may-jun 2026); duplican tablón/transparencia.

### 2. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://aytovaldemorillo.sedelectronica.es/board/`
- **Formato:** Tabla HTML: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
- **Enlaces:** `preview-document/{uuid}`.
- **Ejemplos urbanismo (jun 2026):**
  - `BOCM-20260529-68` — ANUNCIO PUBLICACIÓN BOCM INFORMACIÓN PÚBLICA AVANCE PGOU (exp. 2932/2026).
  - `BANDO INFORMACIÓN PÚBLICA AVANCE PGOU` (exp. 2932/2026).
- **Limitación:** Solo anuncios vigentes (~10 filas); sin archivo histórico indexable.

### 3. Portal de transparencia — Avance PGOU

- **URL:** `https://aytovaldemorillo.sedelectronica.es/transparency/4776aa0e-ebd0-438b-b391-6f8671ede0b2/`
- **Contenido:** Carpeta documental del avance PGOU 2026 (informes técnicos, certificado pleno 30.04.2026, bando IP, prensa ABC).
- **Enlaces:** `preview-document/{uuid}`.

### 4. Sede electrónica — Trámites y expedientes

- **Catálogo:** `/catalog/t/{uuid}` — fichas de trámite (presentación online, no listado de concesiones).
- **Consulta expedientes:** `/expedientes` — requiere identificación Cl@ve.
- **`/info`:** bucle de redirecciones `info` → `info.0` (no usable en scrape automático).

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| Carpeta tributaria CiudadaNET | ICIO/tributos; sin listado licencias |
| BOCM re-parse | Ya en pipeline regional |
| Visor urbanístico municipal | No localizado; sin ArcGIS propio |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS Comunidad de Madrid: `sitcm:VPLA_V_AMBITO` con `DS_MUNICIPIO='VALDEMORILLO'`
  - 25 polígonos de ámbitos de Normas Subsidiarias (UA-1…UA-8, SAU-1…SAU-5, UA CERRO ALARCÓN, etc.)
  - Campo nombre: `DS_NOMB_AMB`; documento: `DS_DOCU` = "NORMAS SUBSIDIARIAS"
- **Estrategia:** query WFS por código ámbito (`UA-\d+`, `SAU-\d+`) o `ILIKE` sobre `DS_NOMB_AMB` cuando el título del expediente cita sector/ámbito. Reproyección `srsName=EPSG:4326`.
- **Limitaciones:**
  - Avance PGOU 2026 aún en tramitación — sin polígonos en SIT vinculados al expediente.
  - Tablón y transparencia publican PDFs sin georreferencia embebida.
  - No hay visor municipal con enlace expediente→geometría.
  - `/info` sede con redirect loop.

## Estrategia de ingesta

- **proyectos.jsonl:** tablón sede (PGOU IP) + transparencia PGOU + PDFs NNSS (urbanismo WP).
- **licencias.jsonl:** enlaces catálogo sede (formularios urbanismo) + tablón si aparecen licencias.
- **IDs:** `valdemorillo-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.
- **Geometría:** enriquecimiento WFS SIT cuando título menciona código/nombre de ámbito NNSS.

## Paridad esperada

- `proyectos`: ok (tablón PGOU + NNSS PDFs + transparencia).
- `licencias`: partial (trámites informativos sede; sin dataset de concesiones con coords).
- `with_geometry`: bajo (PGOU avance sin match SIT; posible match en títulos con UA/SAU).
