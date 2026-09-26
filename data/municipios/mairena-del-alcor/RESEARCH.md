# Mairena del Alcor — investigación portal ayuntamiento

**Municipio:** Mairena del Alcor (Sevilla, Andalucía)  
**Slug:** `mairena-del-alcor`  
**Boletín:** BOJA (`boja`, 3 entradas en histórico)  
**INE:** 41058

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.mairenadelalcor.es | **Operativa** — OpenCMS InPro (theme7) |
| Urbanismo | https://www.mairenadelalcor.es/es/urbanismo-y-medioambiente/ | Noticias urbanismo (paginadas) |
| Planeamiento (redirect) | https://www.mairenadelalcor.es/es/urbanismo-y-medioambiente/planeamiento-urbanistico | Redirige a portal transparencia IND-50 |
| PGOM (redirect) | https://www.mairenadelalcor.es/es/urbanismo-y-medioambiente/pgom | Redirige a pgom.mairenadelalcor.net |
| Portal transparencia Dipusevilla | https://transparencia.mairenadelalcor.es | **Operativa** — SagaSuite / Diputación Sevilla |
| IND-50 Planeamiento | https://transparencia.mairenadelalcor.es/es/transparencia/indicadores-de-transparencia/indicador/50.-Planeamiento-urbanistico-Planeamiento-General/ | **~83 PDFs** (NNSS, PGOU adaptación, fichas sectoriales) |
| Sede general | https://mairenadelalcor.sedelectronica.es | **Operativa** — espublico gestiona |
| Tablón general | https://mairenadelalcor.sedelectronica.es/board | **Operativa** — ~10 filas visibles |
| Sede urbanismo | https://urbanismomairenadelalcor.sedelectronica.es | **Operativa** — espublico dedicado |
| Tablón urbanismo | https://urbanismomairenadelalcor.sedelectronica.es/board | Vacío (ago 2026); licencias en tablón general |
| Transparencia sede | https://mairenadelalcor.sedelectronica.es/transparency | Sección «5. Transparencia… Urbanismo» (638 docs, AJAX) |
| Portal PGOM | https://pgom.mairenadelalcor.net | **Operativa** — WordPress Kubio; redacción nuevo PGOM |
| Documentación PGOM | https://pgom.mairenadelalcor.net/category/documentacion/ | Posts y PDFs fase participación |
| Licencias Diputación | https://portal.dipusevilla.es/LicytalPub/jsp/pub/index.faces?cif=P4105800E | Portal provincial LicytalPub |
| SITUA | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Planeamiento regional Junta de Andalucía |
| Consulta expedientes | https://urbanismomairenadelalcor.sedelectronica.es/expedientes | Requiere identificación |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), misma plataforma que Tomares, Cártama.
- **Listado:** tabla HTML con `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** `preview-document/{uuid}`.
- **Contenido actual (ago 2026):** mezcla plenos/personal/padrón; categoría **Urbanismo** con edictos de licencias de actividad (calificación ambiental).
- **Sede urbanismo dedicada:** tablón vacío; contenido urbanístico publicado en tablón general.

## Planeamiento / transparencia

- **IND-50 (Dipusevilla):** galerías OpenCMS con NNSS (1994/2013), documentos PGOU adaptación LOUA, fichas sectoriales (Cerro Trujillo, Camino Gandul, La Cebonera…), planos calificación suelo.
- **PGOM participación:** portal WordPress independiente con fases 1–8 redacción nuevo PGOM (subvención LISTA).
- **Sede transparencia:** 638 documentos urbanismo en árbol Wicket AJAX (no scrapeable determinísticamente; solo índice).

## Licencias de obra

- No hay dataset municipal histórico de concesiones.
- **Portal provincial:** Diputación de Sevilla LicytalPub CIF `P4105800E`.
- Edictos puntuales en tablón sede (licencias de actividad / calificación ambiental).
- Trámites vía sede urbanismo `/dossier` y `/expedientes` (autenticación).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - Sin visor urbanístico municipal (ArcGIS/WFS) en web, sede ni PGOM.
  - SITUA/VITUA (Junta de Andalucía): cartografía regional de planeamiento; sin enlace por expediente del tablón ni WFS REST accesible por código expediente.
  - Documentación IND-50 y PGOM son PDFs/planos sin georreferencia enlazable.
- **Estrategia:** documentos son PDF/listas HTML; el orquestador aplicará centroide municipio + jitter.
- **Limitaciones:**
  - Transparencia sede (638 docs) requiere Wicket AJAX para subcarpetas.
  - Portal LicytalPub provincial no scrapeable de forma determinista.
  - Sin `geom_geojson` en fuentes públicas del ayuntamiento.

## Limitaciones generales

- Tablón: solo primera página HTML (sin paginación visible).
- Transparencia sede: árbol AJAX; solo índice raíz scrapeado.
- OpenCMS urbanismo: muchas noticias no son expedientes (obras menores, mantenimiento).
- Consulta de expedientes requiere login.

## Adapter implementado

- `municipio.adapters.mairena_del_alcor:MairenaDelAlcorAyuntamientoAdapter`
- Fuentes: tablón sede (general + urbanismo) + PDFs IND-50 transparencia + portal PGOM + índice transparencia sede + SITUA + páginas informativas licencias.
- IDs: `mairena-del-alcor-lic-*` / `mairena-del-alcor-proy-*` (sha256[:14]).
