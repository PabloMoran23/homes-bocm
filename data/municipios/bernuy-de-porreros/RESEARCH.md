# Bernuy de Porreros — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León). El ayuntamiento publica su web en la plataforma **Liferay de la Diputación de Segovia** (`dipsegovia.es`); el dominio `www.bernuydeporreros.es` redirige pero está protegido por WAF desde algunos entornos. La **sede electrónica** es **espublico gestiona** (`bernuydeporreros.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Portal Liferay (DipSegovia) | https://www.dipsegovia.es/web/ayuntamiento-de-bernuy-de-porreros |
| Urbanismo | https://www.dipsegovia.es/web/ayuntamiento-de-bernuy-de-porreros/urbanismo |
| Tablón municipal (web) | https://www.dipsegovia.es/web/ayuntamiento-de-bernuy-de-porreros/tablon-de-anuncios |
| Sede electrónica | https://bernuydeporreros.sedelectronica.es |
| Tablón sede | https://bernuydeporreros.sedelectronica.es/board |
| Trámites (catálogo) | https://bernuydeporreros.sedelectronica.es/dossier |
| Archivo PLAI (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=031 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=031 |

## Expedientes / planeamiento

- **Urbanismo en web:** página informativa con enlace al archivo PLAI de la Junta de CYL; contacto por email (`aytoadmon@bernuydeporreros.es`, asunto URBANISMO). No hay listado HTML de expedientes en curso.
- **PLAI JCYL:** tabla HTML paginada (`searchVPubDocMuniPlau.do`) con documentos de planeamiento aprobado (modificaciones puntuales, NUM, convenios urbanísticos, etc.). ~15+ filas por página.
- **Tablón sede:** tabla HTML con filas `preview-document/…` (Wicket). A agosto 2026: 1 anuncio (subasta parcelas fotovoltaicas, no urbanismo clásico).
- **Sin visor municipal propio** ni Drupal/WordPress local con expedientes IP.

## Licencias de obra

- Trámites en sede espublico (`/dossier`, catálogo `/catalog/t/…`); requieren certificado para iniciar.
- No hay listado público de licencias concedidas con coordenadas; el tablón sede puede publicar anuncios puntuales.
- El adapter incluye páginas informativas de trámites y entradas del tablón cuando aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Bernuy de Porreros'`:
  - `urbanismo:plau_cyl_instrumentos_ambito` (1 feature)
  - `urbanismo:plau_cyl_planes_parciales` (3 features)
  - `urbanismo:plau_cyl_sectores` (6 features: UE 1–3, Los Hitales, Nº A-2, etc.)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título/sector en filas PLAI y tablón.
- **Limitaciones:** sin visor ArcGIS municipal; licencias sin polígono; expedientes del tablón no siempre enlazan a sector WFS.

## Limitaciones generales

- Dominio propio `bernuydeporreros.es` bloqueado por WAF en algunos entornos (usar `dipsegovia.es`).
- Sede `/dossier` puede responder lento; el adapter tolera timeout.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PLAI.
