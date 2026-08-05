# Daganzo de Arriba — investigación portal ayuntamiento

**Municipio:** Daganzo de Arriba (Comunidad de Madrid)  
**Fecha:** 2026-08-03  
**BOCM regional (referencia):** 10 avisos

## Resumen

Daganzo de Arriba publica urbanismo en la web corporativa (Fontventa CMS) y en la **sede electrónica eHome / espublico gestiona**:

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| NNSS 1995 | `https://www.ayto-daganzo.org/avisos/normas-subsidiarias-de-planeamiento-1995` | HTML + PDFs `/media/` | Proyectos (planeamiento) |
| Ordenanzas municipales | `https://www.ayto-daganzo.org/avisos/ordenanzas-municipales` | HTML + PDFs `/media/` | Licencias (ordenanzas) |
| Tablón sede | `https://daganzo.sedelectronica.es/board` | HTML tabla eHome | Proyectos y licencias (anuncios vigentes) |
| Transparencia sede | `https://daganzo.sedelectronica.es/transparency` | Wicket catálogo | Informativo (urbanismo) |
| Sede trámites | `https://daganzo.sedelectronica.es/dossier` | eHome catálogo | Informativo licencias |
| Trámites urbanismo web | `https://www.ayto-daganzo.org/sede-electronica/urbanismo/*` | Páginas informativas | Licencias (trámites) |
| Consulta expedientes | `https://daganzo.sedelectronica.es/expedientes` | eHome | Requiere Cl@ve/certificado |
| Portal tributos | `https://tributos.daganzoconecta.org` | eAdmin | Autoliquidaciones (no licencias) |

## Fuentes detalladas

### 1. Web corporativa — Normas subsidiarias de planeamiento

- **URL:** `https://www.ayto-daganzo.org/avisos/normas-subsidiarias-de-planeamiento-1995`
- **Contenido:** Memoria NNSS, normas generales/particulares, fichero de ordenación, catálogo de bienes protegidos, planos de clasificación y estructura (7 planos PDF).
- **Mecanismo:** enlaces directos a `/media/{id}/{nombre}.pdf` (Fontventa CMS).

### 2. Web corporativa — Ordenanzas municipales

- **URL:** `https://www.ayto-daganzo.org/avisos/ordenanzas-municipales`
- **Contenido:** Índices y textos de ordenanzas fiscales y de policía/buen gobierno; enlace a NNSS.
- **Uso:** modelos y normativa de trámites (licencias).

### 3. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://daganzo.sedelectronica.es/board`
- **Formato:** Tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha de Publicación (`data-label`).
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Ejemplos (ago 2026):** publicación BOCM aprobación provisional modificación NNSS S-9 y S-10, anuncio BOCM expropiación; también empleo público y presupuesto.
- **Limitación:** Solo anuncios vigentes (~10 filas); paginación vía Wicket AJAX.

### 4. Sede electrónica — Trámites urbanismo

- **Catálogo:** `/dossier` — licencias urbanísticas, actividades, consulta expedientes.
- **Páginas web informativas:** `/sede-electronica/urbanismo/*` (licencia ocupación vía pública, etc.).
- **Consulta expedientes:** `/expedientes` — requiere identificación electrónica.

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `www.daganzodearriba.es` | Dominio inactivo / no resuelve |
| Visor municipal propio | No existe visor urbanístico municipal público |
| BOCM re-parse | Ya cubierto en pipeline regional |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS SITCM Comunidad de Madrid: `https://idem.comunidad.madrid/geoserver3/ows` capa `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='DAGANZO DE ARRIBA'`.
  - 30 ámbitos disponibles: S-1, S-2, S-3 (aplzado)…S-7, U1–U12, áreas de gestión condicionada A–H, áreas de desarrollo urbanístico condicionado.
  - NNSS PDFs y planos: sin georreferencia directa en el portal.
  - Sede `/expedientes`: requiere autenticación; no expone geometría pública.
- **Estrategia:** El adapter cruza títulos con códigos S-/U- en SITCM vía `resolve_ambito_geometry`. Sin visor municipal enlazado a expediente individual.
- **Limitaciones:** Ordenanzas genéricas y tablón sin sector identificable no obtienen polígono; el orquestador aplica centroide + jitter.

## Estrategia de ingesta

- **proyectos.jsonl:** PDFs NNSS/planeamiento (web) + tablón sede filtrado (urbanismo, planeamiento, BOCM, IP).
- **licencias.jsonl:** Páginas informativas (sede + trámites urbanismo) + tablón filtrado.
- **IDs:** `daganzo-de-arriba-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.
