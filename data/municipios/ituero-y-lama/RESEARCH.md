# Ituero y Lama — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). El ayuntamiento publica su web en la plataforma **Liferay de la Diputación de Segovia** (`dipsegovia.es`). El dominio `ituero.es` corresponde a una asociación cultural local, no al ayuntamiento. La **sede electrónica** es **espublico gestiona** (`itueroylama.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal Liferay (DipSegovia) | https://www.dipsegovia.es/web/ayuntamiento-de-ituero-y-lama |
| Urbanismo | https://www.dipsegovia.es/web/ayuntamiento-de-ituero-y-lama/urbanismo |
| Sede electrónica | https://itueroylama.sedelectronica.es |
| Tablón sede | https://itueroylama.sedelectronica.es/board |
| Transparencia | https://itueroylama.sedelectronica.es/transparency |
| Trámites (catálogo) | https://itueroylama.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=108 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=108 |

## Expedientes / planeamiento

- **Urbanismo en web DipSegovia:** página con actuaciones publicadas (aprobación inicial canon de saneamiento Coto de San Isidro, aprobación definitiva UN-1, actuación aislada CSI-4 pavimentación, etc.) y enlace al portal de transparencia.
- **PLAI JCYL:** tabla HTML paginada con documentos de planeamiento. A agosto 2026: NUT (Normas Urbanísticas Territoriales) en información pública; archivo aprobado con NUM (Normas Urbanísticas Municipales, 2004).
- **Tablón sede:** tabla HTML con filas `preview-document/…` (Wicket). A agosto 2026: anuncios de padrones, licencias de transporte, colonias felinas; sin licencias de obra urbanística clásicas.
- **Transparencia sede:** categoría «7. URBANISMO, OBRAS PÚBLICAS Y MEDIO AMBIENTE» (43 documentos); portal Wicket/AJAX sin API JSON pública.

## Licencias de obra

- Trámites en sede espublico (`/dossier`, catálogo `/catalog/t/…`); requieren certificado para iniciar.
- No hay listado público de licencias de obra concedidas con coordenadas.
- El tablón publica licencias de transporte (autotaxi) pero no licencias urbanísticas de edificación.
- El adapter incluye páginas informativas de trámites y entradas del tablón cuando aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Ituero y Lama'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature: NUM)
  - `urbanismo:plau_cyl_planes_parciales` (1 feature)
  - `urbanismo:plau_cyl_sectores` (6 features: SECTOR 4 El Camping, SECTOR1B Gran Monte, SECTORES 5/6/A/B)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAI, DipSegovia urbanismo y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; transparencia requiere navegación Wicket; expedientes del tablón no siempre enlazan a sector WFS.

## Limitaciones generales

- Dominio `ituero.es` no es el ayuntamiento (asociación cultural).
- Sede `/dossier` puede responder lento o timeout en CI; el adapter tolera fallo.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
