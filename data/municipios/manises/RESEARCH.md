# Manises — investigación portal ayuntamiento

**Municipio:** Manises (Valencia, Comunitat Valenciana)  
**Slug:** `manises`  
**Boletín:** DOGV (`dogv`, 1 entrada en histórico)  
**INE:** 46159

## URLs base y páginas semilla

| Fuente | URL | Estado |
|--------|-----|--------|
| Web corporativa | https://www.manises.es | **Operativa** — Drupal 10 Portales municipales |
| Urbanismo | https://www.manises.es/es/urbanisme/pagina/planeamiento | Hub planeamiento |
| Planeamiento estructural (PGOU) | https://www.manises.es/es/urbanisme/pagina/planeamiento-estructural | PDFs PGOU 1988 + modificaciones |
| Planeamiento pormenorizado | https://www.manises.es/es/urbanisme/pagina/planeamiento-pormenorizado | ~29 planes parciales/especiales (acordeón) |
| Revisión / info pública PGE | https://www.manises.es/es/urbanisme/pagina/revision-planeamiento-vigente-informacion-publica | PGE en información pública (2025) |
| Transparencia urbanística | https://www.manises.es/es/transparencia/informacion-urbanistica | PGOU + PGE + modificaciones |
| API Digital Value | https://api.digitalvalue.es/manises/collections/articulos | Artículos CMS (~1200+) |
| Sede electrónica | https://manises.sedipualba.es | **Operativa** — sedipualba (no espublico gestiona) |
| Tablón anuncios (RSS) | https://manises.sedipualba.es/tablondeanuncios/tablon_rss.aspx | **Operativo** — edictos licencia ambiental, etc. |
| Catálogo trámites | https://manises.sedipualba.es/catalogoservicios.aspx | Área Urbanismo (URB0001–URB0024) |
| Sede espublico | https://manises.sedelectronica.es | **Indeterminada** — selector de sede, sin datos |
| GIS municipal | https://gis.manises.es | Visor 3D interno (Bootstrap/Three.js); sin REST/ArcGIS público |

## CMS y listado de expedientes

- **Web:** Drupal 10 Portales + Digital Value (`api.digitalvalue.es/manises`). Matomo site 222.
- **Proyectos Drupal:** páginas de planeamiento con acordeones; cada sección expone `data-a2a-url` + `data-a2a-title` (p. ej. «PP Sector 1 1988», «PE 2007 Suelo Dotacional Hospital»).
- **API articulos:** categoría `urbanisme`; artículo reciente «MP 31 PGOU y MP 1 Plan Parcial El Comtat – Información Pública» (ago 2026) con PDFs en `filesGroup`.
- **Tablón:** sedipualba ASP.NET con RSS funcional. Mezcla personal/subvenciones con edictos urbanísticos (licencia ambiental, etc.).
- **Licencias:** no hay dataset público de concesiones. Trámites URB0019 (licencia de obra), URB0004 (ambiental), URB0009 (DR obra simplificada), etc. en catálogo sedipualba.

## Licencias de obra

- Trámites visibles en catálogo sedipualba área Urbanismo (URB0001–URB0024).
- Edictos del tablón: licencia ambiental (ej. C/ Marina Baixa, 4), sin registro histórico de concesiones.
- El adapter devuelve páginas informativas de trámite + edictos del tablón filtrados por regex.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - ICV WFS `ms:InventarioSuSuz` en `https://terramapas.icv.gva.es/0702_Planeamiento`
  - ICV WFS `Planeamiento.Zonificacion` (misma base URL)
  - Formato: GML3 (`outputFormat=GML3`, `srsName=EPSG:4326`), paginación `STARTINDEX`
  - Filtro cliente: `cod_ine_mun=46159` (Manises)
  - Sectores SU/SUZ detectados: **35** con polígono (SECTOR 1–3, UA 1–31, etc.)
  - Zonificación: 3 polígonos adicionales
  - GIS municipal `gis.manises.es`: visor 3D sin API REST enlazable a expedientes
- **Estrategia:** descargar features ICV como proyectos con polígono; enriquecer artículos Drupal/API por coincidencia de tokens sectoriales (SECTOR, UA, UE, etc.)
- **Limitaciones:**
  - CQL_FILTER del WFS no funciona en servidor; requiere paginar ~14k features y filtrar por INE
  - GIS municipal sin ArcGIS MapServer/WFS público
  - Licencias del tablón sin geometría explícita
  - Sede sedipualba: trámites requieren certificado digital; sin API de expedientes públicos

## Limitaciones generales

- `manises.sedelectronica.es` devuelve página de sede indeterminada (no usable).
- Tablón mezcla urbanismo con personal, subvenciones, formación (filtro por regex).
- Artículos de prevención incendios / comunicaciones bajo categoría urbanisme (excluidos por filtro ruido).
- BOCM regional: DOGV (1 entrada histórica en cola).

## Adapter implementado

- `municipio.adapters.manises:ManisesAyuntamientoAdapter`
- Fuentes: ICV WFS + páginas Drupal semilla + API Digital Value + tablón sedipualba + trámites informativos.
- IDs: `manises-lic-*` / `manises-proy-*` (sha256[:14]).
