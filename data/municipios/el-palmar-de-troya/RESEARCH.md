# El Palmar de Troya — investigación portal ayuntamiento

**Municipio:** El Palmar de Troya (Sevilla, Andalucía)  
**Slug:** `el-palmar-de-troya`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.elpalmardetroya.es | **Operativa** — OpenCMS INPRO theme7 |
| Urbanismo | https://www.elpalmardetroya.es/es/urbanismo/ | **Operativa** — sección con PGOU, noticias, proyectos de obras |
| Noticias urbanismo | https://www.elpalmardetroya.es/es/urbanismo/noticias/ | **Operativa** — listado OpenCMS paginado |
| PGOU (web) | https://www.elpalmardetroya.es/es/urbanismo/pgou | Página informativa (contenido en transparencia) |
| Sede electrónica | https://sede.elpalmardetroya.es | **Operativa** — GSede OpenCMS (Guadaltel) |
| Tablón INPRO | https://sede.elpalmardetroya.es/tablon-1.0/do/entradaPublica?ine=41996 | **Operativa** — tabla displaytag HTML (9 edictos ago 2026) |
| Portal transparencia | https://transparencia.elpalmardetroya.es | **Operativa** — SagaSuite INPRO |
| Indicador PGOU (IND-50) | https://transparencia.elpalmardetroya.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Esta-publicado-el-Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan.-00029/ | **Operativa** — ~15 PDFs PGOM (memoria, cartografía) |
| Indicador normativa (IND-56/83) | https://transparencia.elpalmardetroya.es/es/transparencia/indicadores-de-transparencia/indicador/56.-Se-publica-informacion-precisa-de-la-normativa-vigente-en-materia-de-gestion-urbanistica-del-Ayuntamiento.-00029/ | **Operativa** — ordenanzas urbanísticas PDF |
| Web PGOM | https://elpalmardetroya.nuevoplan.es/ | **Operativa** — portal consulta PGOM (NuevoPlan) |
| SITUA Junta | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41996 | **Operativa** — planeamiento regional (sin geometría por expediente) |

## Tablón electrónico INPRO (sede propia)

- **CMS:** INPRO tablón-1.0, INE `41996`.
- **Listado:** tabla HTML `displaytag` con columnas ocultas (referencia, asunto, URL servlet) y extracto/fecha.
- **Documentos:** `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...`
- **Histórico actual (sep 2026):** 9 edictos — RRHH, cobranza IBI, bases emergencia social; **sin licencias ni planeamiento** en el tablón activo.

## PGOM / planeamiento

- El municipio está en redacción/aprobación del **PGOM** (antes PGOU). Documentación publicada en transparencia (IND-50): memoria, diagnóstico, ordenación, cartografía (PDF multiparte).
- Noticia web: exposición pública del avance del PGOM.
- Portal `elpalmardetroya.nuevoplan.es` para consulta ciudadana del plan (HTML estático, sin API GIS pública).

## Licencias de obra

- No hay dataset público de concesiones (LicytalPub / registro licencias).
- Trámites urbanismo en sede vía ticket GSede (`area: URBANISMO`); sin catálogo scrapeable sin autenticación.
- Noticia 2020: resolución de alcaldía iniciando expediente de licencia de actividad con calificación ambiental (PDF adjunto en galería OpenCMS).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Cartografía PGOM en PDF raster (transparencia IND-50) — sin GeoJSON/WFS.
  - Portal NuevoPlan (`elpalmardetroya.nuevoplan.es`) — consulta documental, sin MapServer/ArcGIS accesible.
  - SITUA Junta (`cid=41996`) — difusión planeamiento regional, sin enlace por expediente municipal ni geometría descargable.
- **Estrategia:** documentos PDF sin georreferencia; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos/cartografía son PDF/imagen, no servicios ArcGIS/WFS.
  - Tablón sin edictos urbanísticos en el histórico actual.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Tablón INPRO codificación ISO-8859-1/latin-1.
- Mayoría de edictos del tablón son RRHH/subvenciones/fiscal (filtrado en adapter).
- Licencias: páginas informativas + noticia histórica 2020; sin registro de concesiones.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.el_palmar_de_troya:ElPalmarDeTroyaAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + PGOM PDFs transparencia + normativa urbanística + noticias urbanismo + metadatos SITUA/PGOM web + licencia noticia 2020.
- IDs: `el-palmar-de-troya-lic-*` / `el-palmar-de-troya-proy-*` (sha256[:14]).
