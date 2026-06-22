# Navalcarnero — investigación portal ayuntamiento

**Municipio:** Navalcarnero (Comunidad de Madrid)  
**Fecha:** 2026-06-22  
**BOCM regional (referencia):** 37 avisos

## Resumen

Navalcarnero publica urbanismo en varios subsitios WordPress del dominio `navalcarnero.es`, un portal de transparencia independiente (`transparencia.navalcarnero.es`) y una sede electrónica (`sede.navalcarnero.es`) orientada a trámites con identificación.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Urbanismo — mapa obras | `https://navalcarnero.es/navalcarnero/urbanismo/` | HTML + MapPress (`mapdata` JSON) | Proyectos de mejora urbana con coords |
| Urbanismo — RSS | `https://navalcarnero.es/navalcarnero/urbanismo/feed/` | RSS WordPress | PGOU, planes especiales, modificaciones |
| Transparencia — urbanismo | `https://transparencia.navalcarnero.es/obras-publicas-y-urbanismo/` | WordPress + PDFs | Convenios, planes especiales, PGOU |
| Tablón de anuncios | `https://navalcarnero.es/navalcarnero/tablondeanuncios/feed/` | RSS WordPress | Anuncios/edictos (filtro urbanismo) |
| Trámites urbanismo | `https://navalcarnero.es/navalcarnero/tramites/?category=71` | Download Monitor | Formularios licencia (informativo) |
| Sede electrónica | `https://sede.navalcarnero.es/` | Redirige a carpeta ciudadano | Trámites online (login) |

## Fuentes detalladas

### 1. Subsitio Urbanismo (WordPress + MapPress)

- **Base:** `https://navalcarnero.es/navalcarnero/urbanismo/`
- **Mapa:** plugin MapPress con variable JS `mapdata.pois[]` — 37 puntos con `lat`/`lng`, título y enlace a ficha PDF en `/urbanismo/files/*.pdf`
- **Tabla HTML:** listado de obras municipales con año de ejecución y enlace a ficha PDF
- **Posts recientes (RSS):** modificaciones puntuales PGOU (1, 2, 4, 7), plan especial fotovoltaica Labrador, plan especial soterramiento LAMT
- **Información de interés:** enlaces a trámites (`/tramites/?category=71`) y normativa BOE/CM

### 2. Portal de transparencia

- **PGOU:** `obras-publicas-y-urbanismo/informacion-del-pgou/` — mapas y planos
- **Planes parciales:** `obras-publicas-y-urbanismo/planes-parciales/` — sin PDFs directos visibles en listado
- **Planes especiales:** `obras-publicas-y-urbanismo/planes-especiales/` — PDFs PSF Labrador (2026)
- **Convenios:** `obras-publicas-y-urbanismo/convenios-urbanisticos/` — ~65 PDFs históricos (T1–T12 2006, addenda Iberdrola, convenio 2023)
- **Visor regional:** enlace a `http://idem.madrid.org/cartografia/sitcm/html/visor.htm` (SITCM Comunidad de Madrid, no enlaza expedientes municipales)
- **Geo-referenciación catastral:** enlace a consulta CM (no API scrapeable por expediente)

### 3. Tablón de anuncios (WordPress)

- **Categorías:** bandos, citaciones, actas sesiones, etc.
- **Formato:** posts con PDF en `/tablondeanuncios/files/At_Publico2_*.pdf`
- **Urbanismo:** pocos anuncios explícitos; predominan tributos, precios públicos, actas de dominio registral

### 4. Sede electrónica

- Redirige a `GDCarpetaCiudadano` (gestión documental / consulta expedientes con login)
- No hay tablón público scrapeable comparable a add4u/espublico
- Trámites de licencia solo como formularios descargables en web de trámites

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - MapPress en página urbanismo: 37 POIs con `point.lat` / `point.lng` (WGS84 implícito Google Maps)
  - IDEM/SITCM visor regional: sin capa municipal de expedientes
  - Sin ArcGIS MapServer ni WFS municipal público
- **Estrategia:** extraer coords del JSON `mapdata` embebido; generar polígono buffer (~30 m) alrededor de cada punto para `geom_geojson`; planeamiento/PDFs sin geometría
- **Limitaciones:**
  - Solo puntos de obras municipales en mapa (no delimitación de expedientes PGOU/planes)
  - Planes especiales y convenios son PDF sin georreferencia scrapeable
  - Sede requiere autenticación para consulta de expedientes
  - `with_geometry` en parity refleja obras con buffer; resto usa centroide municipio + jitter

## Limitaciones generales

| Limitación | Impacto |
|------------|---------|
| Sin listado público de licencias concedidas | `licencias.jsonl` partial (trámites informativos) |
| Múltiples subsitios WordPress | Crawl por feed + páginas semilla |
| PDFs tablón con nombres opacos (`At_Publico2_*.pdf`) | Título del post como metadato principal |
| Sede sin tablón abierto | No se scrapean concesiones de obra |

## Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| Pipeline Madrid (`sector_geometry/madrid_*`) | Fuera de alcance |
| Re-parseo BOCM regional | Ya en `web/public/data/projects.json` |
| IDEM visor CM | Cartografía regional, sin enlace a expediente municipal |

## Estrategia de ingesta

- **proyectos.jsonl:** MapPress obras + RSS urbanismo + PDFs transparencia + tablón (filtro urbanismo)
- **licencias.jsonl:** tablón (filtro licencia) + trámites category=71 + sede informativa
- **IDs:** `navalcarnero-{lic|proy}-{sha256[:14]}`
- **source:** `ayuntamiento`

## Paridad esperada

- `proyectos`: ok (obras mapa + planeamiento + convenios)
- `licencias`: partial (formularios/trámites; sin concesiones públicas)
- `with_coords`: ok en obras con MapPress
- `with_geometry`: partial (buffer en obras mapa)
