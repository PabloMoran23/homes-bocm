# Bétera — investigación portal ayuntamiento

## URLs base y semillas

| Recurso | URL |
|---------|-----|
| Web municipal | https://www.betera.es |
| Urbanismo (sección) | https://www.betera.es/es/seccion/urbanismo |
| Información pública | https://www.betera.es/es/pagina/informacion-publica |
| Información urbanismo | https://www.betera.es/es/pagina/informacion-urbanismo-e-infraestructuras |
| PGOU | https://www.betera.es/va/enlace/pla-general-urbanistic-pgou |
| Documentación | https://www.betera.es/es/enlace/documentacion |
| Cartografía | https://www.betera.es/es/enlace/cartografia |
| Tablón (enlace web) | https://www.betera.es/es/enlace/tablon-anuncios |
| Sede electrónica | https://betera.sedelectronica.es |
| Tablón sede | https://betera.sedelectronica.es/board |
| Transparencia sede (urbanismo) | https://betera.sedelectronica.es/transparency |
| SIG municipal | https://sig.betera.es/ |

## CMS y formato de listados

- **Web:** Drupal 10 (`portalesmunicipales` / módulos `digital_value/*`).
- **Expedientes / edictos:** sede **espublico gestiona** (Wicket). Tablón HTML con columnas `class_name`, `class_folderCode`, `class_folderName`, enlaces `/preview-document/{uuid}`.
- **Información pública:** páginas Drupal con PDFs estáticos bajo `/sites/www.betera.es/files/Informatica/Areas/Urbanismo_E_Infrastructuras/Informacion_Publica/` (modificaciones PG 2023, PMUS, plan parcial sector R-13 2024, depósito Mas Camarena 2025).
- **Licencias:** no hay dataset abierto de concesiones; trámites vía catálogo sede (`/dossier`) y consulta expedientes con certificado (`/expedientes`).

## Licencias

- Tablón sede: edictos de licencias de obra/actividad cuando se publican.
- Formularios y requisitos en sección urbanismo (obras, actividades, planeamiento).
- Adapter: filas del tablón + páginas informativas de trámites (paridad mínima).

## Proyectos / planeamiento

- PDFs de información pública y consulta previa en web municipal.
- ICV WFS `Planeamiento.Zonificacion` filtrado por `cod_ine_mun=46047` (plan general y sectores).
- Transparencia sede: categoría «Urbanismo, obras públicas y medio ambiente» (documentos PDF sueltos).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS ICV: `https://terramapas.icv.gva.es/0702_Planeamiento` — capa `Planeamiento.Zonificacion`, campo `cod_ine_mun=46047`, atributos `denominaci`, `expediente`.
  - Visor GVA: https://visor.gva.es/visor/?capas=spaicv0702_plan_zonificacion
  - SIG municipal: https://sig.betera.es/ (cartografía y planeamiento local; sin API GeoJSON documentada para expedientes individuales).
- **Estrategia:** descarga paginada WFS por `startIndex`; emparejar título/tablon con `denominaci` (sector, plan general); polígonos en WGS84 vía GeoJSON WFS.
- **Limitaciones:** licencias del tablón sin parcela en HTML; SIG municipal no expone query REST pública por código de expediente; WFS ICV cubre instrumentos de planeamiento, no cada licencia de obra. Algunas features ICV con `cod_ine_mun=46047` tienen geometría fuera del término (centroide ~38.88°N) y se descartan en el adapter.

## Limitaciones generales

- Consulta de expedientes en sede requiere certificado digital.
- `insecure_ssl: true` en sede (certificado intermitente en algunos entornos).
- Paginación WFS lenta (~500 features/página); cache en adapter.
