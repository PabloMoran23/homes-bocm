# Alhama de Granada — investigación portal ayuntamiento

**Municipio:** Alhama de Granada (Granada, Andalucía)  
**Slug:** `alhama-de-granada`  
**Boletín:** BOJA (`boja`, 1 entrada en histórico)  
**INE:** 18013

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web municipal (WordPress) | https://news.alhamadegranada.info | **Operativa** — noticias, transparencia, urbanismo |
| Información urbanística | https://news.alhamadegranada.info/informacion-urbanistica/ | PDFs PGOU/SNU (Dropbox + uploads) |
| PGOU | https://news.alhamadegranada.info/pgou/ | Planos y memorias en Dropbox |
| PGOU 2014 | https://news.alhamadegranada.info/pgou-2014/ | Histórico planeamiento |
| Sede electrónica | https://alhamadegranada.sedelectronica.es | **Operativa** — espublico gestiona (`insecure_ssl`) |
| Tablón de anuncios | https://alhamadegranada.sedelectronica.es/board/ | Tabla HTML ~10 filas recientes |
| Transparencia sede | https://alhamadegranada.sedelectronica.es/transparency | Carpetas documentales (IP urbanística puntual) |
| Catálogo trámites | https://alhamadegranada.sedelectronica.es/dossier | Redirige a `/dossier.0` |
| Consulta expedientes | https://alhamadegranada.sedelectronica.es/expedientes | Requiere autenticación |
| CDAU | https://news.alhamadegranada.info/callejero-digital-de-andalucia-unificado-cdau-alhama-de-granada/ | Enlace informativo; sin visor propio |
| Punto catastral | https://news.alhamadegranada.info/punto-de-informacion-catastral/ | Oficina urbanismo; cartografía vía sedecatastro.gob.es |

## Tablón de anuncios (espublico gestiona)

- **CMS:** espublico gestiona (Wicket/Java), patrón Andalucía (Alcaucín, Cómpeta, Coín).
- **Listado:** tabla HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, `class_boardCategory`, `class_description`, `class_dateFrom`.
- **Documentos:** enlace `preview-document/{uuid}`.
- **Paginación:** solo primera página visible en HTML estático (~10 anuncios recientes).
- **Categorías urbanísticas observadas:** «Licencias Urbanísticas» (p. ej. aprobación definitiva proyecto actuación núcleo zoológico).

## Licencias de obra

- No hay dataset público histórico de concesiones con coordenadas.
- Trámites vía sede (`/dossier`, `/expedientes` con login).
- Edictos de licencias publicados en tablón cuando procede.
- El adapter incluye páginas informativas (tablón, catálogo sede, información urbanística).

## Proyectos / planeamiento

- **WordPress:** noticias filtradas sobre innovación PGOU, PEPRI BIC, variante A-402, información pública, alegaciones (REST `/wp-json/wp/v2/posts?search=...`).
- **Páginas estáticas:** `informacion-urbanistica`, `pgou`, `pgou-2014` con enlaces Dropbox (memorias, planos SNU/innovación) y PDFs en `wp-content/uploads`.
- **Tablón sede:** anuncios BOP/edictos de licencias y actuaciones urbanísticas.
- **Transparencia sede:** documentación puntual de información pública (p. ej. variante A-402 referenciada en noticias).

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes revisadas:**
  - CDAU / callejero digital Andalucía: sin capa WFS/ArcGIS enlazada al ayuntamiento.
  - Sede catastro (`sedecatastro.gob.es`): consulta parcela, no geometría de expediente municipal.
  - Documentación PGOU en Dropbox/PDF: planos raster sin API GeoJSON.
  - SITUA/VITUA Junta de Andalucía: planeamiento regional; sin query por código de expediente del tablón.
- **Estrategia:** no hay visor ArcGIS/WFS municipal accesible por código de expediente; el orquestador usará centroide municipio + jitter.
- **Limitaciones:** anuncios y documentos son PDF; tablón paginado AJAX; consulta expedientes requiere login.

## Limitaciones generales

- Web principal en subdominio WordPress (`news.alhamadegranada.info`), no `www.alhamadegranada.es`.
- Sede con certificado que requiere `insecure_ssl: true` en CI.
- Tablón muestra solo anuncios recientes.
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.alhama_de_granada:AlhamaDeGranadaAyuntamientoAdapter`
- Fuentes: tablón sede + páginas/documentos WordPress + noticias REST filtradas.
