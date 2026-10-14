# Paterna de Rivera — investigación portal ayuntamiento

**Municipio:** Paterna de Rivera (Cádiz, Andalucía)  
**Slug:** `paterna-de-rivera`  
**INE:** 11025 · **BOJA:** 1 entrada en histórico regional  
**Perfil contratante Diputación:** entidad 414

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.paternaderivera.es | Operativa (Joomla + YOOtheme + Phoca Download) |
| Tablón de anuncios (web) | https://www.paternaderivera.es/tablon-de-anuncios | Phoca Download — categorías y PDFs |
| Contratos de obra | https://www.paternaderivera.es/tablon-de-anuncios/75-contratacion-obras | Histórico licitaciones/adjudicaciones obra pública |
| Plan vivienda y suelo | https://www.paternaderivera.es/tablon-de-anuncios/85-plan-municipal-de-vivienda-y-suelo-de-paterna-de-rivera | Categoría PMVS (poco contenido urbanístico directo) |
| Acuerdos — Comisión Urbanismo | https://www.paternaderivera.es/acuerdos-y-normativa/81-comision-informativa-de-urbanismo-y-medio-ambiente | Convocatorias comisión |
| Impresos licencias | https://www.paternaderivera.es/impresos-y-solicitudes/22-licencia-de-apertura | DR apertura / actividad |
| Portal transparencia | https://www.paternaderivera.es/portal-de-transparencia | Enlace corporativo |
| Sede electrónica | https://paternaderivera.sedelectronica.es | Operativa — espublico gestiona |
| Tablón sede | https://paternaderivera.sedelectronica.es/board | Tablón principal (HTML tabla) |
| SITU@ (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento aprobado regional |
| BOP Cádiz | https://bopcadiz.es/ | Boletín provincial |

**Nota:** `www.paternaderivera.es` devuelve 403 sin User-Agent de navegador (Plesk).

## Cómo se listan expedientes / proyectos

1. **Phoca Download (web):** enlaces `?download={id}:{slug}` en tablón, acuerdos e impresos. El adapter recorre semillas y subcategorías `pd-subcategory` (contratos de obra, comisión urbanismo, etc.).
2. **Tablón sede (`/board`):** filas con enlace `/preview-document/{uuid}` y metadatos en atributo `title` (expediente municipal, p. ej. `1959/2026`). Sin API JSON pública.
3. **SITU@:** instrumentos de planeamiento general aprobados a nivel autonómico (consulta por municipio INE 11025); no enlaza expedientes municipales concretos.

## Licencias de obra

- **No hay listado histórico** de licencias concedidas en web abierta.
- Formularios en `/impresos-y-solicitudes` (licencia apertura, licencias de obras vacía).
- Edictos puntuales pueden aparecer en tablón sede o Phoca (obra pública ≠ licencia urbanística privada).
- Adapter expone páginas informativas de sede + formularios + edictos del tablón si coinciden con patrones de licencia.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes evaluadas:**
  - **SITU@ / VITUA (Junta):** planeamiento general (listado); sin geometría por expediente municipal ni query por código de licencia.
  - **Callejero web** (`/turismo/callejero`): mapa WidgetKit/Google Maps; sin capas de ordenación ni enlace a expediente.
  - **Phoca PDFs:** documentos administrativos sin servicio WMS/WFS.
  - **Sede tablón:** solo metadatos textuales.
- **Estrategia:** sin visor urbanístico municipal; orquestador usará centroide `[36.5219, -5.8683]` + jitter.
- **Limitaciones:** urbanismo disperso en tablón de obras y comisiones; sin sección PGOU dedicada en la web actual.

## Limitaciones generales

- Tablón sede paginado; adapter captura página inicial.
- WAF en web corporativa requiere User-Agent identificable.
- Categoría «Plan Municipal de Vivienda y Suelo» mezcla contenido no urbanístico.
- Licencias históricas no publicadas como dataset.

## Adapter

- `municipio.adapters.paterna_de_rivera:PaternaDeRiveraAyuntamientoAdapter`
- IDs: `paterna-de-rivera-lic-*` / `paterna-de-rivera-proy-*` (sha256[:14]).
