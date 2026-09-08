# Atarfe — investigación portal ayuntamiento

**Municipio:** Atarfe (Granada, Andalucía)  
**Slug:** `atarfe`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 18010

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.atarfe.es | **Operativa** (HTTP 500 en cabecera pero HTML servido) — CMS PHP Porto/Bootstrap |
| Urbanismo | https://www.atarfe.es/urbanismo | Operativa — noticias y enlaces relacionados |
| Anuncios plenos | https://www.atarfe.es/anuncios-plenos-municipales | Operativa |
| Noticias | https://www.atarfe.es/noticias | Operativa — listado extenso (~1,8 MB HTML) |
| Sede electrónica | https://atarfe.sedelectronica.es | **Operativa** — espublico gestiona (requiere `insecure_ssl`) |
| Tablón de anuncios | https://atarfe.sedelectronica.es/board | Operativa — tabla HTML con preview-document |
| Ordenanzas fiscales | https://atarfe.sedelectronica.es/transparency/43805ba8-ae16-47ec-b379-184d3b166287/ | Operativa — ICIO/IBI |
| Instancia genérica | https://atarfe.sedelectronica.es/info.0 | Operativa |
| Perfil contratante | http://atarfe.sedelectronica.es/contractor-profile-list | Operativa |
| Consulta expedientes | https://atarfe.sedelectronica.es/expedientes | Requiere autenticación (redirect loop sin login) |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Antas, Vera, Tomares.
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** ~10 filas visibles en primera carga.

### Ejemplos urbanísticos encontrados (ago 2026)

| Fecha | Documento | Procedimiento |
|-------|-----------|---------------|
| 03/08/2026 | BOP Nº 146 Aprobación constitución Junta de Compensación SI-2 | Licencias Urbanísticas |

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites informativos vía sede (`/info.0`) y transparencia (ordenanzas ICIO).
- Edictos de licencias publicados en tablón cuando existen (p. ej. Junta de Compensación).

## Proyectos / planeamiento

- **Web municipal:** artículos slug-based (`/recurso-casacion-tribunal-supremo-urbanizacion-medina-elvira-atarfe`, ordenanzas ICIO/IBI, obras urbanización).
- **Anuncios plenos:** convocatorias con contenido urbanístico ocasional.
- **Tablón sede:** BOP y resoluciones urbanísticas.
- **SITUA:** visor regional Junta de Andalucía para consulta de planeamiento (sin API WFS accesible desde CI).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA: `https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf` — página de búsqueda operativa; WFS GeoServer (`situa:ambitos_planeamiento`) no responde desde entorno agente.
  - Web municipal: sin visor ArcGIS/WFS enlazado a expedientes.
  - Tablón y noticias: PDFs y HTML sin georreferencia embebida.
- **Estrategia:** no hay MapServer/FeatureServer consultable por código de expediente. El orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Consulta de expedientes requiere login.
  - Web responde HTTP 500 en cabecera (contenido accesible).
  - Muchas noticias con «urbanización» se refieren a barrios residenciales, no planeamiento.

## Limitaciones generales

- Sin geometría por expediente.
- Histórico de licencias concedidas no publicado como listado estructurado.
- `/expedientes` inaccesible sin autenticación.

## Adapter implementado

- `municipio.adapters.atarfe:AtarfeAyuntamientoAdapter`
- Fuentes: tablón espublico + crawl web (urbanismo/anuncios/noticias filtradas) + metadata SITUA.
