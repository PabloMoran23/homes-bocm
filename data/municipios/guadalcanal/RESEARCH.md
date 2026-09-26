# Guadalcanal — investigación portal ayuntamiento

**Municipio:** Guadalcanal (Sevilla, Andalucía)  
**Slug:** `guadalcanal`  
**INE oficial:** 41049  
**CIF:** P4104800J (tablón/sede usan código 41048)  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.guadalcanal.es | **Operativa** — OpenCMS INPRO theme4 |
| Sede electrónica | https://sede.guadalcanal.es | **Operativa** — GSede OpenCMS (Guadaltel/INPRO) |
| Alias sede Diputación | https://sedeguadalcanal.dipusevilla.es | Redirige a sede.guadalcanal.es |
| Tablón INPRO | https://sede.guadalcanal.es/tablon-1.0/do/entradaPublica?ine=41048 | **Operativa** — 10 anuncios (sep 2026) |
| Transparencia | https://transparencia.guadalcanal.es | **Operativa** — portal INPRO separado |
| PGOU transparencia | https://transparencia.guadalcanal.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00017/ | **Operativa** — memoria, 8 planos, normas subsidiarias |
| Modificaciones PGOU | https://transparencia.guadalcanal.es/es/transparencia/indicadores-de-transparencia/indicador/Modificaciones-aprobadas-del-PGOU-y-los-Planes-parciales-aprobados-00017/ | **Operativa** — modificación puntual N°2 (2019) + EAE |
| Urbanismo (delegación) | https://www.guadalcanal.es/es/ayuntamiento/delegaciones/detalle/Urbanismo-Infraestructuras-Movilidad-y-Seguridad-Ciudadana/ | **Operativa** — noticias; sin listado expedientes |
| Licyt@l Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4104800J | **Operativa** — contratación local |

## CMS y formato de listados

- **Web:** OpenCMS INPRO (`es.inpro.opencms.*`), galerías en `/export/sites/guadalcanal/`.
- **Sede:** GSede 1.4 (módulos `gsede`, `sede`); tablón INPRO tablón-1.0 con tabla HTML `displaytag`; codificación **latin-1**.
- **Transparencia:** OpenCMS INPRO en subdominio propio; indicadores ITA con galerías PDF en `.galleries/IND-50-`, `IND-53-`.
- **Tablón web** (`/es/ayuntamiento/tablon-de-anuncios-electronico/`): **404** — el tablón activo está solo en la sede.

## Tablón electrónico INPRO

- Parámetro `ine=41048` (coincide con CIF, no con INE oficial 41049).
- 10 anuncios visibles (sep 2026): mayoría **Empleo** (7), **Exposición Pública** (2), **Bandos** (1).
- 2 exposiciones públicas (refs 682–683): convenio Colegio Veterinarios — clasificadas como urbanismo por asunto.
- Servlet detalle `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...` devuelve error en algunos anuncios.
- Paginación hasta página 8 pero solo 10 filas totales (histórico corto).

## Planeamiento / expedientes

| Tipo | Fuente | Notas |
|------|--------|-------|
| PGOU adaptación LOUA | Transparencia IND-50 | Memoria, anexo NNUU, 8 planos información |
| Normas subsidiarias | Transparencia IND-50/NORMAS-SUBSIDIARIAS | 2 PDFs |
| Modificación puntual N°2 | Transparencia IND-53 | EAE, estudio acústico, modificación (2019) |
| Exposición pública | Tablón sede | Convenio urbanístico (Colegio Veterinarios) |

## Licencias de obra

- No hay dataset público de concesiones de licencias urbanísticas.
- Sede GSede: catálogo de trámites sin listado histórico de expedientes concedidos.
- Licyt@l Diputación: contratación administrativa, no registro de licencias.
- Ordenanzas fiscales (ICIO) en transparencia — no son licencias concedidas.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal (ArcGIS, gvSIG, etc.).
  - PGOU y modificaciones solo en PDF raster en galerías transparencia (planos sin georreferencia WGS84).
  - SITUA Junta de Andalucía: sin capa consultable enlazada por expediente para este municipio.
  - Diputación Sevilla: sin WFS/ArcGIS por expediente.
- **Estrategia:** documentos PDF sin servicio GIS; no hay query por código de expediente.
- **Limitaciones:**
  - Planos son PDF/imagen, no WFS/GeoJSON.
  - Tablón sin geometría ni enlace a visor.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Municipio pequeño (Sierra Norte de Sevilla); histórico tablón corto y mayoritariamente administrativo.
- INE en tablón (41048) ≠ INE oficial (41049) — peculiaridad del ayuntamiento/CIF.
- Tablón web corporativo 404; fuente activa solo en sede.
- Sin licencias históricas publicadas; páginas informativas de trámites.

## Adapter implementado

- `municipio.adapters.guadalcanal:GuadalcanalAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + PDFs transparencia (PGOU, modificaciones, normas) + páginas informativas licencias.
- IDs: `guadalcanal-lic-*` / `guadalcanal-proy-*` (sha256[:14]).
