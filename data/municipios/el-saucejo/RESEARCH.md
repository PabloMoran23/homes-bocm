# El Saucejo — investigación portal ayuntamiento

**Municipio:** El Saucejo (Sevilla, Andalucía)  
**Slug:** `el-saucejo`  
**INE:** 41090 | **CIF:** P4109000B  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.elsaucejo.es | **Operativa** — OpenCMS INPRO theme4 |
| Urbanismo | https://www.elsaucejo.es/es/urbanismo/ | **Operativa** — noticias urbanismo |
| PGOU / PBOM | https://www.elsaucejo.es/es/ayuntamiento/pgou | **Operativa** — 26 PDFs (indicador transparencia IND-50) |
| Transparencia | https://www.elsaucejo.es/es/transparencia | **Operativa** — integrada en web INPRO |
| Sede electrónica | https://sedeelsaucejo.dipusevilla.es | **Operativa** — GSede OpenCMS (Guadaltel) |
| Tablón INPRO | https://sedeelsaucejo.dipusevilla.es/tablon-1.0/do/entradaPublica?ine=41090 | **Operativa** — ~110 edictos, 11 páginas |
| NSS Diputación | https://3web.dipusevilla.es/planeamiento/NSSaucejo/inicio-saucejo.htm | **Operativa** — Normas Subsidiarias (PDFs MO, NU, planos P1–P9) |
| LicytalPub | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4109000B | **Operativa** — consulta licencias (sin dataset scrapeable) |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41090 | **Operativa** — visor regional Junta de Andalucía |

## Tablón electrónico INPRO (sede Diputación)

- **CMS:** INPRO tablón-1.0 (Sociedad Provincial de Informática de Sevilla), INE `41090`.
- **Listado:** tabla HTML `displaytag` con columnas ocultas (referencia, asunto, URL servlet) y extracto/fecha.
- **Paginación:** parámetro `d-16544-p`; 11 páginas (~10 registros/página).
- **Documentos:** `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...`.
- **Contenido actual (sep 2026):** mayoría RRHH/bolsa de empleo/edictos fiscales; sin licencias de obra ni planeamiento reciente en tablón.

## PGOU y planeamiento

- **Vigente histórico:** Normas Subsidiarias (aprobación definitiva 17/11/2000, Diputación Sevilla).
- **En tramitación:** PGOU suspendido (2024); PBOM aprobación inicial abril 2026 en información pública.
- **PGOU web:** 26 PDFs en galería IND-50 (memoria, normas urbanísticas, planos ordenación/información, EsAE PBOM 2025, estudio acústico, inundabilidad).
- **NSS Diputación:** memoria, normas urbanísticas, planos P1–P9 (núcleo principal, Mezquitilla, término municipal).

## Licencias de obra

- No hay dataset público de concesiones scrapeable (LicytalPub requiere búsqueda interactiva).
- Las licencias publicadas aparecerían en tablón INPRO; histórico actual sin licencias de obra.
- Trámites urbanismo en sede vía ticket GSede (`area: URBANISMO`); sin catálogo público sin autenticación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PGOU/PBOM/NSS: planos en PDF raster (OpenCMS galería IND-50, 3web.dipusevilla.es) — sin GeoJSON/WFS.
  - SITUA Junta de Andalucía: visor regional con planeamiento digitalizado; sin API REST por expediente municipal.
  - LicytalPub: sin geometría de ámbito.
- **Estrategia:** documentos PDF sin georreferencia; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos son PDF/imagen, no servicios ArcGIS/WFS enlazables.
  - Tablón INPRO codificación ISO-8859-1.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Mayoría de edictos del tablón son RRHH/subvenciones (filtrado en adapter).
- Licencias: solo páginas informativas + tablón + LicytalPub (sin concesiones históricas scrapeables).
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.el_saucejo:ElSaucejoAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + PGOU web (IND-50) + NSS Diputación + SITUA metadata + páginas informativas licencias.
- IDs: `el-saucejo-lic-*` / `el-saucejo-proy-*` (sha256[:14]).
