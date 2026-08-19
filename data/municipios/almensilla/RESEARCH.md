# Almensilla — investigación portal ayuntamiento

**Municipio:** Almensilla (Sevilla, Andalucía)  
**Slug:** `almensilla`  
**Boletín:** BOJA (`boja`, 3 entradas en histórico)

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.almensilla.es | **Operativa** — OpenCMS INPRO theme7 |
| PGOU | https://www.almensilla.es/es/ayuntamiento/pgou/ | **Operativa** — ~86 PDFs (memoria, planos, índices) |
| Normativa municipal | https://www.almensilla.es/es/ayuntamiento/normativa-municipal/ | **Operativa** — ordenanzas/tasas urbanísticas |
| Tablón web | https://www.almensilla.es/es/ayuntamiento/tablon-de-anuncios/ | **Operativa** — listado Solr `pm-anuncio` (JS) |
| Sede electrónica | https://sedealmensilla.dipusevilla.es | **Operativa** — GSede OpenCMS (Guadaltel) |
| Tablón INPRO | https://sedealmensilla.dipusevilla.es/tablon-1.0/do/entradaPublica?ine=41010 | **Operativa** — tabla displaytag HTML |
| Portal transparencia | https://transparencia.almensilla.es | **Operativa** — SagaSuite Diputación Sevilla |
| Indicador PGOU transparencia | https://transparencia.almensilla.es/es/transparencia/indicadores-de-transparencia/indicador/Plan-General-de-Ordenacion-Urbana-PGOU-y-los-mapas-y-planos-que-lo-detallan-00040/ | Indicador Ley Transparencia (sin PDFs directos en HTML) |
| Multimedia Diputación | http://multimedia.dipusevilla.es/almensilla/documentos/ | PDFs PGOU enlazados desde web |
| POTAUS | https://www.almensilla.es/es/ayuntamiento/potaus/ | Página informativa (sin documentos) |

## Tablón electrónico INPRO (sede Diputación)

- **CMS:** INPRO tablón-1.0 (Sociedad Provincial de Informática de Sevilla), INE `41010`.
- **Listado:** tabla HTML `displaytag` con columnas ocultas (referencia, asunto, URL servlet) y extracto/fecha.
- **Paginación:** parámetro `d-16544-p`; 25 registros en 3 páginas (10+10+5).
- **Documentos:** `/tablon-1.0/servlet/obtenerAnuncio?idAnuncio=...` y URL permanente por hash.
- **Asuntos urbanismo:** código 205 «PLANEAMIENTO URBANÍSTICO»; también edictos en «OTROS» (plan parcial).

### Ejemplos urbanísticos (ago 2026)

| Ref | Asunto | Extracto |
|-----|--------|----------|
| 404 | OTROS | Consulta pública previa — avance plan parcial sector SUZs-8 |

## PGOU y planeamiento (web corporativa)

- Página PGOU con índices y enlaces a PDFs en `opencms/export/...` y `multimedia.dipusevilla.es/almensilla/documentos/`.
- Contenido: memoria, normas urbanísticas, catálogo, planos de información y ordenación (clasificación, sectores, redes).
- Aprobación inicial PGOU publicada en BOP nº 260 (9/11/2019).

## Licencias de obra

- No hay dataset público de concesiones (LicytalPub / registro licencias Diputación no expuesto para Almensilla).
- Las licencias publicadas aparecerían en tablón INPRO; en el histórico actual (25 edictos) no hay licencias de obra.
- Trámites urbanismo en sede vía ticket GSede (`area: URBANISMO`); sin catálogo scrapeable sin autenticación.

## Geometría / visor

- **geometry_status:** `unavailable`
- **Fuentes:**
  - PGOU/planos en PDF raster (`multimedia.dipusevilla.es`, OpenCMS galleries) — sin GeoJSON/WFS.
  - SITUA / visor Diputación Sevilla: sin endpoint REST público enlazable por expediente (404 en rutas probadas).
  - Junta de Andalucía SITUA/VITUA: planeamiento regional sin campo expediente del ayuntamiento.
- **Estrategia:** documentos PDF sin georreferencia; no hay query GIS por código de expediente.
- **Limitaciones:**
  - Planos PGOU son PDF/imagen, no servicios ArcGIS/WFS.
  - Tablón web usa Solr vía JavaScript (no replicado; sede INPRO cubre edictos).
  - El orquestador aplicará centroide municipio + jitter.

## Limitaciones generales

- Tablón INPRO codificación ISO-8859-1/latin-1 en algunas respuestas.
- Mayoría de edictos del tablón son RRHH/subvenciones (filtrado en adapter).
- Licencias: solo páginas informativas + tablón (sin concesiones históricas scrapeables).
- Sin geometría por expediente.

## Adapter implementado

- `municipio.adapters.almensilla:AlmensillaAyuntamientoAdapter`
- Fuentes: tablón INPRO sede + PGOU web + normativa urbanística filtrada + páginas informativas licencias.
- IDs: `almensilla-lic-*` / `almensilla-proy-*` (sha256[:14]).
