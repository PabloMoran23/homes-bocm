# Mojados — investigación portal ayuntamiento

**Municipio:** Mojados (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-09-24  
**BOCYL (referencia):** 1 aviso  
**INE:** 47103 | **PlanPublica municipio:** 090 (provincia 47) | **WFS c_mun:** 47090

## Resumen

Mojados **no tiene web municipal propia** (dominios `mojados.es` / `aytomojados.es` sin DNS). La presencia digital es la **sede electrónica espublico gestiona** (`mojados.sedelectronica.es`). El planeamiento aprobado e histórico está en **PlanPublica** (Junta de CYL). Los polígonos de sectores e instrumentos están en el **WFS IDECyL** `urbanismo:plau_cyl_*`. El tablón municipal no publica concesiones de licencias de obra con dirección; solo trámites informativos en el catálogo.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede (inicio) | https://mojados.sedelectronica.es/info | Redirige a `info.0` |
| Tablón de anuncios | https://mojados.sedelectronica.es/board/ | Tabla HTML con `preview-document` |
| Catálogo de trámites | https://mojados.sedelectronica.es/dossier/ | Usar `/dossier/` (no `/dossier/.0`, bucle 302) |
| PlanPublica PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=090 | 14 documentos (PP, modificaciones, PGOU revisión) |
| PlanPublica PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=090 | Sin expedientes en IP activos |
| SiuCyL / SiUR | https://idecyl.jcyl.es/siur/index.html?id=47103 | Visor regional del municipio |

## 2. Urbanismo — expedientes y licencias

### Tablón (`/board/`)

- Listado en `<tbody>` con columnas: documento, expediente, procedimiento, categoría, descripción, fecha.
- Enlaces PDF: `https://mojados.sedelectronica.es/preview-document/{uuid}`.
- Contenido actual (sep 2026): subvenciones, calendario laboral, anuncio IAE con procedimiento «Certificados o Informes Urbanísticos» (no licencia de obra).
- **Licencias:** no hay filas de concesión de licencia urbanística publicadas; el adapter usa páginas de trámite del catálogo.

### Catálogo (`/dossier/`)

Trámites urbanísticos relevantes (UUID en `/catalog/t/...`):

- Declaración Responsable de Obras y Usos
- Solicitud de Licencia de Construcciones, Instalaciones y Obras
- Solicitud de Licencia de Ocupación / Actividad
- Solicitud de Certificado o Informe Urbanístico

### PlanPublica (PLAU)

Tabla HTML con títulos como «PP LA CORONILLA», «MODIFICACION PUNTUAL: SECTOR LA CORONILLA», «PLAN PARCIAL INDUSTRIAL DEL SECTOR 2M», PGOU revisión, etc. PDF vía `openDocumento.do?cDocId=...`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS GeoServer JCYL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `urbanismo:plau_cyl_planes_parciales`, `urbanismo:plau_cyl_sectores`
  - Filtro: `CQL_FILTER=n_mun='Mojados'` (c_mun `47090`)
  - Salida: `outputFormat=application/json`, `srsName=EPSG:4326`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; enriquecer filas PLAU/tablón con `_wfs_sector_geometry` por código de sector en el título.
- **Limitaciones:** sin visor municipal propio; licencias del tablón sin geometría; instrumento PGOU revisión tiene polígono de ámbito pero licencias individuales no.

## 3. Limitaciones técnicas

- `/dossier/.0` provoca bucle de redirecciones con `urllib`; usar `/dossier/`.
- Primera petición a sede requiere cookie jar + `insecure_ssl` opcional (certificado gestionado por espublico).
- `request_delay_s` ≥ 0.35 recomendado.

## 4. Adapter

Patrón **Valverdón / espublico CYL**: tablón + dossier + PlanPublica + WFS IDECyL.
