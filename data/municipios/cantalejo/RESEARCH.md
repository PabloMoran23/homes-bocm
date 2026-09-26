# Cantalejo — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). El ayuntamiento publica su web en **Liferay Segovia8** bajo dominio propio `www.cantalejo.es` (gestionado por la Diputación de Segovia). La **sede electrónica** es **espublico gestiona** (`cantalejo.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal Liferay (Segovia8) | https://www.cantalejo.es |
| Urbanismo | https://www.cantalejo.es/urbanismo |
| Sede electrónica | https://cantalejo.sedelectronica.es |
| Tablón sede | https://cantalejo.sedelectronica.es/board |
| Transparencia sede | https://cantalejo.sedelectronica.es/transparency |
| Trámites (catálogo) | https://cantalejo.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=049 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=049 |

## Expedientes / planeamiento

- **Urbanismo en web:** galería Liferay (`IGDisplayPortlet`) con PDFs de NNSS/modificaciones puntuales (p. ej. UE-1 Sector-2, UE-3 Sector-4, información pública). Enlaces `/documents/2362911/…`.
- **PLAI JCYL:** tabla HTML paginada (`searchVPubDocMuniPlau.do`, municipio 049). Documentos de planeamiento aprobado (NUM, sectores, modificaciones). Existe aviso de documentos en información pública (`searchVPubDocMuniPlai.do`).
- **Tablón sede:** tabla HTML con filas `preview-document/…` (Wicket). A agosto 2026: mayoritariamente edictos registrales y anuncios presupuestarios; sin licencias urbanísticas recientes visibles.
- **Sin visor municipal propio** ni API JSON de expedientes.

## Licencias de obra

- Trámites en sede espublico (`/dossier`, categoría «URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» con ~312 trámites). Requieren certificado para iniciar.
- No hay listado público de licencias concedidas con coordenadas.
- El adapter incluye páginas informativas de trámites y entradas del tablón cuando aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Cantalejo'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature)
  - `urbanismo:plau_cyl_planes_parciales` (6 features)
  - `urbanismo:plau_cyl_sectores` (25 features: UE-1…UE-8 en sectores 1–4, SUNC 5.1/5.2, etc.)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAI, Liferay y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; expedientes del tablón no siempre enlazan a sector WFS.

## Limitaciones generales

- Sede `/dossier` puede responder lento (>45 s); el adapter tolera timeout.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
- Certificado SSL de sede puede requerir `insecure_ssl: true` en algunos entornos.
