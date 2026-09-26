# La Roda de Andalucía — investigación portal ayuntamiento

**Municipio:** La Roda de Andalucía (Sevilla, Andalucía)  
**Slug:** `la-roda-de-andalucia`  
**INE:** 41082  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.larodadeandalucia.es | **Operativa** — OpenCMS INPRO theme7 |
| Búsqueda urbanismo | https://www.larodadeandalucia.es/es/busqueda/?formCategoryFilter=/sites/larodadeandalucia/.categories/temas/urbanismo/&formTypeFilter=pm-noticia | **Operativa** — noticias categoría urbanismo (vacío sep 2026) |
| Ordenanzas municipales | https://www.larodadeandalucia.es/es/municipio/Ordenanzas-Municipales/ | **Operativa** — mayoría fiscales (IBI, ICIO, vehículos) |
| Transparencia | https://www.larodadeandalucia.es/.galleries/enlaces-servicios/transparencia | Enlace externo transparencia |
| Sede electrónica | https://sede.larodadeandalucia.es | **Operativa** — GSede OpenCMS (Guadaltel) |
| Tablón INPRO | https://sede.larodadeandalucia.es/tablon-1.0/do/entradaPublica?ine=41082 | **Operativa** — tabla displaytag HTML |
| NNSS Diputación Sevilla | https://3web.dipusevilla.es/planeamiento/82nsADenlaces.htm/Urbanismo.htm | **Operativa** — ~35 PDFs (memoria, normas, planos) |
| SITUA Junta Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf?cid=41082 | **Operativa** — consulta planeamiento regional |

## CMS y formato de listados

- **Web:** OpenCMS INPRO (`es.inpro.opencms.*`), galerías en `/export/sites/larodadeandalucia/`.
- **Sede:** GSede Guadaltel; trámites por ticket (`area: URBANISMO`); catálogo incluye «LICENCIA DE OBRA MENOR CON DECLARACIÓN RESPONSABLE».
- **Tablón:** INPRO tablón-1.0 en sede propia; tabla HTML `displaytag` con referencia/asunto/URL servlet; codificación ISO-8859-1.
- **Planeamiento:** HTML estático Diputación Sevilla (`3web.dipusevilla.es`) con enlaces PDF relativos.

## Tablón electrónico INPRO

- Escudo INPRO: `41082` (INE oficial).
- 10 edictos visibles (sep 2026): presupuesto, RRHH, tributos, subvenciones — **sin edictos urbanísticos** en el histórico actual.
- Filtro asunto `URBANISMO` disponible en combo del tablón.
- Documentos: `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...`

## Planeamiento / expedientes

| Tipo | Fuente | Notas |
|------|--------|-------|
| NNSS vigentes | Diputación Sevilla `82nsADenlaces.htm` | Aprobación definitiva CPOTU 5/3/2004; BOP 15/5/2004 |
| Adaptación LOUA | BOJA / BOP 2010 | Modificación sector Polígono Industrial Nudo Norte |
| Modificación puntual 2020 | BOJA 2023 | Vereda de Écija + sectorización I-II Fase 2 |
| PBOM en elaboración | Consulta pública 2022+ | Redacción adjudicada (T10 Team + jmmeléndez) |
| SITUA | Junta de Andalucía | Difusión documentación digitalizada NNSS |

### Documentos NNSS (Diputación Sevilla)

- `82NormSubs.pdf` — normas subsidiarias
- `RANSIU0.pdf` … `RANSI17.pdf` — planos de información y ordenación
- `RANSMO.pdf` — memoria
- `RANSanexoI-IV.pdf` — anexos (vías pecuarias, etc.)
- `RANSVP*.pdf`, `RANSO*.pdf` — planos complementarios

## Licencias de obra

- No hay dataset público de concesiones (LicytalPub / registro licencias no expuesto).
- Sede GSede: trámite informativo «LICENCIA DE OBRA MENOR CON DECLARACIÓN RESPONSABLE» (sin listado de expedientes concedidos).
- Tablón INPRO: sin licencias de obra en histórico actual.
- Ordenanzas web: impuesto construcciones (fiscal), no registro de licencias.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - NNSS/planos en PDF raster (`3web.dipusevilla.es`) — sin GeoJSON/WFS.
  - SITUA/VITUA Junta de Andalucía: documentación digitalizada sin query REST por expediente municipal.
  - Sin visor urbanístico municipal (ArcGIS, gvSIG) en web ni sede.
- **Estrategia:** documentos PDF sin georreferencia; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos NNSS son PDF/imagen escaneada, no servicios ArcGIS/WFS.
  - PBOM en elaboración sin geometría publicada.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Tablón INPRO codificación ISO-8859-1/latin-1.
- Mayoría de edictos del tablón son administrativos (RRHH, tributos, subvenciones).
- Sin sección urbanismo dedicada en web corporativa (solo categoría noticias).
- Licencias: solo páginas informativas de trámites sede + tablón vacío de urbanismo.

## Adapter implementado

- `municipio.adapters.la_roda_de_andalucia:LaRodaDeAndaluciaAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + NNSS Diputación Sevilla + SITUA + ordenanzas filtradas + noticias urbanismo.
- IDs: `la-roda-de-andalucia-lic-*` / `la-roda-de-andalucia-proy-*` (sha256[:14]).
