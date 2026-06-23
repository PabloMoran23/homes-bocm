# Villanueva del Pardillo — investigación portal ayuntamiento

**Municipio:** Villanueva del Pardillo (Comunidad de Madrid)  
**Fecha:** 2026-06-23  
**BOCM regional (referencia):** 30 avisos

## Resumen

Villanueva del Pardillo publica planeamiento en la **web corporativa Joomla** y anuncios administrativos en la **sede electrónica eHome** (espublico / `sedelectronica.es`):

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Normativa urbanística | `https://www.vvapardillo.org/normativa-urbanistica` | Joomla + ~71 PDFs | Proyectos (PGOU, SUZ, planes parciales) |
| Trámites urbanismo | `https://www.vvapardillo.org/tramites/urbanismo` | Joomla (formularios) | Licencias informativas |
| Tablón sede | `https://sede.vvapardillo.org/board/` | HTML tabla eHome | Proyectos/licencias (anuncios vigentes) |
| Sede electrónica | `https://sede.vvapardillo.org/` | eHome Wicket | Trámites telemáticos |
| Transparencia sede | `https://sede.vvapardillo.org/transparency/68d77b07-…/` | Wicket/AJAX | Sección 7 Urbanismo (docs vía JS; no scrapeado) |
| Portal transparencia web | `https://www.vvapardillo.org/portal-de-transparencia` | Joomla | Enlaces a sede |

## Fuentes detalladas

### 1. Web corporativa — Normativa urbanística (Joomla)

- **URL:** `https://www.vvapardillo.org/normativa-urbanistica`
- **Contenido:** PGOU (normativa + planos), modificaciones puntuales, PEPRI, sectores A–D, SUZ I/II (planes parciales), plan especial infraestructuras (fotovoltaica).
- **PDFs:** `https://www.vvapardillo.org/images/doc/ordterritorio/...`
- **Subpáginas:** `/suz-i-10-las-vegas` (sector retirado temporalmente por anulación judicial).

### 2. Sede electrónica eHome — Tablón de anuncios

- **URL:** `https://sede.vvapardillo.org/board/`
- **Formato:** Tabla HTML: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
- **Enlaces:** `preview-document/{uuid}` por fila.
- **Limitación:** ~10 anuncios vigentes; sin histórico indexable por GET.
- **SSL:** Certificado Firmaprofesional no verificado en CI → `sede_insecure_ssl: true`.

### 3. Trámites urbanismo (licencias)

- **URL:** `https://www.vvapardillo.org/tramites/urbanismo`
- **Contenido:** Formularios PDF (obra mayor/menor, declaraciones responsables, actividades, segregación, etc.).
- **No hay** listado público de licencias concedidas con coordenadas.

### 4. Consulta de expedientes

- **URL:** `https://sede.vvapardillo.org/expedientes` — requiere identificación Cl@ve/certificado.

### 5. Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| `sector_geometry/madrid_*` | Pipeline Madrid capital — fuera de alcance |
| Visor SIT Comunidad Madrid | Planeamiento regional; sin enlace a expedientes municipales |
| Transparencia sede (AJAX) | Documentos cargados por JavaScript; sin API pública |
| BOCM re-parse | Ya cubierto en pipeline regional |

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:** No hay visor urbanístico municipal ni WFS/ArcGIS con campo de expediente. El ayuntamiento publica planos en PDF estático. El Visor SIT de la Comunidad de Madrid (`idem.madrid.org`) muestra planeamiento aprobado a nivel regional pero sin vínculo scrapeable expediente↔polígono.
- **Estrategia:** Sin `geom_geojson` en adapter; el orquestador aplica centroide municipal + jitter en geocode.
- **Limitaciones:** Solo PDFs sin georreferencia; consulta de expedientes con certificado digital.

## Estrategia de ingesta

- **proyectos.jsonl:** PDFs normativa urbanística + tablón sede filtrado (urbanismo/BOCM/planeamiento).
- **licencias.jsonl:** Páginas trámites urbanismo + tablón sede filtrado (licencia/obra).
- **IDs:** `villanueva-del-pardillo-{lic|proy}-{sha256[:14]}`.
- **source:** `ayuntamiento`.

## Paridad esperada

- `proyectos`: ok (~71 PDFs planeamiento + anuncios tablón si aplican).
- `licencias`: partial (trámites informativos; sin concesiones georreferenciadas).
- `with_geometry`: 0 (geometry_status unavailable).
