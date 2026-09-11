# Castellanos de Moriscos — investigación portal ayuntamiento

**Slug:** `castellanos-de-moriscos`  
**Provincia:** Salamanca (Castilla y León)  
**Código INE:** 37092  
**PlanPublica:** provincia=37, municipio=084

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | http://castellanosdemoriscos.es |
| Sede electrónica (espublico gestiona) | https://castellanosdemoriscos.sedelectronica.es |
| Tablón de anuncios | https://castellanosdemoriscos.sedelectronica.es/board/ |
| Información pública sede | https://castellanosdemoriscos.sedelectronica.es/info.0 |
| Catálogo de trámites | https://castellanosdemoriscos.sedelectronica.es/dossier/.0 |
| PlanPublica PLAU (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=084 |
| PlanPublica PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=084 |
| Diputación Salamanca (ficha) | http://www.lasalina.es/Aplicaciones/GestorInter.jsp?codMunicipio=92 |

**Nota:** El dominio con guiones (`castellanos-de-moriscos.sedelectronica.es`) devuelve página indeterminada; la sede operativa es `castellanosdemoriscos.sedelectronica.es`.

## Expedientes / planeamiento

- **Tablón sede:** HTML con tabla Wicket; enlaces `preview-document/{uuid}` a PDFs de anuncios (plenos, BOP, etc.). Parsing por filas `<tbody><tr>`.
- **PlanPublica JCyl:** Sin documentos PLAU publicados al momento de la investigación; PLAI vacío. El instrumento NUM está en WFS.
- **IDECyL WFS:** Capas `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores` filtradas por `n_mun='Castellanos de Moriscos'`.
- **Trámites sede:** Catálogo espublico con UUIDs estándar JCyl (licencias, planeamiento, actuaciones urbanísticas).

## Licencias de obra

- No hay dataset público de concesiones de licencia.
- El tablón puede publicar resoluciones puntuales (filtro regex licencia/obra).
- Trámites informativos del catálogo sede (licencia urbanística, comunicación previa, etc.) como filas de referencia.

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `plau_cyl_instrumentos_ambito` (NUM municipal, MultiPolygon), `plau_cyl_sectores` (12 sectores SUR/SUNC), `plau_cyl_planes_parciales`
  - Filtro: `CQL_FILTER=n_mun='Castellanos de Moriscos'`
  - Parámetros: `outputFormat=application/json`, `srsName=EPSG:4326`
- **Estrategia:** Descarga masiva WFS por capa; enriquecimiento puntual por código de sector (SUR-*, SUNC-*) en títulos de tablón/PLAU.
- **Limitaciones:**
  - Sin visor ArcGIS propio del ayuntamiento; geometría solo vía IDECyL.
  - Licencias del tablón sin georreferencia (solo PDF).
  - Sede requiere `insecure_ssl` por certificado intermedio.

## Limitaciones generales

- Web corporativa sin listado estructurado de expedientes (noticias/fiestas).
- PlanPublica sin filas documentales en PLAU/PLAI (solo WFS).
- Tablón con pocos anuncios urbanísticos; mayoría administrativos.
- SSL sede: certificado no verificado en entorno agente (`insecure_ssl: true`).
