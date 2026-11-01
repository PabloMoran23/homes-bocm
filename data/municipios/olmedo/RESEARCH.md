# Olmedo — investigación portal ayuntamiento

**Municipio:** Olmedo (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-09-27  
**BOCYL (referencia):** 1 aviso  
**INE:** 47104 | **PlanPublica municipio:** 104 (provincia 47) | **WFS c_mun:** 47104

## Resumen

La web `www.olmedo.es` redirige al portal de la Diputación de Valladolid (`olmedo.ayuntamientosdevalladolid.es`), que a su vez redirige a la **sede electrónica espublico gestiona** (`olmedo.sedelectronica.es`). El planeamiento aprobado está en **PlanPublica** (Junta de CYL). Los polígonos de sectores e instrumentos están en el **WFS IDECyL** `urbanismo:plau_cyl_*`. El tablón municipal no publica concesiones de licencia de obra con dirección; el catálogo de trámites ofrece páginas informativas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Redirección corporativa | https://www.olmedo.es → http://olmedo.ayuntamientosdevalladolid.es | HTTP del portal diputación a menudo lento/timeout desde cloud |
| Sede (inicio) | https://olmedo.sedelectronica.es/info | Punto de entrada operativo |
| Tablón de anuncios | https://olmedo.sedelectronica.es/board/ | Tabla HTML con `preview-document` |
| Catálogo de trámites | https://olmedo.sedelectronica.es/dossier/ | Usar `/dossier/` (sin barra final → bucle 302) |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=104 | ~13 documentos (PP SUD-*, PGOU, modificaciones) |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=104 | Consultar IP activa |
| SiuCyL / SiUR | https://idecyl.jcyl.es/siur/index.html?id=47104 | Visor regional del municipio |

## 2. Urbanismo — expedientes y licencias

### Tablón (`/board/`)

- Listado en `<tbody>` con columnas: documento, expediente, procedimiento, categoría, descripción, fecha.
- Enlaces PDF: `https://olmedo.sedelectronica.es/preview-document/{uuid}`.
- Contenido actual (sep 2026): personal, IAE, listados varios; sin filas claras de licencia urbanística concedida.

### Catálogo (`/dossier/`)

Trámites urbanísticos relevantes (UUID en `/catalog/t/...`):

- Declaración Responsable o Comunicación en Materia Urbanística (`a2f7c529-…`)
- Solicitud de Licencia o Autorización Urbanística (`15fabacb-…`)
- Solicitud de Modificación o Renuncia de una Licencia Urbanística (`a3c783fb-…`)
- Solicitud de Licencia de Ocupación (`b834b3fa-…`)
- Solicitud de Certificado o Informe Urbanístico (`e247f7c3-…`)
- Solicitud de Actuación Urbanística / Aprobación de Planeamiento de Desarrollo
- Modificación del Planeamiento de Desarrollo / Planeamiento General (Modificación)

### PlanPublica (PLAU)

Tabla HTML con títulos como «PP SUD-1 LA ALMAZARA», «PP SUD-4 CAMINO DEL AGUASAL», «PLAN GENERAL DE ORDENACIÓN URBANA (REVISIÓN)», modificaciones puntuales PGOU, etc. PDF vía `openDocumento.do?cDocId=…`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** IDECyL GeoServer WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_instrumentos_ambito`
  - Filtro: `n_mun = 'Olmedo'` (c_mun `47104`)
  - Sectores de ejemplo: SNC-01, SUG-1, SUD-04, PE-FE, SUD-07
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas PLAU/tablón con `_attach_geometry` buscando códigos de sector (SUD-*, SNC-*, etc.) en el texto.
- **Limitaciones:** tablón sin coordenadas; licencias sin GIS; no hay visor ArcGIS municipal propio; portal diputación HTTP inestable.

## Limitaciones generales

- Sede con certificado válido; scraper usa cookie jar en `/dossier/`.
- Paginación del tablón limitada a la página principal en el scrape actual.
