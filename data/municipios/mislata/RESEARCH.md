# Mislata — investigación portal ayuntamiento

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web corporativa | https://www.mislata.es |
| Urbanismo (oficina virtual) | https://www.mislata.es/es/administracion/oficina-virtual/urbanismo |
| Transparencia urbanística | https://www.mislata.es/es/transparencia/informacion-urbanistica-y-medioambiental |
| Planeamientos urbanísticos | https://www.mislata.es/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos |
| PGOU | https://www.mislata.es/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos/plan-general-de-ordenacion-urbana |
| Planes en trámite | https://www.mislata.es/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos/planes-urbanisticos-en-tramite |
| Plano clasificación suelo | https://www.mislata.es/es/transparencia/informacion-urbanistica-y-medioambiental/planeamientos-urbanisticos/plano-de-clasificacion-del-suelo |
| Sede electrónica | https://mislata.sedipualba.es |
| Tablón anuncios (RSS) | https://mislata.sedipualba.es/tablondeanuncios/tablon_rss.aspx |
| Catálogo trámites | https://mislata.sedipualba.es/catalogoservicios.aspx |
| Geo-referencia catastral | https://www.mislata.es/es/transparencia/informacion-urbanistica-y-medioambiental/consulta-online-de-geo-referencia-catastral |

## CMS y listado de expedientes

- **Web:** Drupal 9 (módulo `digital_value/ayuntamiento`, tema portales municipales). Codificación ISO-8859-1 en varias páginas.
- **Proyectos:** páginas de transparencia con subsecciones PGOU (Plan General, edictos de modificación 2012–2017, proyecto urbanización/integración paisajística), plano clasificación suelo y planes en trámite (vacío en crawl).
- **API Digital Value:** `api.digitalvalue.es/mislata/collections/articulos` devuelve 0 artículos — no usable.
- **Tablón:** sedipualba ASP.NET con RSS funcional. Últimos 20 ítems son personal/subvenciones; sin edictos urbanísticos recientes.
- **Licencias:** no hay registro público de concesiones. Trámites URB.* y OBS.* en catálogo sedipualba (licencia edificación, obra mayor, DR, demolición, primera ocupación, etc.).

## Licencias de obra

- Trámites visibles en sedipualba: URB.076 Licencia de edificación, URB.077 Obra mayor, URB.049 DR con proyecto, URB.081 Demolición, URB.209/264 Primera ocupación, OBS.035 DR sin proyecto, etc.
- Sin dataset ni listado histórico de licencias concedidas; el adapter devuelve páginas informativas de trámite + referencia al tablón RSS.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - ICV WFS `Planeamiento.Zonificacion` (misma base URL)
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`), paginación `STARTINDEX`
  - Filtro cliente: `cod_ine_mun=46169` (Mislata; ICV usa 46169, no 46154)
  - Sectores detectados: Plan general, Homologación Les Vinyes, Sector Quint I/II, Villarrasa, El Paquillo (~21 SU/SUZ + ~12 zonificación, todos con polígono)
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
  - Consulta catastral municipal (enlace transparencia; no WFS expediente)
- **Estrategia:** descargar features ICV como proyectos con polígono; enriquecer páginas transparencia por coincidencia de tokens sectoriales (Quint, Villarrasa, Vinyes, Paquillo, PGOU)
- **Limitaciones:**
  - No hay visor municipal ArcGIS propio enlazado al expediente
  - CQL_FILTER del WFS no funciona; requiere paginar ~12k features y filtrar por INE
  - Tablón sedipualba sin edictos urbanísticos recientes
  - `mislata.sedelectronica.es` responde «Sede indeterminada»; sede real es sedipualba
  - API Digital Value vacía para este municipio

## Limitaciones generales

- Sede sedipualba: trámites requieren certificado digital para presentación; sin API de expedientes públicos
- Tablón mezcla urbanismo con personal, subvenciones, cementerio (filtro por regex)
- Planes en trámite: sección vacía en transparencia (2026-09)
- BOCM regional: DOGV (1 entrada histórica en cola)
