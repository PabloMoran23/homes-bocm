# Láchar — investigación portal ayuntamiento

**Municipio:** Láchar (Granada, Andalucía)  
**Slug:** `lachar`  
**INE:** 18128  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.lachar.es | **Operativa** — OpenCMS SAGA/Alhambra (Diputación Granada) |
| Plan de ordenación urbana | https://www.lachar.es/ayuntamiento/plan-de-ordenacion-urbana/ | **Operativa** — texto informativo POU/PGOU; enlace a sede transparencia |
| Trámites e impresos | https://www.lachar.es/ayuntamiento/tramites-e-impresos/ | **Operativa** — enlace a dossier sede |
| Tablón web | https://www.lachar.es/ayuntamiento/tablon-de-anuncios-00001 | Redirige a sede `/board/` |
| Sede electrónica | https://lachar.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://lachar.sedelectronica.es/board/ | **Operativa** — tabla HTML preview-document |
| Transparencia urbanismo | https://lachar.sedelectronica.es/transparency/4dea4596-b4ae-4c99-9b87-94184e7adb83/ | **Operativa** — secciones 7.1–7.5 con **0 documentos** |
| Catálogo trámites | https://lachar.sedelectronica.es/dossier.1 | **Lento/timeout** en CI; enlace desde web municipal |
| Consulta expedientes | https://lachar.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |
| Ordenanzas | https://www.lachar.es/ayuntamiento/ordenanzas/ | Sin PDFs urbanísticos enlazados en listado |

## Cómo se listan expedientes

- **Web OpenCMS:** páginas informativas (POOU, trámites); sin listado de expedientes ni PDFs de planeamiento en la web.
- **Sede espublico:** tablón `/board/` con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`; documentos en `preview-document/{uuid}`.
- **Transparencia sede:** portal estructurado por indicadores (7. URBANISMO); actualmente vacío (0 docs en 7.1–7.5).
- **Sept 2026:** tablón dominado por empleo público, subvenciones e IAE; sin anuncios urbanísticos recientes.

## Planeamiento conocido (contexto BOJA, no re-parseado)

- PGOU aprobado definitivamente **26/03/2003** (Comisión Provincial OTU).
- Normas urbanísticas publicadas en BOJA **2020/208/69** (27/10/2020) por requerimiento Junta.
- Innovación n.º 1 Normas Subsidiarias Peñuelas (recalificación industrial→residencial) en BOJA **2022/220/95**.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Trámites vía sede (`/dossier.1`) y formularios en web municipal.
- Licencias concedidas se publicarían en tablón cuando existan edictos.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA Junta: `https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=18128` — visor regional; sin REST/WFS con geometría por expediente.
  - Portal transparencia urbanismo: vacío; sin visor cartográfico municipal.
  - Diputación Granada (`dipgra.es`): gestiona web OpenCMS; sin visor urbanístico propio enlazado.
- **Estrategia:** SITUA permite consulta de planeamiento digitalizado a nivel autonómico, pero no expone polígonos queryables por código de expediente del tablón. Los anuncios son PDF sin georreferencia.
- **Limitaciones:**
  - Sin ArcGIS MapServer/WFS municipal.
  - Tablón sin coordenadas ni enlace GIS.
  - `/dossier` inestable (timeout) en CI.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Transparencia urbanismo sin documentos publicados.
- Tablón paginado Wicket (adapter parsea primera página).
- Consulta expedientes requiere login.
- Web municipal sin descarga directa de normativa PGOU (referencia histórica vía BOJA).

## Adapter implementado

- `municipio.adapters.lachar:LacharAyuntamientoAdapter`
- Fuentes: metadata web/sede (POOU, transparencia, SITUA) + tablón sede filtrado.
- IDs: `lachar-lic-*` / `lachar-proy-*` (sha256[:14]).
