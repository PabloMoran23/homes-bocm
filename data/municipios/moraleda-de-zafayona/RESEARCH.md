# Moraleda de Zafayona — investigación portal ayuntamiento

**Municipio:** Moraleda de Zafayona (Granada, Andalucía)  
**Slug:** `moraleda-de-zafayona`  
**INE:** 18143  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.moraledadezafayona.es | **Operativa** — OpenCMS SAGA/Alhambra (Diputación Granada) |
| Plan de ordenación urbana | https://www.moraledadezafayona.es/ayuntamiento/plan-de-ordenacion-urbana/ | **Operativa** — galería PDF (consulta pública PGOU 2021, decretos) |
| Trámites e impresos | https://www.moraledadezafayona.es/ayuntamiento/tramites-e-impresos/ | **Operativa** — impresos U01–U13 + enlace dossier sede |
| Tablón web | https://www.moraledadezafayona.es/ayuntamiento/tablon-de-anuncios/ | Redirige a sede `/board/` |
| Sede electrónica | https://moraledadezafayona.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón de anuncios | https://moraledadezafayona.sedelectronica.es/board/ | **Operativa** — tabla HTML `preview-document` |
| Transparencia urbanismo | https://moraledadezafayona.sedelectronica.es/transparency/6adbe577-24f5-4e83-bcf9-c858e67a1d87/ | **Operativa** — sin documentos `preview-document` indexados (sept 2026) |
| Catálogo trámites | https://moraledadezafayona.sedelectronica.es/dossier.2 | Enlace desde web municipal (redirect Wicket) |
| Consulta expedientes | https://moraledadezafayona.sedelectronica.es/expedientes | Requiere autenticación Cl@ve |

## Cómo se listan expedientes

- **Web OpenCMS:** página POOU con galería de descargas (`/export/sites/MoraledaZafayona/.galleries/Plan-de-Ordenacion-Urbana-Documentos/*.pdf`).
- **Sede espublico:** tablón `/board/` con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`; documentos en `preview-document/{uuid}`.
- **Transparencia sede:** portal enlazado desde POOU; sin documentos visibles en HTML (sin enlaces preview).
- **Sept 2026:** tablón con anuncios de subvenciones escolares y jurado de personal; sin edictos urbanísticos recientes.

## Planeamiento (contexto portal, no re-parse BOCM)

- Procedimiento **avance y PGOU 2021**: edicto consulta pública y decreto de inicio publicados en galería POOU (oct 2021).
- Documento de contratación sector público (dic 2022) en misma galería.

## Licencias de obra

- No hay dataset público de concesiones con coordenadas.
- Formularios descargables en trámites (licencia obra mayor/menor, comunicaciones previas, tasas T01/T02).
- Trámites telemáticos vía sede `dossier.2`.
- Concesiones se publicarían en tablón cuando existan edictos.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - SITUA Junta: `https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=18143` — visor regional de planeamiento digitalizado; interfaz JSF sin API REST/WFS por código de expediente municipal.
  - Transparencia urbanismo sede: sin visor cartográfico ni capas descargables.
  - Web municipal: sin visor ArcGIS ni datos abiertos geoespaciales.
- **Estrategia:** consulta informativa SITUA; no hay enlace tablón/PDF → geometría queryable.
- **Limitaciones:**
  - Sin ArcGIS MapServer/WFS municipal.
  - Tablón y PDFs sin georreferencia.
  - El orquestador aplicará centroide municipio + jitter (`centroid` en manifest).

## Limitaciones generales

- Transparencia urbanismo sin documentos indexados en sede.
- Tablón paginado Wicket (adapter parsea primera página).
- Consulta expedientes requiere login.
- `dossier.2` puede responder con redirect lento en CI.

## Adapter implementado

- `municipio.adapters.moraleda_de_zafayona:MoraledaDeZafayonaAyuntamientoAdapter`
- Fuentes: metadata web/sede (POOU, transparencia, SITUA) + PDFs galería POOU + tablón sede filtrado.
- IDs: `moraleda-de-zafayona-lic-*` / `moraleda-de-zafayona-proy-*` (sha256[:14]).
