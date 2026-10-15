# Respenda de la Peña — investigación portal ayuntamiento

**Municipio:** Respenda de la Peña (Palencia, Castilla y León)  
**INE:** 34151  
**PLAU:** provincia=34, municipio=151  
**Fecha:** 2026-10-15  
**BOCYL regional (referencia):** 1 aviso

## Resumen

El ayuntamiento publica urbanismo en **web WordPress**, **sede espublico gestiona** y el **visor autonómico** (PlanPublica / IDECyL).

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://respendadelapena.es | WordPress (REST API deshabilitada) | Sección Urbanismo (página estática) |
| Sede electrónica | https://respendadelapena.sedelectronica.es | espublico gestiona (Wicket) | Tablón `/board`, trámites `/dossier`, transparencia |
| Junta CYL | https://servicios.jcyl.es/PlanPublica | PlanPublica | NUM y documentación OT aprobada |
| IDECyL | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | WFS GeoServer | Polígono NUM municipal |
| SIUR | https://idecyl.jcyl.es/siur/index.html?id=34151 | Visor JCyL | Consulta planeamiento por municipio |

## Fuentes identificadas

### 1. WordPress — Urbanismo

- **URL:** https://respendadelapena.es/ayuntamiento/urbanismo/
- **Formato:** página informativa (sin listado de expedientes ni PDFs locales en el scrape actual)
- **REST API:** `/wp-json/` responde 401 «No REST API»

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://respendadelapena.sedelectronica.es/board/
- **Formato:** tabla HTML espublico (`preview-document/…` cuando hay anuncios)
- **Ventana actual:** sin filas urbanísticas con `preview-document` (solo estructura de tablón)

### 3. Sede — catálogo de trámites

- **URL:** https://respendadelapena.sedelectronica.es/dossier
- **Formato:** enlaces `/catalog/t/{uuid}` (puede ser lento en CI)
- Trámites informativos de licencias/urbanismo si están publicados en catálogo

### 4. Junta CYL — PlanPublica

- **Archivo aprobado:** `searchVPubDocMuniPlau.do?provincia=34&municipio=151`
- **Documentos detectados (2026-10):**
  - `34151-PU-20220720-298392` — NUM vigente (cDocId=298392)
  - `34000-OT-20090128-293564`
  - `00000-OT-20110414-286664`
- **Índice:** `openDocuIndice.do?cDocId=…`
- **PDF:** `http://www.jcyl.es/plaupdf//34/34151/{cDocId}/`

### 5. IDECyL WFS

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas con datos:** `plau_cyl_instrumentos_ambito` (1 polígono NUM)
- **Capas vacías:** `plau_cyl_sectores`, `plau_cyl_planes_parciales` (0 features para c_mun=34151)
- **Filtro:** `n_mun='Respenda de la Peña'` o `c_mun='34151'`
- **NUM:** aprobación 2022-07-11, publicación BOCYL 2022-07-19 (`c_plan=34151-PU-20220720-298392`)

## Licencias

No hay dataset abierto de concesiones georreferenciadas.

- Licencias vía **trámites informativos** en sede (`/dossier`) y posibles anuncios en tablón
- Sin visor municipal de licencias con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono del instrumento NUM (ámbito municipal)
  - SIUR JCyL (`id=34151`) — visor autonómico (sin API directa por expediente municipal)
- **Estrategia:** descarga WFS por `c_mun`; enriquecer filas de planeamiento (NUM / PlanPublica) con `geom_geojson` del ámbito; tablón/PDF sin enlace GIS → centroide manifest + jitter
- **Limitaciones:**
  - Sin sectores/ámbitos parciales en WFS para este municipio
  - Tablón sin anuncios urbanísticos en la ventana actual
  - Licencias sin geometría en fuentes públicas

## Limitaciones

- WordPress sin API REST pública
- Catálogo sede puede tardar o fallar en entornos CI (reintentos en adapter)
- SSL sede: `insecure_ssl: true` por cadena incompleta en algunos entornos
