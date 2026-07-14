# Quijorna — investigación portal ayuntamiento

**Municipio:** Quijorna (Comunidad de Madrid)  
**Fecha:** 2026-07-14  
**BOCM regional (referencia):** 18 avisos

## Resumen

Quijorna publica urbanismo en web corporativa WordPress (tema **citygov**, Elementor) y sede electrónica **espublico gestiona** (eHome/Wicket):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Web urbanismo | `https://aytoquijorna.org/concejalias/urbanismo/` | WordPress | Índice trámites y normativa |
| Trámites PDF | `.../tramites-y-gestiones-de-urbanismo/` | 22 PDFs `wp-content/uploads/2026/06/` | Licencias (guías) + proyectos |
| Transparencia NN.SS | `.../transparency/c3bde2cb-3329-460a-9b0b-d02e55dc25f5/` | 10 capítulos Tomo II | Proyectos (planeamiento) |
| Ordenanzas urbanísticas | `.../transparency/ad88615a-a13d-4576-a91d-63050c8fc9f8/` | 8 documentos | Proyectos (ordenanzas) |
| Tablón general | `https://aytoquijorna.sedelectronica.es/board/` | HTML tabla eHome | Proyectos (anuncios vigentes) |
| Tablón urbanismo | `.../board/974e6d5e-f59b-11de-b600-00237da12c6a/` | HTML tabla eHome | Vacío salvo bando limpieza parcelas |
| Normativa web | `.../normativa-urbanistica/` | Enlaces a sede/transparencia | Semilla dossiers |
| Sede trámites | `https://aytoquijorna.sedelectronica.es/info.2` | eHome catálogo | Informativo licencias |

## Fuentes detalladas

### 1. Web corporativa — Urbanismo (WordPress)

- **URL base:** `https://aytoquijorna.org/concejalias/urbanismo/`
- **Trámites:** 22 guías PDF (obras mayores/menores, segregaciones, fotovoltaicas, demoliciones, etc.) en `wp-content/uploads/2026/06/`.
- **Catálogo procedimientos:** página informativa sin dataset scrapeable.
- **Mecanismo:** HTML estático con enlaces directos a PDF.

### 2. Sede electrónica eHome — Tablón de anuncios

- **URL general:** `https://aytoquijorna.sedelectronica.es/board/`
- **Formato:** Tabla HTML con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Contenido (jul 2026):** ~4 anuncios no urbanísticos (IAE, empleo, subvenciones) + bando limpieza parcelas en tablón urbanismo.
- **Limitación:** Solo anuncios vigentes; sin archivo histórico indexable.
- **SSL:** Certificado cadena incompleta → `insecure_ssl: true` en adapter.

### 3. Transparencia — Normas Subsidiarias (Tomo II)

- **URL:** `https://aytoquijorna.sedelectronica.es/transparency/c3bde2cb-3329-460a-9b0b-d02e55dc25f5/`
- **Contenido:** 10 capítulos (índice + caps. 1–10) con enlaces `preview-document/{uuid}`.
- **Uso:** Proyectos de planeamiento (NN.SS municipales).

### 4. Transparencia — Ordenanzas urbanísticas

- **URL:** `https://aytoquijorna.sedelectronica.es/transparency/ad88615a-a13d-4576-a91d-63050c8fc9f8/`
- **Contenido:** 8 ordenanzas (asoleo, estéticas, zonas verdes, aire acondicionado, etc.).

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| BOCM re-parse | Ya cubierto en pipeline regional |
| Consulta expedientes sede | Requiere Cl@ve/certificado |
| Dossiers transparencia vacíos (`07b48e79`, `f3a06c71`) | Sin documentos |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** SIT Comunidad de Madrid WFS `sitcm:VPLA_V_AMBITO`, filtro `DS_MUNICIPIO='QUIJORNA'` (27 ámbitos: UE-01…UE-21, S-01R…S-06I).
- **Estrategia:** Enriquecimiento post-scrape vía `geometry.enrichers` → `sitcm_ambito` en manifest; matching por códigos UE/S en título cuando existan.
- **Limitaciones:** PDFs normativos y guías de trámite no incluyen códigos de ámbito; tablón sin expedientes georreferenciados. Sin visor municipal propio.

## Estrategia de ingesta

- **proyectos.jsonl:** NN.SS transparencia + ordenanzas + guías tramitación + tablón sede filtrado.
- **licencias.jsonl:** guías tramitación (modelos licencia) + páginas informativas sede + tablón filtrado.
- **IDs:** `quijorna-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (40+ documentos normativos/trámites).
- `licencias`: partial (guías y trámites informativos; sin listado de concesiones con coordenadas).
- `with_geometry`: bajo (solo filas con código UE/S en título; mayoría centroid+jitter).
