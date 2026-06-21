# Ciempozuelos — investigación portal ayuntamiento

**Municipio:** Ciempozuelos (Comunidad de Madrid)  
**Fecha:** 2026-06-21  
**BOCM regional (referencia):** 38 avisos

## Resumen

Ciempozuelos publica urbanismo y licencias en portales fragmentados: sede electrónica add4u (tablón de edictos) y web corporativa WordPress (Avada).

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Sede electrónica (tablón) | `https://sede.ayto-ciempozuelos.org/eAdmin/Tablon.do?action=verAnuncios` | HTML tabular (add4u) | Proyectos y licencias del tablón |
| Web corporativa — urbanismo | `https://ayto-ciempozuelos.org/index.php/urbanismo/` | WordPress + PDFs | Trámites informativos (IEE, normativa) |
| Web — trámites urbanismo | `https://ayto-ciempozuelos.org/index.php/tramites-municipales/#tramites-urbanismo/1544` | WordPress APC | Enlace a trámites sede |
| Sede — trámites | `https://sede.ayto-ciempozuelos.org/eAdmin/Registrar.do?action=inicioPortalTramites` | HTML (add4u) | Solicitud General Urbanismo (informativo) |

## Fuentes detalladas

### 1. Sede electrónica add4u (tablón de edictos)

- **Base:** `https://sede.ayto-ciempozuelos.org/eAdmin/`
- **Listado:** `Tablon.do?action=verAnuncios` (~130 anuncios activos e históricos visibles)
- **Detalle:** `Tablon.do?action=verAnuncio&id=<HEX16>`
- **Campos en detalle:** Identificador, Descripción, Contenido, Fecha inicio/fin publicación, GRUPO
- **Documentos:** PDFs vía JavaScript (`abrir('base64')`); no hay URL directa scrapeable sin ejecutar JS
- **Urbanismo relevante:** anuncios de información pública, plenos municipales (acuerdos), IBI urbana, ordenanzas fiscales con impacto urbanístico

### 2. Web corporativa WordPress

- **Base:** `https://ayto-ciempozuelos.org` (redirige desde `www.ciempozuelos.es` a portal comercio)
- **Urbanismo:** página informativa con ordenanza IEE y enlaces a normativa CM
- **Plenos:** `index.php/plenos-municipales/` — actas en tablón sede, no listado estructurado en web
- **Portal transparencia:** sin sección dedicada de planeamiento/convenios comparable a Fuenlabrada

### 3. Trámites electrónicos

- Categoría **Urbanismo** en sede: «Solicitud General Urbanismo» (trámite online, sin listado de concesiones)
- No hay dataset abierto de licencias con coordenadas (a diferencia de Madrid capital)

## Limitaciones

| Limitación | Impacto |
|------------|---------|
| PDFs del tablón vía JS (`abrir`) | No se extrae `pdf_url` directo; se usa URL de detalle del anuncio |
| Sin visor urbanístico ni API | No hay geometrías ni expedientes estructurados |
| `www.ciempozuelos.es` redirige a portal comercio | Usar `ayto-ciempozuelos.org` como base |
| Licencias de obra no publicadas en tablón | `licencias.jsonl` será partial (trámites informativos) |

## Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `tucomercio.ciempozuelos.es` | Portal comercio, no urbanismo |
| Pipeline Madrid (`sector_geometry/madrid_*`) | Fuera de alcance |
| Re-parseo BOCM regional | Ya existe en `web/public/data/projects.json` |

## Estrategia de ingesta

- **proyectos.jsonl:** tablón sede (filtro urbanismo/pleno/información pública) + detalle enriquecido
- **licencias.jsonl:** tablón (filtro licencia) + páginas informativas urbanismo/sede
- **IDs:** `ciempozuelos-{lic|proy}-{sha256[:14]}`
- **source:** `ayuntamiento`

## Paridad esperada

- `proyectos`: ok (anuncios IP, plenos, IBI urbana en tablón)
- `licencias`: partial/none (sin concesiones públicas; trámites informativos)
