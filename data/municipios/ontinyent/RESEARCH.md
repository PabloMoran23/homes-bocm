# Ontinyent — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web corporativa | https://www.ontinyent.es |
| Área urbanismo | https://www.ontinyent.es/va/pagina/territori-urbanisme-patrimoni-transport-public-serveis-municipals-activitats-autoritzacions |
| Planeamiento aprobado | https://www.ontinyent.es/va/pagina/aprovats-definitivament-0 |
| Planes parciales / estudios detalle | `/va/pagina/plans-parcials`, `/va/pagina/estudis-detall` |
| PGOU y modificaciones | `/va/pagina/pla-general-ontinyent-2007-modificacions` |
| PRI / expropiaciones | páginas `projecte-*` bajo urbanismo |
| Registro programas actuación | `/va/pagina/registre-programes-dactuacio` |
| Sede electrónica | https://ontinyent.sedipualba.es |
| Tablón anuncios (RSS) | https://ontinyent.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites | https://ontinyent.sedipualba.es/catalogoservicios.aspx |

## CMS y listado de expedientes

- **Web:** Drupal 10 con módulos `digital_value` (tema portalesmunicipales.es). Sin JSON:API pública.
- **Proyectos:** páginas estáticas `/va/pagina/...` con PDFs en `/sites/www.ontinyent.es/files/`. Crawl por semillas urbanismo.
- **Tablón:** sedipualba ASP.NET; listado HTML + **RSS** (`tablon_rss.aspx`). Anuncios urbanísticos mezclados con otros edictos.
- **Licencias:** no hay registro público de concesiones; solo fichas de trámite sedipualba (certificado digital obligatorio) y edictos del tablón.

## Licencias de obra

- Trámites URBANISME en catálogo sedipualba: llicència d'obres, declaració responsable, primera ocupació, informes compatibilidad, etc.
- Sin dataset ni listado de licencias concedidas; el adapter devuelve páginas informativas de trámite + edictos del tablón filtrados.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`), paginación `STARTINDEX`
  - Filtro cliente: `cod_ine_mun=46184` (Ontinyent)
  - Campos: `pp` (plan parcial/sector), `ue` (unidad ejecución), `clasificacion` (SU/SUZ)
- **Estrategia:** descargar sectores SU/SUZ del inventario ICV como proyectos con polígono; enriquecer filas del tablón/Drupal por coincidencia de tokens sectoriales (SD-*, UE-*, etc.)
- **Limitaciones:**
  - No hay visor municipal ArcGIS enlazado al expediente
  - CQL_FILTER del WFS no funciona en servidor; requiere paginar ~5000 features y filtrar por INE
  - Licencias del tablón no tienen geometría explícita (solo match textual a sectores ICV)
  - Proyectos documentales (PRI, expropiación) sin enlace GIS directo

## Limitaciones generales

- Sede sedipualba: trámites requieren certificado digital; sin API de expedientes públicos
- Tablón mezcla urbanismo con subvenciones, igualdad, etc. (filtro por regex)
- Web ontinyent.es ocasionalmente resetea conexiones TLS (reintentos en adapter)
