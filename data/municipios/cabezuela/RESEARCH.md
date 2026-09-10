# Cabezuela — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). El ayuntamiento publica su web en la plataforma **Liferay Segovia9** (`www.cabezuela.es`, gestionada por la Diputación de Segovia). La **sede electrónica** es **espublico gestiona** (`cabezuela.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal web | https://www.cabezuela.es |
| Urbanismo | https://www.cabezuela.es/urbanismo |
| Tablón municipal (web) | https://www.cabezuela.es/tablon-de-anuncios |
| Sede electrónica | https://cabezuela.sedelectronica.es |
| Tablón sede | https://cabezuela.sedelectronica.es/board |
| Información pública sede | https://cabezuela.sedelectronica.es/info |
| Trámites (catálogo) | https://cabezuela.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=036 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=036 |

## Expedientes / planeamiento

- **Urbanismo en web:** galería de documentos Liferay con la documentación de las **Normas Urbanísticas Municipales (NUM)** y anexos (memoria informativa, normativa, planos, trámite ambiental). PDFs en `/documents/1811359/…`.
- **PLAI JCYL:** tabla HTML paginada con planeamiento aprobado: NUM (2004, 2006, 2012, 2014), planes parciales (Virgen de la Estrella, El Pinar, Eras Arriba), PORN Sierra de Guadarrama. Código municipio PLAI: **036** (provincia 40).
- **Tablón sede:** tabla/listado Wicket con `preview-document/…`. Incluye anuncios de consulta pública (ordenanza caminos rurales) y otros edictos.
- **Sin visor urbanístico municipal** ni listado JSON de expedientes en curso.

## Licencias de obra

- Trámites en sede espublico (`/dossier`); requieren certificado para iniciar.
- No hay dataset público de licencias concedidas con coordenadas.
- El adapter incluye entradas del tablón sede cuando aplican y páginas informativas de trámites.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Cabezuela'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature)
  - `urbanismo:plau_cyl_sectores` (6 features: La Fábrica U6, Prados D4, Camino de Aguilafuente D5, Piscinas U1, Eras I U2, Ermita U3)
  - `urbanismo:plau_cyl_planes_parciales` (0 features con geometría independiente; planes en PLAI)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAI, tablón y documentos urbanismo.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; expedientes del tablón no siempre enlazan a sector WFS.

## Limitaciones generales

- Algunas rutas (`/es/urbanismo`) pueden devolver WAF «Request Rejected»; usar `www.cabezuela.es/urbanismo`.
- Sede `/dossier` puede responder lento; el adapter tolera timeout.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
