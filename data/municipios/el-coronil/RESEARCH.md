# El Coronil — investigación portal ayuntamiento

**Municipio:** El Coronil (Sevilla, Andalucía)  
**Slug:** `el-coronil`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 41036

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.elcoronil.es | **Operativa** — OpenCMS/Guadaltel |
| Sede electrónica | https://sede.elcoronil.es | **Operativa** — GSede OpenCMS |
| Tablón INPRO (Dip. Sevilla) | https://sedeelectronicadipusevilla.es/tablon-1.0/do/entradaPublica?ine=41036 | **Operativa** — tabla displaytag HTML |
| Tablón sede (espejo) | https://sede.elcoronil.es/tablon-1.0/do/entradaPublica?ine=41036 | **Operativa** — mismo contenido |
| Portal transparencia | https://transparencia.elcoronil.es | **Operativa** — SagaSuite Diputación Sevilla |
| Indicador urbanismo (50) | https://transparencia.elcoronil.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Instrumentos-de-ordenacion-urbanistica/ | **Operativa** — ~178 PDFs PGOU/PBOM/planes |
| Ordenanzas | https://www.elcoronil.es/es/ayuntamiento/ordenanzas/ | **Operativa** |
| PBOM participación | https://nuevoplanelcoronil.es | **Bloqueado** — captcha SiteGround (redirect desde web) |
| SITUA Junta Andalucía | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | **Operativa** — visor regional (sin enlace por expediente) |

## Tablón electrónico INPRO (Diputación Sevilla)

- **CMS:** INPRO tablón-1.0 (Sociedad Provincial de Informática de Sevilla), INE `41036`.
- **Listado:** tabla HTML `displaytag` con columnas ocultas (referencia, asunto, URL servlet) y extracto/fecha.
- **Paginación:** sin paginación visible (8 registros en primera página, sep 2026).
- **Documentos:** `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...` vía sede Diputación.

### Ejemplos urbanísticos (sep 2026)

| Ref | Asunto | Extracto |
|-----|--------|----------|
| 709 | EDICTOS | Aprobación definitiva Modificación Puntual nº 9 — Ampliación Centro de Salud |

## Proyectos / planeamiento (transparencia)

- **PGOU 2012:** memoria, normas urbanísticas, planos de información y ordenación (galería `PGOU2012/`).
- **PBOM:** anuncio BOP nº 124 (plan básico ordenación municipal) + documentación en transparencia.
- **Plan parcial sector Los Molinos (PP-4):** memoria, normas, planos, resolución aprobación.
- **Estudio de detalle sector San Ignacio:** memoria y planos.
- **Modificación puntual nº 9 (2025-2026):** acuerdo pleno, publicación BOP, diligencia.
- **Normas subsidiarias 1991** y documentación TIP 2014 (ORYP/BOJA).

## Licencias de obra

- No hay dataset público de concesiones (LicytalPub / registro licencias Diputación no expuesto para El Coronil).
- Trámites urbanismo en sede vía ticket GSede; sin catálogo scrapeable sin autenticación.
- Las licencias publicadas aparecerían en tablón INPRO; en el histórico actual no hay licencias de obra.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Transparencia y web: planos PGOU/PBOM/sectores en PDF raster — sin GeoJSON/WFS.
  - SITUA/VITUA (Junta de Andalucía): visor regional de planeamiento general; sin campo expediente del ayuntamiento ni query REST por código (`/rest/municipio/41036` → 404).
  - Sin visor urbanístico municipal ArcGIS/WFS enlazado a expedientes.
- **Estrategia:** documentos PDF sin georreferencia machine-readable; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos son PDF/imagen, no servicios ArcGIS/WFS.
  - Portal PBOM (`nuevoplanelcoronil.es`) protegido por captcha.
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Tablón INPRO codificación ISO-8859-1/latin-1.
- Mayoría de edictos del tablón son bandos administrativos (filtrado en adapter).
- Licencias: solo páginas informativas + tablón (sin concesiones históricas scrapeables).
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.el_coronil:ElCoronilAyuntamientoAdapter`
- Fuentes: tablón INPRO + transparencia indicador 50 (PDFs urbanismo) + ordenanzas web + SITUA metadata + páginas informativas licencias.
- IDs: `el-coronil-lic-*` / `el-coronil-proy-*` (sha256[:14]).
