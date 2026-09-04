# Vejer de la Frontera — investigación portal ayuntamiento

**Municipio:** Vejer de la Frontera (Cádiz, Andalucía)  
**Slug:** `vejer-de-la-frontera`  
**INE:** 11039 · **BOJA:** 2 entradas en histórico regional  
**Diputación transparencia:** `entidadId=2201`

## URLs base y páginas semilla

| Recurso | URL | Estado |
|---------|-----|--------|
| Web corporativa | https://www.vejer.es | Operativa (Joomla 4/5 + YOOtheme + Phoca Download, EPICSA) |
| Urbanismo | https://www.vejer.es/es/ayuntamiento/urbanismo | Operativa — árbol Phoca Download |
| PGOU 2016 (tramitación) | https://www.vejer.es/es/pgou-2016 | Archivo completo PGOU 2016 (EAE negativa dic 2024) |
| Anuncios web | https://www.vejer.es/es/convocatorias/anuncios | Tablón secundario |
| Sede electrónica | https://vejerdelafrontera.sedelectronica.es | Operativa — espublico gestiona (Indra eHome, ~jul 2026) |
| Tablón de anuncios | https://vejerdelafrontera.sedelectronica.es/board | Tablón principal |
| Transparencia sede | https://vejerdelafrontera.sedelectronica.es/transparency | Sección 7 Urbanismo vacía |
| Catálogo trámites | https://vejerdelafrontera.sedelectronica.es/dossier | Formularios (sin listado histórico) |
| Transparencia Diputación | https://gobiernoabierto.dipucadiz.es/catalogo-de-informacion-publica?entidadId=2201 | Urbanismo vacío |
| SITUA (Junta) | https://ws132.juntadeandalucia.es/situadifusion/pages/search.jsf | Visor planeamiento regional |
| VITUA (Junta) | https://www.juntadeandalucia.es/institutodeestadisticaycartografia/visores/VITUA/ | Visor urbanístico regional |
| BOP Cádiz | https://bopcadiz.es/ | Boletín provincial |

**Nota:** `vejer.es` bloquea peticiones sin User-Agent de navegador (WAF Plesk → 403).

## Cómo se listan expedientes / proyectos

1. **Web urbanismo (Phoca Download):** categorías bajo `/es/ayuntamiento/urbanismo/`:
   - `/14-planeamiento/` — PGOU, NNSS, PEPRICH, planes especiales El Palmar
   - `/220-proyectos-de-actuacion/` — proyectos activos (Faveranga SL, etc.)
   - `/288-ed-aip-3-plaza-de-la-paz-ii/` — AIP + estudios de detalle
   - `/155-modificado-proyecto-urbanizable-suo-1-buenavista/` — SUO-1 Buenavista
   - `/169-aip-1-calle-santiago/`, `/172-aip-2-plaza-de-la-plaza-de-la-paz/`
   - Enlaces `?download={id}:{slug}` → PDF directo
2. **Tablón sede (`/board`):** tabla HTML Wicket con columnas Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha. Enlaces a `/preview-document/{uuid}`. Paginación AJAX «Mostrar más» (solo primera página scrapeada).
3. **PGOU 2016:** archivo completo en `/es/pgou-2016` (memoria, planos, normas) — tramitación fallida (EAE negativa dic 2024).
4. **Planeamiento vigente (Junta):** NNSS 2000 + adaptación parcial LOUA 2009.

## Licencias de obra

- **No hay listado público** de licencias concedidas.
- El tablón sede publica edictos puntuales (códigos expediente tipo `1497/2026`, `JGL/2026/13`).
- Trámites en `/dossier` (licencia obra mayor/menor, DR urbanística) — solo formularios.
- Transparencia Diputación y sede: sección urbanismo **vacía**.
- Adapter devuelve páginas informativas de referencia + edictos del tablón si aparecen.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes evaluadas:**
  - **VITUA / SITUA (Junta):** instrumentos de planeamiento regional (LISTA); no enlazables a código de expediente municipal.
  - **Mapea4 callejero** (`/es/turismo/callejero`, `locality=11039`): calles/direcciones EPSG:25830, sin polígonos de expediente.
  - **IDECádiz** (`dipucadiz.es/idecadiz`): infraestructura provincial, sin capas de ordenación para Vejer.
  - **Phoca PDF planos:** raster PDF @ 1:2000, sin servicio GIS.
  - **Sede tablón:** campo `expediente` texto, sin coordenadas.
- **Estrategia:** sin visor municipal enlazable; el orquestador aplicará centroide municipal + jitter (`centroid: [36.2519, -5.9631]`).
- **Limitaciones:** planeamiento publicado como PDF; sin ref. catastral sistemática en listados HTML; transparencia vacía; PGOU 2016 sin aprobar.

## Limitaciones generales

- Tablón paginado (10 filas visibles); adapter captura página actual.
- WAF en `vejer.es` requiere User-Agent de navegador.
- Sede nueva (~jul 2026); histórico limitado en tablón.
- Licencias históricas no publicadas en web abierta.
- SSL sede: certificado válido; `insecure_ssl: true` por consistencia con otros adapters espublico.

## Adapter

- `municipio.adapters.vejer_de_la_frontera:VejerDeLaFronteraAyuntamientoAdapter`
- IDs: `vejer-de-la-frontera-lic-*` / `vejer-de-la-frontera-proy-*` (sha256[:14]).
