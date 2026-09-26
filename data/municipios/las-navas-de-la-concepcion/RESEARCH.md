# Las Navas de la Concepción — investigación portal ayuntamiento

**Municipio:** Las Navas de la Concepción (Sevilla, Andalucía)  
**Slug:** `las-navas-de-la-concepcion`  
**INE:** 41066  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.lasnavasdelaconcepcion.es | **Operativa** — OpenCMS INPRO theme7 |
| PGOU / planeamiento | https://www.lasnavasdelaconcepcion.es/es/ayuntamiento/pgou- | **Operativa** — edicto PGOU + adaptación NNSS (PDFs) |
| Normativa municipal | https://www.lasnavasdelaconcepcion.es/es/ayuntamiento/normativa | **Operativa** — enlaces transparencia ITA urbanismo |
| Transparencia | https://www.lasnavasdelaconcepcion.es/es/transparencia | **Operativa** — indicadores ITA (SagaSuite integrado) |
| Indicador PGOU | https://www.lasnavasdelaconcepcion.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00048/ | Indicador Ley Transparencia |
| Sede electrónica | https://sedenavasdelaconcepcion.dipusevilla.es | **Operativa** — GSede OpenCMS (Guadaltel) |
| Tablón INPRO | https://sedenavasdelaconcepcion.dipusevilla.es/tablon-1.0/do/entradaPublica?ine=41066 | **Operativa** — tabla displaytag HTML |
| NNSS Diputación (3web) | http://3web.dipusevilla.es/planeamiento/66PG%20Las%20Navas/66NSLasNavas.html | **Operativa** — memoria, normas y planos NNSS 1997 (PDF/TIF) |
| LicytalPub | https://portalag.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4106600A | Portal consulta licencias Diputación (sin dataset scrapeable) |
| Delegación Urbanismo | https://www.lasnavasdelaconcepcion.es/es/ayuntamiento/delegaciones/detalle/Delegacion-de-Urbanismo-00002/ | Informativa |

## Tablón electrónico INPRO (sede Diputación)

- **CMS:** INPRO tablón-1.0 (Sociedad Provincial de Informática de Sevilla), INE `41066`.
- **Listado:** tabla HTML `displaytag` con columnas ocultas (referencia, asunto, URL servlet) y extracto/fecha.
- **Paginación:** parámetro `d-16544-p`; ~6 registros visibles (sep 2026).
- **Contenido actual:** empleo (SEPE/funcionarios) y bandos; **sin edictos urbanísticos** en el histórico reciente.
- **Documentos:** `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...`.

## PGOU y planeamiento (web corporativa)

- Página PGOU con edicto y documentos de **adaptación de NNSS** al nuevo PBOM en tramitación:
  - `EDICTO_PGOU.pdf`
  - `Doc_Adapt_NNSS-min.1.pdf` … `Doc_Adapt_NNSS-min.4.pdf`
- **NNSS vigentes (1997):** memoria, normas urbanísticas y planos de ordenación en 3web Diputación (`66NSLasNavas*.pdf/tif`).
- PBOM en elaboración (diagnóstico Fase III publicado en galería noticias).

## Licencias de obra

- No hay dataset público de concesiones scrapeable (LicytalPub requiere consulta interactiva).
- Tablón INPRO sin licencias de obra en histórico actual.
- Trámites urbanismo en sede vía ticket GSede (`Delegación de Urbanismo`); sin catálogo scrapeable sin autenticación.
- Adapter incluye páginas informativas (tablón, sede, LicytalPub, transparencia).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - NNSS/planos en PDF/TIF raster (3web Diputación, galerías OpenCMS) — sin GeoJSON/WFS.
  - SITUA / visor Diputación Sevilla: sin endpoint REST público enlazable por expediente.
  - Junta de Andalucía SITUA/VITUA: planeamiento regional sin campo expediente del ayuntamiento.
- **Estrategia:** documentos PDF/TIF sin georreferencia; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos NNSS/PGOU son PDF/imagen, no servicios ArcGIS/WFS.
  - Tablón sin edictos urbanísticos recientes.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Tablón INPRO codificación ISO-8859-1/latin-1.
- Mayoría de edictos del tablón son empleo/bandos (filtrado en adapter).
- Licencias: solo páginas informativas + tablón (sin concesiones históricas scrapeables).
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.las_navas_de_la_concepcion:LasNavasDeLaConcepcionAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + PGOU web + NNSS 3web DipSevilla + normativa/transparencia + páginas informativas licencias.
- IDs: `las-navas-de-la-concepcion-lic-*` / `las-navas-de-la-concepcion-proy-*` (sha256[:14]).
