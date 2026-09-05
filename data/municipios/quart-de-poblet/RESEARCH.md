# Quart de Poblet — investigación portal ayuntamiento

**Municipio:** Quart de Poblet (Valencia, Comunitat Valenciana)  
**Slug:** `quart-de-poblet`  
**INE:** 46120  
**Boletín:** DOGV (`dogv`, 2 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web oficial | https://www.quartdepoblet.es | **Operativa** — Zity Builder / DigitalValue |
| API contenidos | https://api.digitalvalue.es/quartdepoblet | **Operativa** — REST JSON (`articulos`, `areas`, …) |
| Área urbanismo | https://www.quartdepoblet.es/es/desarrollo-urbano-sostenible | **Operativa** — artículos de planeamiento |
| Sede electrónica | https://quartdepoblet.sedipualba.es | **Operativa** — Sedipualba ASP.NET |
| Tablón de anuncios | https://quartdepoblet.sedipualba.es/tablondeanuncios/ | **Operativa** |
| Tablón RSS | https://quartdepoblet.sedipualba.es/tablondeanuncios/tablon_rss.aspx | Feed RSS (iso-8859-1) |
| Catálogo trámites urbanismo | https://quartdepoblet.sedipualba.es/catalogoservicios.aspx?area=1537&ambito=1 | Solo trámites informativos |
| Transparencia | https://zity-dashboard.digitalvalue.es/webs/transparencia/?realm=quartdepoblet | Portal transparencia Zity |

## Cómo se listan expedientes / proyectos

- **CMS:** Zity Builder (DigitalValue) con API `api.digitalvalue.es/quartdepoblet/collections/articulos`.
- **Categoría:** artículos con `categories: ["urbanismo"]` (~23 de 1157 totales).
- **Contenido relevante:** PGE/PGOU, modificaciones puntuales, plan parcial Molí d'Animeta, catálogo de protecciones, información pública.
- **Ruido filtrado:** artículos de reciclaje (contenedores), subvenciones IVACE/polígonos, gestión de residuos.
- **Tablón sede:** edictos y anuncios administrativos; pocos urbanísticos recientes en RSS.

## Licencias de obra

- No hay registro público de concesiones de licencia.
- Catálogo sede urbanismo: un trámite informativo (`URBA-5101 Informe urbanístico municipal`).
- Licencias aparecen en tablón solo cuando el ayuntamiento publica edictos (no hay dataset).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV GVA WFS `terramapas.icv.gva.es/0702_Planeamiento` capa `ms:InventarioSuSuz`, filtro cliente `cod_ine_mun=46120`.
  - 5 sectores SU/SUZ con polígonos: UNIDAD DE EJECUCIÓN CALVARI-BOBALAR-CAMI REIAL, SALUDADOR, BOBALAR SAU-I, PENYA LLISA, SAN PIO V.
  - Mapas uMap embebidos en área urbanismo (contenedores, árboles) — no enlazados a expedientes.
  - Sin visor urbanístico municipal ArcGIS propio.
- **Estrategia:** paginación WFS por `STARTINDEX` (200 en 200), merge por keywords en título (sector, UE, plan parcial).
- **Limitaciones:**
  - CQL_FILTER del servidor WFS no filtra por INE → paginación costosa (~60 s).
  - Artículos DigitalValue y tablón sin geometría embebida; solo matching por nombre de sector.
  - No hay coords por expediente de licencia.

## Limitaciones generales

- Tablón RSS con encoding iso-8859-1 y contenido mayoritariamente administrativo (empleo, fiestas).
- API DigitalValue sin filtro por sección urbanismo en query; se filtra por categoría en cliente.
- Provincia en cola BOCM aparece como nombre del municipio; provincia real: Valencia.

## Adapter implementado

- `municipio.adapters.quart_de_poblet:QuartDePobletAyuntamientoAdapter`
- Fuentes: API DigitalValue + ICV WFS + tablón RSS Sedipualba + trámites informativos sede.
- IDs: `quart-de-poblet-lic-*` / `quart-de-poblet-proy-*` (sha256[:14]).
