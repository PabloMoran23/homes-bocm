# Mata de Cuéllar — investigación portal ayuntamiento

## Resumen

Municipio de la provincia de Segovia (Castilla y León, INE **40124**). El ayuntamiento publica su web en **Liferay** con el tema **Segovia12** de la Diputación de Segovia (`www.matadecuellar.es`). La **sede electrónica** es **espublico gestiona** (`matadecuellar.sedelectronica.es`).

## URLs base y páginas semilla

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.matadecuellar.es |
| Urbanismo | https://www.matadecuellar.es/urbanismo |
| Sede electrónica | https://matadecuellar.sedelectronica.es |
| Tablón sede | https://matadecuellar.sedelectronica.es/board |
| Trámites (catálogo) | https://matadecuellar.sedelectronica.es/dossier |
| Archivo PLAU (aprobado) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=124 |
| Archivo PLAI (info pública) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=124 |
| SiuCyL / visor JCYL | https://idecyl.jcyl.es/siur/index.html?id=40124 |

## Expedientes / planeamiento

- **Urbanismo en web:** página Liferay casi vacía (sin PDFs ni listado de expedientes); enlace al tablón y sede.
- **PLAU JCYL:** 1 documento — *SIN PLANEAMIENTO GENERAL* (instrumento SPG).
- **PLAI JCYL:** 1 documento en información pública — *NORMAS URBANÍSTICAS TERRITORIALES* (NUT, junio 2025).
- **Tablón sede:** tabla HTML Wicket con `preview-document/…`. A agosto 2026: 1 anuncio (padrón alcantarillado/agua, no urbanismo).
- **Catálogo trámites (`/dossier`):** responde vacío o timeout desde algunos entornos; el adapter tolera fallo.

## Licencias de obra

- Trámites urbanísticos en sede espublico (requieren certificado para iniciar).
- No hay listado público de licencias concedidas con coordenadas.
- El adapter incluye páginas informativas (urbanismo web, dossier) y entradas del tablón cuando aplican.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `urbanismo:plau_cyl_*` filtrado por `n_mun = 'Mata de Cuéllar'` (`c_mun = 40124`):
  - `urbanismo:plau_cyl_instrumentos_ambito` — 1 feature (SPG, MultiPolygon ~20 km²)
  - `urbanismo:plau_cyl_planes_parciales` — 0 features
  - `urbanismo:plau_cyl_sectores` — 0 features (municipio sin sectores publicados)
- **Estrategia:** descarga WFS GeoJSON (`EPSG:4326`) + enriquecimiento por coincidencia de título en filas PLAI/PLAU.
- **Limitaciones:** sin visor ArcGIS municipal; sin sectores WFS; licencias sin polígono; tablón sin anuncios urbanísticos recientes.

## Limitaciones generales

- Sede `/dossier` puede no responder (timeout); scrape tolerante.
- Sin API JSON de expedientes; scrape determinista HTML + WFS + PlanPublica.
- BOCM regional (`bocyl`): 3 entradas históricas ya en `projects.json` (no re-parseadas).
