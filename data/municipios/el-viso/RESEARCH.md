# El Viso — investigación portal ayuntamiento

**Municipio:** El Viso (Córdoba, Andalucía)  
**Slug:** `el-viso`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://ayto-elviso.com | **Operativa** — WordPress + Elementor |
| Sede electrónica | https://elviso.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://elviso.sedelectronica.es/board | **Operativa** — ~10 filas vigentes |
| Modelos solicitudes | https://ayto-elviso.com/modelos-de-solicitudes-varias/ | **Operativa** — PDFs licencia obra y DR urbanística |
| Bandos WP (API) | https://ayto-elviso.com/wp-json/wp/v2/posts?categories=4 | **Operativa** — 126 bandos (filtro urbanístico) |
| Catálogo trámites | https://elviso.sedelectronica.es/dossier | **Operativa** — SPA lenta en CI |
| Consulta expedientes | https://elviso.sedelectronica.es/expedientes | Requiere Cl@ve/certificado |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Vera, Tomares, Cártama.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Categoría urbanística:** «Licencias Urbanísticas» en varios anuncios vigentes.

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Expediente | Categoría | Descripción |
|-------|------------|-----------|-------------|
| — | 379/2025 | Licencias Urbanísticas | Proyecto actuación ampliación instalaciones ganaderas Hnos. Pedrajas |
| — | 379/2025 | Licencias Urbanísticas | Informe técnico exp. 379/2025 |
| — | — | Licencias Urbanísticas | BOP nº 141 (23/07/2026) — información pública actuación interés público suelo rústico |
| — | — | — | Ordenanza Fiscal Impuesto Construcciones, Instalaciones y Obras |

## WordPress (bandos y noticias)

- **CMS:** WordPress con REST API (`/wp-json/wp/v2/`).
- **Categoría bandos:** id=4, slug `bandos`, 126 entradas.
- **Filtro urbanístico:** anuncios BOP, ordenanzas fiscales de obras, actuaciones de interés público.
- **Sin sección dedicada** de planeamiento/PGOU en páginas estáticas del sitemap.

## Licencias de obra

- No hay dataset público de concesiones de licencia con coordenadas.
- Modelos descargables: «Solicitud Licencia de Obras» y «Declaración Responsable o Comunicación en Materia Urbanística» (PDFs en `/wp-content/uploads/`).
- Tablón sede publica documentación de expedientes en trámite (categoría Licencias Urbanísticas).
- Trámites de solicitud vía sede (`/dossier`); consulta de expedientes requiere autenticación.

## Proyectos / planeamiento

- **Tablón:** actuaciones de interés público, informes técnicos, ordenanzas fiscales de obras.
- **Bandos WP:** anuncios BOP (ordenanza ICIO, plan económico-financiero), actuaciones en suelo rústico.
- **SITUA:** visor regional Junta de Andalucía para consulta de planeamiento aprobado; sin enlace scrapeable expediente↔polígono.
- **BOJA:** 2 entradas históricas en CSV regional; no re-parseadas por el adapter.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - No hay visor urbanístico municipal ni WFS/ArcGIS con campo de expediente en ayto-elviso.com ni sede.
  - SITUA (`ws132.juntadeandalucia.es/situadifusion`) — planeamiento regional; sin query por código de expediente del ayuntamiento.
  - IDEAndalucía: datos cartográficos regionales sin enlace a expedientes municipales.
- **Estrategia:** no hay fuente GIS pública enlazable a expedientes del tablón. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin `geom_geojson` por proyecto.
  - Tablón con pocos anuncios vigentes (~10).
  - `/dossier` y raíz de sede lentos en CI (timeout >25s sin cookie).

## Limitaciones generales

- Sin listado histórico amplio de licencias concedidas.
- Portal web sin sección PGOU/planeamiento estructurada.
- Sede electrónica lenta en entornos CI sin sesión previa.

## Adapter implementado

- `municipio.adapters.el_viso:ElVisoAyuntamientoAdapter`
- Fuentes: tablón sede + bandos WP (API) + búsqueda WP + modelos PDF + referencia SITUA.
