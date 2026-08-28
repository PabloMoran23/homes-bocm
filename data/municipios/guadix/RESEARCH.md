# Guadix — investigación portal ayuntamiento

**Municipio:** Guadix (Granada, Andalucía)  
**Slug:** `guadix`  
**Boletín:** BOJA (`boja`, 2 entradas en histórico)  
**INE:** 18139

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://guadix.es | **Operativa** — WordPress + Elementor |
| Urbanismo y Patrimonio | https://guadix.es/urbanismo-patrimonio/ | **Operativa** — noticias + PDF memoria |
| Sede electrónica | https://guadix.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://guadix.sedelectronica.es/board | **Operativa** — ~10 filas vigentes |
| Portal transparencia | https://guadix.sedelectronica.es/transparency | **Parcial** — sección 7. URBANISMO (269 docs, AJAX Wicket) |
| Catálogo trámites | https://guadix.sedelectronica.es/dossier | Lenta en CI; sin listado histórico |
| Consulta expedientes | https://guadix.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| SITUA búsqueda | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional |
| SITUA PGOU Guadix | https://ws132.juntadeandalucia.es/situadifusion/pages/planeamientoGeneralCompartir.jsf | PGOU aprobado (cod. figura 3918, mun. 18089) |
| VITUA visor | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ | Visor cartográfico Junta |
| BOP Diputación Granada | https://bop.dipgra.es | Anuncios urbanismo publicados en BOP provincial |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Cártama, Cómpeta, Vera.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** ~10 anuncios vigentes (ago 2026); sin histórico amplio en primera página.

### Ejemplos urbanísticos encontrados (jul–ago 2026)

| Fecha | Expediente | Procedimiento | Descripción |
|-------|------------|---------------|-------------|
| 23/07/2026 | 3563/2022 | Planeamiento General | Innovación PGOU — incorporación nuevos terrenos zona Belerda |
| 26/08/2026 | 9156/2025 | Disposiciones Normativas | Ordenanza nominación y rotulación de calles y vías urbanas |

## Web municipal (WordPress)

- Sección **Urbanismo y Patrimonio** con noticias de actuaciones urbanísticas y enlace a memoria PDF (`Anexo-3-Memoria.pdf`).
- Noticias relevantes: Plan Especial del Casco Histórico (tramites municipales finalizados), Agenda Urbana, innovaciones PGOU (BOJA / BOP Dipgra).
- REST API `wp-json/wp/v2/posts` accesible para búsqueda por términos urbanísticos.

## Licencias de obra

- No hay dataset público de concesiones de licencia de obra con coordenadas.
- Trámites de solicitud vía sede `/dossier`; consulta de expedientes requiere Cl@ve.
- El adapter incluye páginas informativas del tablón, catálogo de trámites y departamento urbanismo web.

## Proyectos / planeamiento

- **Tablón:** innovación PGOU (exp. 3563/2022), ordenanzas urbanísticas.
- **Web:** Plan Especial Casco Histórico, Agenda Urbana, noticias de planeamiento.
- **SITUA:** PGOU Guadix aprobado (instrumento general vigente).
- **Transparencia:** 269 documentos en sección urbanismo; árbol requiere sesión Wicket AJAX (no scrapeable determinísticamente).
- **BOJA / BOP Dipgra:** modificaciones PGOU (PP6, casco histórico) — no re-parseadas por el adapter.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - VITUA (Junta de Andalucía): visor cartográfico de planeamiento municipal; sin enlace por código de expediente del tablón ayuntamiento.
  - SITUA/SITUADIFusión: documentación PGOU y figuras de planeamiento; sin query REST por expediente municipal.
  - Transparencia sede: PDFs sin georreferencia embebida.
- **Estrategia:** los anuncios del tablón y documentos web son PDF sin campo GIS enlazable. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Sin `geom_geojson` por expediente.
  - Transparencia urbanismo (269 docs) requiere navegación AJAX.
  - `/dossier` puede ser muy lento en CI.

## Limitaciones generales

- Tablón con pocos anuncios vigentes (~10).
- Sin listado histórico público de licencias concedidas.
- Transparencia urbanismo con árbol AJAX (269 docs).
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.guadix:GuadixAyuntamientoAdapter`
- Fuentes: tablón sede + web WordPress (REST + estáticos) + metadatos SITUA/VITUA.
- IDs: `guadix-lic-*` / `guadix-proy-*` (sha256[:14]).
