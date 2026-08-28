# Fresno de Cantespino — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). La web corporativa está en **Liferay** (`www.fresnodecantespino.es`, tema Segovia11 de la Diputación) con réplica en **DipSegovia** (`dipsegovia.es/web/ayuntamiento-de-fresno-de-cantespino`). La **sede electrónica** es **espublico gestiona** (`fresnodecantespino.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web corporativa | https://www.fresnodecantespino.es |
| Urbanismo | https://www.fresnodecantespino.es/urbanismo |
| DipSegovia (réplica) | https://www.dipsegovia.es/web/ayuntamiento-de-fresno-de-cantespino |
| Urbanismo DipSegovia | https://www.dipsegovia.es/web/ayuntamiento-de-fresno-de-cantespino/urbanismo |
| Sede electrónica | https://fresnodecantespino.sedelectronica.es |
| Tablón sede | https://fresnodecantespino.sedelectronica.es/board |
| Trámites (catálogo) | https://fresnodecantespino.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=089 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=089 |

## Expedientes / planeamiento

- **Urbanismo en web:** página Liferay con documentación (mapa de ruido, localización temporal de instalaciones, etc.) vía `asset_publisher`; enlace al archivo PLAI JCYL. Sin listado HTML de expedientes en curso en la web corporativa.
- **PLAI JCYL (código municipio 089 / INE 40089):**
  - Aprobado: SPG «SIN PLANEAMIENTO GENERAL».
  - Información pública: NUT «NORMAS URBANÍSTICAS TERRITORIALES» (finalizado plazo, 2025).
- **Tablón sede:** tabla HTML con filas `preview-document/…` (Wicket). A agosto 2026: anuncios de IBI/IAE y resolución de alcaldía expediente 302-2024 (urbanismo).
- **Sin visor municipal ArcGIS** ni API JSON de expedientes.

## Licencias de obra

- Trámites en sede espublico (`/dossier`, catálogo `/catalog/t/…`); requieren certificado para iniciar.
- No hay listado público de licencias concedidas con coordenadas; el tablón puede publicar resoluciones puntuales.
- El adapter incluye páginas informativas de trámites y entradas del tablón cuando aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Fresno de Cantespino'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature: ámbito municipal)
  - `urbanismo:plau_cyl_planes_parciales` (2 features)
  - `urbanismo:plau_cyl_sectores` (3 features: SECTOR Nº1 SUNC. PAJARES DE FRESNO, SECTOR URBANIZABLE INDUSTRIAL «LA BALSA», SECTOR ED-1)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`, `outputFormat=application/json`) + enriquecimiento por coincidencia de título/sector en filas PLAI y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; expedientes del tablón no siempre enlazan a sector WFS.

## Limitaciones generales

- Catálogo `/dossier` de la sede puede responder lento o timeout en CI; el adapter tolera fallo.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
