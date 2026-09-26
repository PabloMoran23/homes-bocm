# Aguilafuente — investigación portal ayuntamiento

Municipio: **Aguilafuente** (`aguilafuente`), provincia Segovia, Castilla y León. INE `40004`.

## URLs base y páginas semilla

| Fuente | URL |
|--------|-----|
| Web oficial (alias Liferay) | https://www.aguilafuente.es |
| Portal DipSegovia | https://www.dipsegovia.es/web/ayuntamiento-de-aguilafuente |
| Urbanismo | https://www.dipsegovia.es/web/ayuntamiento-de-aguilafuente/urbanismo |
| Sede electrónica (espublico) | https://aguilafuente.sedelectronica.es |
| Tablón / info pública | https://aguilafuente.sedelectronica.es/board , `/info` |
| Catálogo trámites | https://aguilafuente.sedelectronica.es/dossier |
| PLAI JCYL (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=004 |
| PLAI JCYL (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=004 |

## Proyectos / planeamiento

- **DipSegovia (Liferay):** sección Urbanismo enlaza al archivo PLAI JCYL (`municipio=004`, provincia 40).
- **PLAI JCYL:** tabla HTML con documentos aprobados (NUM, estudios de detalle por sector). Ejemplos: modificación NUM 1-2022, estudio de detalle sector La Chimenea.
- **IDECyL WFS:** capas `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito` filtradas por `n_mun = 'Aguilafuente'`. 11 sectores con polígono (El Pastel U2, La Chimenea U4, Carravieja U5, Palomar U1, desarrollos D1–D6, Sector A U6).
- **Sede tablón:** documentos PDF en `/preview-document/` (mayoría administrativos; sin expedientes urbanísticos detallados).

## Licencias de obra

- No hay dataset público de concesiones de licencias con coordenadas.
- El tablón de la sede publica anuncios generales (IAE, créditos); no listados estructurados de licencias urbanísticas.
- El catálogo de trámites (`/dossier`) incluye procedimientos de licencia/obra como páginas informativas.
- **Estrategia adapter:** filas informativas de trámites + cualquier anuncio del tablón que coincida con patrones de licencia.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_sectores` (principal), `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `CQL_FILTER=n_mun = 'Aguilafuente'`, `srsName=EPSG:4326`, `outputFormat=application/json`
  - Campos enlace: `n_sector`, `n_num_sect`, `c_id_sect` (p. ej. `40004U2`)
- **Estrategia:** descarga WFS por municipio; cruza títulos PLAI/tablón con nombre de sector (`La Chimenea`, `El Pastel`, etc.) para adjuntar `geom_geojson` en `proyectos.jsonl`.
- **Limitaciones:** geometría a nivel de sector/planeamiento, no por expediente individual; licencias sin polígono; tablón sin GIS; no hay visor ArcGIS propio del ayuntamiento.

## Limitaciones generales

- PLAI con pocos documentos publicados (2 aprobados visibles).
- Tablón sede con volumen bajo y contenido mayoritariamente no urbanístico.
- SSL sede: certificado gestionado por espublico (adapter usa `insecure_ssl` por compatibilidad con el patrón DipSegovia).
- Paginación PLAI estándar JCYL (15 filas/página).
