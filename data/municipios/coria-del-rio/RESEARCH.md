# Coria del Río — investigación portal ayuntamiento

**Municipio:** Coria del Río (Sevilla, Andalucía)  
**Slug:** `coria-del-rio`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 41034 · **CIF:** P4103400J

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.coriadelrio.es | **Operativa** — OpenCMS INPRO theme4 |
| PGOM (portal municipal) | https://www.coriadelrio.es/es/ciudadania/page-00001/ | **Operativa** — enlace a web externa del plan |
| PGOM web informativa | https://nuevoplandecoriadelrio.es/ | **Protegida** — captcha SiteGround (302 desde web) |
| Normas subsidiarias | https://www.coriadelrio.es/es/ciudadania/normas-subsidiarias-municipales/ | **Operativa** — ~19 PDF/ZIP (memorias, sectores) |
| Plan biodiversidad urbana | https://www.coriadelrio.es/es/ciudadania/plan-de-biodiversidad-urbana/ | **Operativa** — PDF PBUC |
| Formularios licencias | https://www.coriadelrio.es/es/ayuntamiento/formularios-disponibles/ | **Operativa** — modelos DR, CP, licencia apertura |
| Sede electrónica | https://sede.coriadelrio.es | **Operativa** — GSede OpenCMS (Guadaltel/EPICSA) |
| Tablón INPRO | https://sede.coriadelrio.es/tablon-1.0/do/entradaPublica?ine=41034 | **Operativa** — tabla displaytag HTML |
| LicytalSede (licencias) | https://sedeelectronicadipusevilla.es/LicytalSede/jsp/index.faces?cif=P4103400J | **Operativa** — portal provincial Diputación Sevilla |
| Portal transparencia | https://transparencia.coriadelrio.es | **Operativa** — SagaSuite Diputación Sevilla |
| Indicador normativa | https://transparencia.coriadelrio.es/es/transparencia/indicadores-de-transparencia/indicador/Se-publica-la-Normativa-municipal-tanto-del-Ayuntamiento-como-de-los-Entes-instrumentales-Relacion-de-normativa-en-curso-Ordenanzas-y-texto-en-version-inicial-memorias-e-informes-de-elaboracion-de-las-normativas.-00019/ | Ordenanzas PDF (incl. info pública alteración términos 3.3.26) |
| SITUA Junta Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Consulta planeamiento regional (sin API por expediente ayto.) |
| BOP Sevilla | https://bopsevilla.dipusevilla.es | Boletín provincial |

## Tablón electrónico INPRO (sede municipal)

- **CMS:** INPRO tablón-1.0 (Sociedad Provincial de Informática de Sevilla), INE `41034`.
- **Listado:** tabla HTML `displaytag` con columnas ocultas (referencia, asunto, URL servlet) y extracto/fecha.
- **Paginación:** parámetro `d-16544-p`; ~20 registros en 2 páginas (10+10).
- **Documentos:** `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...`
- **Asuntos urbanismo:** «Trámite de información pública de expediente administrativo» (p. ej. alteración términos ordenanza, vía pecuaria VP/358/2025).

### Ejemplos urbanísticos (sep 2026)

| Ref | Asunto | Extracto |
|-----|--------|----------|
| 2061 | Trámite info. pública | Vía pecuaria Cañada Real Sevilla-Isla Menor — VP/358/2025 |
| — | Transparencia | Resolución apertura info. pública alteración términos 3.3.26 |

## PGOM y planeamiento (web corporativa)

- Página PGOM con enlace externo a `nuevoplandecoriadelrio.es` (web dedicada al nuevo PGOM; captcha en acceso automatizado).
- **Normas subsidiarias:** PDFs en `.galleries/DOCUMENTOS-general/` (memorias ordenación/informativa/definitiva, sectores 1-7, unidades).
- **Plan biodiversidad urbana:** PDF `pbucr2025.pdf` en galería documentos.
- Noticias municipales sobre convenio urbanístico Finca La Estrella (zona industrial SE-40) — no replicadas (portal de noticias).

## Licencias de obra

- **LicytalSede** Diputación Sevilla (`P4103400J`) — consulta provincial de licencias (enlace oficial en sede).
- No hay dataset histórico scrapeable de concesiones en la web del ayuntamiento.
- **Formularios:** declaración responsable obras, ocupación/cambio uso, comunicaciones previas, licencia apertura (PDFs descargables).
- Las licencias publicadas aparecerían en tablón INPRO; en el histórico actual no hay licencias de obra concedidas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PGOM/planos en PDF y ZIP (`DOCUMENTOS-general/ns*.pdf`) — sin GeoJSON/WFS.
  - Web externa PGOM (`nuevoplandecoriadelrio.es`) — captcha; sin API pública.
  - SITUA/VITUA Junta de Andalucía — consulta regional sin campo expediente del ayuntamiento enlazable.
  - LicytalSede — puntos de licencia provincial sin polígono de ámbito por expediente de planeamiento.
- **Estrategia:** documentos PDF/ZIP sin georreferencia; no hay query GIS por código de expediente municipal.
- **Limitaciones:**
  - Planos PGOM son PDF/imagen, no servicios ArcGIS/WFS.
  - Tablón INPRO codificación ISO-8859-1/latin-1.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Mayoría de edictos del tablón son RRHH/deportes/personal (filtrado en adapter).
- Licencias: páginas informativas + LicytalSede + tablón (sin concesiones históricas scrapeables).
- PGOM externo bloqueado por captcha para scraping automatizado.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.coria_del_rio:CoriaDelRioAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + PGOM/NSSS PDFs + normativa transparencia + SITUA + páginas informativas licencias.
- IDs: `coria-del-rio-lic-*` / `coria-del-rio-proy-*` (sha256[:14]).
