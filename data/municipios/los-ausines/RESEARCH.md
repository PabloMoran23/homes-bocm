# Los Ausines — investigación portal ayuntamiento

**Municipio:** Los Ausines (provincia Burgos, Castilla y León)  
**Fecha:** 2026-09-22  
**BOCYL (referencia):** 1 aviso  
**INE:** 09030 | **Código postal:** 09194

## Resumen

Los Ausines dispone de **web corporativa Drupal** (`www.losausines.es`) con enlace al archivo
de planeamiento de la Junta de CyL, y **sede electrónica espublico gestiona**
(`losausines.sedelectronica.es`) con tablón de anuncios activo. El planeamiento urbanístico
vigente (NS + estudio de detalle + sectores SUNC/SUR) está centralizado en **PlanPublica / SiuCyL**.
No hay visor urbanístico municipal ni listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.losausines.es/ | Drupal; menú sede, tablón, transparencia |
| Información general | https://losausines.es/informacion-general | Enlace al archivo PlanPublica |
| Sede electrónica | https://losausines.sedelectronica.es/ | espublico gestiona (Wicket) |
| Tablón de anuncios | https://losausines.sedelectronica.es/board | Tabla HTML con ~3 filas visibles |
| Transparencia | https://losausines.sedelectronica.es/transparency | Secciones estándar espublico |
| Catálogo de trámites | https://losausines.sedelectronica.es/dossier/.0 | Redirect; puede timeout sin sesión |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=030 | 3 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=030 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=09030 | Mapa interactivo regional |

**Contacto:** Plaza Santiago 4, 09194 Los Ausines · Tel. 947 565 916 · losausines@diputaciondeburgos.net

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NS** (Normas Subsidiarias de Planeamiento Municipal), aprobación definitiva **10/09/2001**
  (`cDocId=280715`).
- **Estudio de detalle** para ordenación en barrio de San Juan, aprobación **30/03/2009**
  (`cDocId=284805`).
- **Modificación puntual NS** sector 6 SUNC, aprobación **20/12/2006** (`cDocId=282880`).

### Listado PlanPublica (PLAU) — cómo se presentan

Página HTML con tabla ordenable. Cada fila incluye:

| Campo | Origen HTML |
|-------|-------------|
| Código expediente | `09030-{PU}-YYYYMMDD-{cDocId}` en `doOpen()` / `doGoBoletin()` |
| Tipo instrumento | `PU` (planeamiento urbanístico) |
| Subtipo | NS, ED (estudio de detalle) |
| Fecha publicación | `DD/MM/YYYY` |
| Enlace PDF | `openDocumento.do?cDocId={id}` o `openDocuIndice.do?cDocId={id}` |

**Documentos identificados (sep 2026):**

| cDocId | Fecha | Título |
|--------|-------|--------|
| 280715 | 08/10/2001 | NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL |
| 284805 | 06/05/2009 | ESTUDIO DE DETALLE PARA LA ORDENACIÓN DETALLADA EN EL BARRIO DE SAN JUAN |
| 282880 | 28/03/2007 | MODIFICACIÓN PUNTUAL DE LAS NN.SS. QUE ALTERA LA DELIMITACIÓN DEL SÉCTOR 6 DE SUNC |

### Tablón de anuncios (`/board`)

Tabla HTML espublico con columnas:

`Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha de Publicación`

Anuncios recientes (sep 2026):

| Expediente | Procedimiento | Categoría | Descripción |
|------------|---------------|-----------|-------------|
| 46/2026 | Declaraciones de Ruina | Urbanismo | Información pública expediente declaración de ruina en C. Estación 4 (Bº Quintanilla) |
| 72/2025 | Declaraciones Responsables o Comunicaciones Urbanísticas | Anuncios | Bando Limpieza Parcelas |

PDFs en `https://losausines.sedelectronica.es/preview-document/{uuid}`.

## 3. Building licenses — tablón, sede, etc.

- **Sin licencias de obra concedidas** publicadas con coordenadas en el tablón visible.
- El catálogo de trámites (`/dossier/.0`) incluye formularios de solicitud de licencia
  (patrón espublico estándar), no histórico de concesiones.
- El bando de limpieza de parcelas (exp. 72/2025) se clasifica como comunicación urbanística.

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido Los Ausines |
|--------|-----|---------|----------------------|
| WFS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON/GML | **19 sectores** (SUNC-*, SUR-S*) + **1 instrumento** (NS) |
| WMS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=09030` | JS/ArcGIS-like | Visor regional |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json
  &CQL_FILTER=n_mun='Los Ausines'
```

Sectores identificados: SUNC-3/4/5/6 QUINTANILLA, SUNC-4/5/6 SOPEÑA, SUNC CUBILLO, SUR-S1/S2/S3, etc.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_sectores` (19 polígonos sectoriales); WFS `plau_cyl_instrumentos_ambito`
  (1 polígono municipal NS); SiUR visor regional (`id=09030`).
- **Estrategia:** ingestar sectores WFS con geometría; cruzar códigos SUNC/SUR del título con WFS;
  documentos PlanPublica sin sector explícito heredan polígono NS; fallback centroide municipio + jitter.
- **Limitaciones:** licencias y tablón sin GIS; SiUR no expone API scrapeable; dossier puede timeout.

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Web corporativa | **Drupal** (we-mega-menu, cookiesjsr) |
| Sede electrónica | **espublico gestiona** sobre **Apache Wicket** + nginx |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |

## Limitaciones

- Tablón: ventana corta (~3 filas), sin API ni paginación clara.
- `/dossier/.0` puede timeout sin cookie de sesión previa.
- Catálogo: formularios informativos, no resoluciones históricas de licencias.
- Sin dataset de licencias georreferenciadas.

## Estrategia adapter

1. **WFS SIUCyL** → geometría por sector (`plau_cyl_sectores`, `plau_cyl_instrumentos_ambito`).
2. **PlanPublica PLAU** → parsear tabla HTML (`doOpen`, fechas, títulos).
3. **Tablón sede** (`/board`) → filtrar keywords urbanismo/licencia/ruina.
4. **Catálogo dossier** → licencias informativas (páginas `/catalog/t/{uuid}`).
5. **IDs:** `los-ausines-{lic|proy}-{sha256[:14]}`.
