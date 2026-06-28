# Valdemoro — investigación portal ayuntamiento

**Municipio:** Valdemoro (Comunidad de Madrid)  
**Fecha:** 2026-06-23  
**BOCM regional (referencia):** 28 avisos

## Resumen

Valdemoro publica urbanismo y licencias en una **sede electrónica Liferay** (`sede.valdemoro.es`) separada de la web corporativa (`www.valdemoro.es`). No hay listado abierto de concesiones de licencia con coordenadas; el tablón electrónico mezcla anuncios administrativos (muchos de empleo público) con algún contenido urbanístico. La documentación de planeamiento (PGOU, catálogo, planos) está en PDF estático.

| Fuente | URL | Formato | Uso en adapter |
|--------|-----|---------|----------------|
| Sede — tablón electrónico | `https://sede.valdemoro.es/tablon-electronico` | Liferay asset publisher (HTML, ~392 anuncios paginados) | Proyectos/licencias filtrados |
| Sede — consulta pública | `https://sede.valdemoro.es/consulta-publica` | Liferay content | Exposiciones públicas |
| Sede — PGOU / planos | `https://sede.valdemoro.es/plan-general-de-valdemoro`, `/tomo-v-planos`, `/planos`, `/fichero-del-catalogo-de-bienes-protegidos` | PDF en `/documents/` | Proyectos (planeamiento) |
| Sede — trámites urbanismo | `https://sede.valdemoro.es/tramites-vivienda-urbanismo` | Liferay asset publisher | Licencias informativas |
| Web corporativa | `https://www.valdemoro.es/vivienda-urbanismo` | Liferay (informativo) | Referencia; sin listados scrapeables |

## Fuentes detalladas

### 1. Tablón electrónico (Liferay 6.1)

- **Listado:** `tablon-electronico` con portlet `101_INSTANCE_5eNJAxVOlRs5`, 25 ítems/página, 16 páginas (~392 resultados).
- **Estructura:** cada ítem es `<div class="asset-full-content">` con `<h1>` título y enlaces PDF en `<div class="resumen">`.
- **Subsecciones:** `tablon-de-anuncios` (duplica anuncios), `tablon-edictos` (casi vacío: notarías/jurado).
- **Urbanismo en tablón:** convenios urbanísticos, exposiciones públicas, ordenanzas de tasas urbanísticas, padrones de vados; la mayoría son procesos selectivos (filtrados).

### 2. Planeamiento (PGOU y documentación)

- **Plan General:** aprobado definitivamente (revisión 2004, publicaciones BOCM 2004–2009). Página informativa sin descarga directa en índice.
- **Tomo V planos:** 4 PDF (`0-0.pdf`, `CL.0`–`CL.2`) — clasificación y calificación.
- **Planos casco histórico:** `/planos` — 4 PDF (C1–C4 delimitación/zona arqueológica).
- **Catálogo bienes protegidos:** `/fichero-del-catalogo-de-bienes-protegidos` — ~61 PDF por zona.
- **Planes parciales:** `/planes-parciales` — índice sin PDFs directos en HTML (enlaces a visores externos).
- **Tomos VI–VIII:** páginas índice; documentos en subpáginas o solo presencial.

### 3. Trámites de licencias (informativos)

Catálogo en `tramites-vivienda-urbanismo` (portlet `oIxCS9QHJHAO`): Licencia de Obra Mayor/Menor, Información Urbanística, Primera Ocupación, Declaración responsable, vados, segregación, etc. Son fichas procedimentales, **no** concesiones publicadas.

### 4. Consulta pública

- `consulta-publica` — exposiciones de expedientes presupuestarios/plan económico (2 activos en junio 2026). Útil como proyectos tipo «exposición pública».

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - `sede.valdemoro.es/visor-consulta-publica-1` y `-2`: páginas vacías (sin mapa embebido).
  - `sede.valdemoro.es/visor-anuncio-publico-1`: iframe a SharePoint (`aytovaldemoro-my.sharepoint.com`), no API ArcGIS ni WFS.
  - PGOU/planos: solo PDF sin georreferencia scrapeable.
  - [Visor SIT Comunidad de Madrid](https://www.comunidad.madrid/medio-ambiente/sistema-informacion-territorial-visor-sit): planeamiento municipal refundido, **sin enlace por expediente** del ayuntamiento.
- **Estrategia:** el orquestador aplicará centroide municipal + jitter (`geocode`).
- **Limitaciones:** sin visor ArcGIS/WFS público enlazable a expedientes; documentación cartográfica en PDF estático.

## Limitaciones

| Limitación | Impacto |
|------------|---------|
| Tablón con mucho ruido (empleo público) | Filtro regex + exclusión de procesos selectivos |
| Sin dataset de licencias concedidas | `licencias.jsonl` = trámites informativos + padrones vados |
| PDFs sin coords | `with_geometry: 0` esperado |
| `www.valdemoro.es/c` devuelve 403 a algunos user-agents | Usar `sede.valdemoro.es` como base del adapter |
| Ciberataque mayo 2026 (decretos suspensión plazos) | Documentado en tablón; no bloquea scrape |

## Fuentes descartadas

| Fuente | Motivo |
|--------|--------|
| BOCM regional (`projects.json`) | Fuera de alcance (ya ingestado) |
| Pipeline Madrid (`sector_geometry/madrid_*`) | Fuera de alcance |
| Visor SIT CM | Planeamiento genérico, sin ID expediente ayuntamiento |

## Estrategia de ingesta

- **proyectos.jsonl:** tablón filtrado + PDFs PGOU/planos/catálogo + consulta pública + página plan general.
- **licencias.jsonl:** trámites sede (obra mayor/menor, etc.) + tablón (padrones vados, licencias en anuncios).
- **IDs:** `valdemoro-{lic|proy}-{sha256[:14]}`
- **source:** `ayuntamiento`

## Paridad esperada

- `proyectos`: ok (PGOU PDFs + tablón urbanístico + consulta pública)
- `licencias`: partial (trámites informativos; sin concesiones)
- `with_geometry`: 0 (`geometry_status: unavailable`)
