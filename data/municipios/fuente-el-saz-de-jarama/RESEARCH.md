# Fuente el Saz de Jarama — investigación portal ayuntamiento

**Municipio:** Fuente el Saz de Jarama (Comunidad de Madrid)  
**Fecha:** 2026-06-23  
**BOCM regional (referencia):** 25 avisos

## Resumen

Fuente el Saz publica planeamiento y urbanismo en tres frentes: web corporativa Joomla (Gantry), sede electrónica add4u (tablón de edictos) y portal de transparencia con categoría Urbanismo (artículos + PDFs).

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Portal transparencia — urbanismo | `https://ayuntamientofuentelsaz.com/ayuntamiento/portal-de-transparencia/urbanismo` | Joomla categoría + RSS | Proyectos (estudios de detalle, convenios, reparcelaciones) |
| RSS urbanismo | `.../urbanismo?format=feed&type=rss` | RSS 2.0 | Semilla proyectos recientes |
| Sede electrónica (tablón) | `https://sede.ayuntamientofuentelsaz.com/eAdmin/Tablon.do?action=verAnuncios` | HTML tabular (add4u) | Proyectos (sección Urbanismo) y licencias si aparecen |
| Web — urbanismo | `https://ayuntamientofuentelsaz.com/areas-municipales/urbanismo-y-actividades/urbanismo` | Joomla | Trámites informativos licencias |
| Solicitudes de licencias | `.../urbanismo/solicitudes-de-licencias` | PDFs descargables | Trámites informativos (formularios) |
| PGOU | `.../urbanismo/plan-general-de-ordenacion-urbana` | Joomla + PDFs | Documentación planeamiento |

## Fuentes detalladas

### 1. Portal de transparencia (Joomla)

- **Listado:** categoría Urbanismo con paginación (`?start=0,10,20,30` — ~31 artículos)
- **RSS:** 10 entradas más recientes con título, enlace, fecha y PDFs adjuntos
- **Contenido relevante:** estudios de detalle (ED-15 La Tercia, Uueq-09), convenios (Sector 5 Menesianos, Villa Chiquita AA-03), proyectos de urbanización (UE-1 AA-02 Pocillo Este), reparcelaciones, aprobaciones plenario
- **PDFs:** en `/images/PORTALTRANSPARENCIA/Urbanismo 20XX/`

### 2. Sede electrónica add4u (tablón de edictos)

- **Base:** `https://sede.ayuntamientofuentelsaz.com/eAdmin/`
- **Listado:** `Tablon.do?action=verAnuncios` — secciones Anuncios, Edictos, Urbanismo, etc.
- **Detalle:** `Tablon.do?action=verAnuncio&id=<HEX16>`
- **Campos en detalle:** Identificador, Descripción, Contenido, Fecha inicio/fin publicación, GRUPO
- **Urbanismo activo (jun 2026):** «LA TERCIA, 1 - ESTUDIO DE DETALLE ED-15» (información pública)
- **Documentos:** PDFs vía JavaScript (`abrir('base64')`); no hay URL directa scrapeable

### 3. Web corporativa — trámites licencias

- Página «Solicitudes de Licencias» con formularios PDF (obra mayor/menor, segregación, declaración fuera de ordenación, etc.)
- No hay listado público de concesiones de licencia con dirección ni coordenadas
- Sede electrónica: trámites online requieren certificado digital; sin dataset de concesiones

### 4. Tablón de edictos web (estático)

- `https://ayuntamientofuentelsaz.com/ayuntamiento/tablon-de-edictos` — tabla HTML con edictos históricos (p. ej. Proyecto Urbanización AE-03 Oliver)
- Contenido parcialmente duplicado en transparencia; se usa como semilla secundaria

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - No hay visor urbanístico municipal ni WFS/GeoJSON en el portal del ayuntamiento
  - El PGOU se publica como PDF/planos en la web, sin capa GIS enlazable a expedientes
  - El Visor SIT de la Comunidad de Madrid (`idem.madrid.org`) tiene planeamiento refundido del municipio, pero no enlaza códigos de expediente del tablón/transparencia (ED-15, AA-03, etc.)
- **Estrategia:** el orquestador aplicará centroide municipal + jitter vía `geocode`
- **Limitaciones:** solo PDFs y anuncios textuales; sin polígonos por expediente

## Limitaciones

| Limitación | Impacto |
|------------|---------|
| PDFs del tablón vía JS (`abrir`) | No se extrae `pdf_url` directo; se usa URL de detalle |
| Sin visor GIS municipal | `geom_geojson` ausente; `with_geometry` = 0 |
| Licencias de obra no publicadas | `licencias.jsonl` partial (trámites informativos) |
| Codificación ISO-8859-1 en sede | El adapter decodifica con fallback latin-1 |

## Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| Visor SIT Comunidad de Madrid | PGOU genérico, sin enlace a expedientes del ayto |
| Pipeline Madrid (`sector_geometry/madrid_*`) | Fuera de alcance |
| Re-parseo BOCM regional | Ya existe en `web/public/data/projects.json` |
| `tributos.ayuntamientofuentelsaz.com` | Autoliquidación tasas, no listado concesiones |

## Estrategia de ingesta

- **proyectos.jsonl:** RSS transparencia + crawl categoría urbanismo + tablón sede (filtro urbanismo)
- **licencias.jsonl:** tablón (filtro licencia) + páginas informativas solicitudes/declaración responsable
- **IDs:** `fuente-el-saz-{lic|proy}-{sha256[:14]}`
- **source:** `ayuntamiento`

## Paridad esperada

- `proyectos`: ok (≥30 filas de transparencia + tablón urbanismo)
- `licencias`: partial (formularios/trámites informativos; sin concesiones públicas)
- `with_geometry`: 0 (`geometry_status: unavailable`)
