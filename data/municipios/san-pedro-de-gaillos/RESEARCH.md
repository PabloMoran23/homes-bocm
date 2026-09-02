# San Pedro de Gaíllos — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). El ayuntamiento publica su web en la plataforma **Liferay de la Diputación de Segovia** (`dipsegovia.es`). La **sede electrónica** es **espublico gestiona** (`sanpedrodegaillos.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal Liferay (DipSegovia) | https://www.dipsegovia.es/web/ayuntamiento-de-san-pedro-de-gaillos |
| Urbanismo | https://www.dipsegovia.es/web/ayuntamiento-de-san-pedro-de-gaillos/urbanismo |
| Tablón municipal (web) | https://www.dipsegovia.es/web/ayuntamiento-de-san-pedro-de-gaillos/tablon-de-anuncios |
| Sede electrónica | https://sanpedrodegaillos.sedelectronica.es |
| Tablón sede | https://sanpedrodegaillos.sedelectronica.es/board |
| Transparencia sede | https://sanpedrodegaillos.sedelectronica.es/transparency |
| Trámites (catálogo) | https://sanpedrodegaillos.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=184 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=184 |

## Expedientes / planeamiento

- **Urbanismo en web DipSegovia:** página informativa del servicio de asistencia a municipios; sin listado HTML de expedientes en curso.
- **PLAI JCYL:** tabla HTML paginada con documentos de planeamiento aprobado (NS municipal 2001, modificación puntual 2003, modificación NS 2023 sobre franjas de protección en suelo rústico). Código municipio PLAU: **184** (provincia 40).
- **Tablón sede:** tabla HTML Wicket con anuncios de padrón fiscal, IAE, IBI y bandos (influenza aviar). Sin licencias ni expedientes urbanísticos en agosto 2026.
- **Sin visor municipal propio** ni CMS local con expedientes IP.

## Licencias de obra

- Trámites en sede espublico (`/dossier`); el catálogo puede responder lento (~90 s).
- No hay listado público de licencias concedidas con coordenadas.
- El adapter incluye páginas informativas de trámites cuando el dossier responde.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'San Pedro de Gaíllos'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature: Normas Subsidiarias de Planeamiento Municipal)
  - `urbanismo:plau_cyl_planes_parciales` (0 features)
  - `urbanismo:plau_cyl_sectores` (0 features)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título en filas PLAI.
- **Limitaciones:** sin visor ArcGIS municipal; sin sectores/UE en WFS; licencias sin polígono; tablón sin urbanismo.

## Limitaciones generales

- Dominio propio del municipio no operativo; portal vía DipSegovia.
- Sede `/dossier` puede responder muy lento; el adapter tolera timeout.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
