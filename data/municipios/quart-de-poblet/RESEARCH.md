# Quart de Poblet — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web corporativa | https://quartdepoblet.es |
| Área urbanismo | https://quartdepoblet.es/areas/urbanismo |
| API Digital Value | https://api.digitalvalue.es/quartdepoblet/collections/articulos |
| PGE / catálogo protecciones | https://quartdepoblet.es/areas/urbanismo/articulo/catalogo-de-protecciones-plan-general-estructural |
| Plan parcial Molí d'Animeta | https://quartdepoblet.es/areas/urbanismo/articulo/plan-parcial-moli-d-animeta-aprobacion-definitiva-p-p-por-la-c-t-u-26-11-2010 |
| Sede electrónica | https://quartdepoblet.sedipualba.es |
| Tablón anuncios (RSS) | https://quartdepoblet.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites | https://quartdepoblet.sedipualba.es/catalogoservicios.aspx |
| Transparencia | https://quartdepoblet.es/PortadaTransparencia |

## CMS y listado de expedientes

- **Web:** Digital Value / ZityBuilder (Mithril.js + API REST `api.digitalvalue.es/quartdepoblet`). ~1150 artículos en colección `articulos`.
- **Proyectos:** artículos del área urbanismo (`categories: urbanismo`) con PDFs en `filesGroup`. URLs `/areas/urbanismo/articulo/{slug}`; ayuntamiento en `/ayuntamiento/articulos/{slug}`.
- **Tablón:** sedipualba ASP.NET con RSS funcional. Predominan anuncios de personal/subvenciones; pocos edictos urbanísticos recientes.
- **Licencias:** no hay registro público de concesiones. Solo ficha informativa URBA-5101 (informe urbanístico municipal) en catálogo sedipualba.

## Licencias de obra

- Trámite visible: **URBA-5101 Informe urbanístico municipal** (`idtramite=14267`).
- Sin dataset ni listado de licencias concedidas; el adapter devuelve páginas informativas de trámite + edictos del tablón filtrados por regex.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - ICV WFS `Planeamiento.Zonificacion` (misma base URL)
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`), paginación `STARTINDEX`
  - Filtro cliente: `cod_ine_mun=46104` (Quart de Poblet)
  - Sectores SU/SUZ detectados: **SECTOR SEQUIARS** (UE SEQUIARS)
  - Zonificación: 4 polígonos (normas subsidiarias, homologación sector industrial Sequiars)
- **Estrategia:** descargar features ICV como proyectos con polígono; enriquecer artículos web por coincidencia de tokens sectoriales (SEQUIARS, UE-, etc.)
- **Limitaciones:**
  - No hay visor municipal ArcGIS propio enlazado al expediente (gesquart.com es empresa pública de servicios, no GIS)
  - CQL_FILTER del WFS no funciona en servidor; requiere paginar ~12k features y filtrar por INE
  - Features ICV para cod_ine_mun=46104 **no incluyen geometría** en la respuesta GML (solo metadatos pp/ue/denominaci)
  - Licencias del tablón sin geometría explícita
  - API Digital Value ocasionalmente cierra conexión TLS (reintentos en adapter)

## Limitaciones generales

- Sede sedipualba: trámites requieren certificado digital para presentación; sin API de expedientes públicos
- Tablón mezcla urbanismo con personal, subvenciones, BOP administrativo (filtro por regex)
- Artículos de reciclaje/contenedores publicados bajo categoría urbanismo (excluidos por filtro ruido)
- BOCM regional: DOGV (2 entradas históricas en cola)
