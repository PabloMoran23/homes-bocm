# Real Sitio de San Ildefonso — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León), INE **40181**. El ayuntamiento publica su web corporativa en **WordPress** bajo el dominio compartido **La Granja-Valsaín** (`www.lagranja-valsain.com`). La **sede electrónica** es **espublico gestiona** (`realsitiodesanildefonso.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal WordPress | https://www.lagranja-valsain.com |
| Concejalía de Urbanismo | https://www.lagranja-valsain.com/ayuntamiento/concejalias/concejalia-de-urbanismo/ |
| Declaración responsable | https://www.lagranja-valsain.com/ayuntamiento/concejalias/concejalia-de-urbanismo/declaracion-responsable/ |
| Sede electrónica | https://realsitiodesanildefonso.sedelectronica.es |
| Tablón sede | https://realsitiodesanildefonso.sedelectronica.es/board |
| Trámites (catálogo) | https://realsitiodesanildefonso.sedelectronica.es/dossier/.0 |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=181 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=181 |

## Expedientes / planeamiento

- **Urbanismo en web:** página WordPress con formularios PDF (consulta urbanística, licencia de actividad, ICIO), normativa (DN-NU.rar) y enlace a declaración responsable. REST API WP bloqueada (Kadence Security 401).
- **PLAI JCYL:** tabla HTML paginada con ~90 documentos de planeamiento aprobado (modificaciones puntuales PGOU, plan especial Valsaín, plan parcial Paseo de Bolonia, etc.). Sin documentos en información pública a septiembre 2026.
- **Tablón sede:** tabla HTML con filas `preview-document/…` (Wicket). A agosto 2026: anuncios administrativos (padrón, ordenanzas); sin licencias urbanísticas recientes.
- **Sin visor municipal propio** ni listado HTML de expedientes en curso.

## Licencias de obra

- Trámites en sede espublico (`/dossier/.0`, catálogo `/catalog/t/…`): licencia de obra mayor, declaración responsable urbanística, licencia de ocupación, etc. Requieren certificado para iniciar.
- Formularios PDF descargables en la web municipal (`/files/tramites/urbanismo/`).
- No hay listado público de licencias concedidas con coordenadas; el adapter incluye páginas informativas de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Real Sitio de San Ildefonso'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature)
  - `urbanismo:plau_cyl_planes_parciales` (0 features)
  - `urbanismo:plau_cyl_sectores` (9 features SU-NC: Ampliación Instalac. Industriales, etc.)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAI y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; expedientes del tablón no enlazan a sector WFS; REST API WordPress restringida.

## Limitaciones generales

- Sede `/dossier` redirige a `/dossier/.0` y requiere sesión cookie (JSESSIONID); el adapter usa cookie jar.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
- Boletín regional: BOCYL (2 entradas históricas en CSV).
