# Terradillos — investigación portal ayuntamiento

**Municipio:** Terradillos (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-03  
**BOCYL (referencia):** 2 avisos  
**INE:** 37322 | **DIR3:** L01373224

## Resumen

Terradillos publica trámites y tablón en la **sede electrónica espublico gestiona**
(`terradillos.sedelectronica.es`). La web corporativa (`ayto-terradillos.com`) responde **502** (ago 2026);
solo ofrece formularios descargables sin listado de expedientes. El planeamiento urbanístico vigente (NUM 2006
y numerosas modificaciones, planes parciales UBZR*, convenios urbanísticos) está en **PlanPublica / SiuCyL**.
No hay visor urbanístico municipal ni listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica (inicio) | https://terradillos.sedelectronica.es/info.0 | Lento/timeout sin cookie; usar `/board/` primero |
| Tablón de anuncios | https://terradillos.sedelectronica.es/board/ | Tabla HTML espublico (~8 filas ago 2026) |
| Catálogo de trámites | https://terradillos.sedelectronica.es/dossier/.0 | Requiere cookie de sesión (visitar `/board/` antes) |
| Web corporativa | http://ayto-terradillos.com | HTTP 502; formularios en `/ayuntamiento/solicitudes/` |
| Diputación — normas urbanísticas | http://www.lasalina.es/Aplicaciones/GestorInter.jsp?codMunicipio=322&funcion=VerNormasUrbanisticas&nombre=Terradillos | PDFs NUM 2006 (memoria + plano) |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=322 | 15+ documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=322 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37322 | Mapa interactivo regional |

**Contacto:** Plaza del Ayuntamiento, 1, 37882 Terradillos · Tel. 923 37 30 86 · administracion@ayto-terradillos.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **06/03/2006** (`cDocId=282205`).
- Múltiples **modificaciones puntuales** (2007–2014), **planes parciales** (UBZR1–7, Los Cisnes, El Encinar),
  **convenios urbanísticos** y **proyectos de urbanización** (Los Cisnes, UBZR1).
- Sectores identificados en WFS: UNC-1/2/3, UBZR1–7, UBZRI1, UBZI2, UBZND, R-5.

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Campos: tipo instrumento (PU/GU/CU), subtipo (NUM/PP/PAU/ED…), fecha,
título, enlace PDF (`openDocumento.do?cDocId={id}`).

**Documentos destacados (sep 2026):**

| cDocId | Subtipo | Fecha | Título |
|--------|---------|-------|--------|
| 282205 | NUM | 06/03/2006 | NORMAS URBANÍSTICAS MUNICIPALES |
| 283631 | PP | 05/09/2007 | PLAN PARCIAL DEL SECTOR UBZ-R6 |
| 285357 | PP | 04/12/2009 | PLAN PARCIAL SECTOR UBZR7 |
| 285684 | PAU | 07/04/2010 | MODIFICACIÓN PROYECTO ACTUACIÓN UBZR-1 |
| 286128 | CN_UR | 06/02/2008 | CONVENIO URBANÍSTICO SECTOR UBZR1 |
| 291296 | NUM | 12/11/2014 | MODIFICACIÓN PUNTUAL Nº 2 NUM (UBZ R5) |
| 291752 | CUG | 09/04/2015 | MODIFICACIÓN PROYECTO COMPENSACIÓN U.R. LOS CISNES |

Códigos PlanPublica: **provincia=37** (Salamanca), **municipio=322** (Terradillos).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Columnas: Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.

- Anuncios recientes (2026): cobranza IBI/IAE, subvenciones material didáctico, lista jurado.
- **Sin licencias de obra** en la ventana visible.
- PDFs en `https://terradillos.sedelectronica.es/preview-document/{uuid}`.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos (no histórico de concesiones). Relevantes:

| Trámite | UUID catálogo |
|---------|---------------|
| Declaración Responsable o Comunicación en Materia Urbanística | `5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud de Licencia o Autorización Urbanística | `15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Modificación o Renuncia de Licencia Urbanística | `a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Solicitud de Licencia de Ocupación | `b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Certificado o Informe Urbanístico | `e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Modificación del Planeamiento de Desarrollo | `6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Planeamiento General (Modificación) | `96514574-aca1-40e1-a800-e06485e6d016` |
| Solicitud de Actuación Urbanística | `f91e4a50-d23d-45c1-a19b-b148da37c59f` |

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido Terradillos |
|--------|-----|---------|----------------------|
| WFS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON/GML | **1** instrumento NUM + **13** sectores + **6** planes parciales |
| WMS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=37322` | JS/ArcGIS-like | Visor regional |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Terradillos'
```

Sectores: UNC-1, UNC-2, UNC-3, UBZR1–7, UBZRI1, UBZI2, UBZND, R-5.

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (Apache Wicket) + nginx |
| Web corporativa | WordPress (inactiva, 502) |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_instrumentos_ambito` (polígono NUM municipal), `plau_cyl_sectores`
  (13 sectores UBZR/UNC), `plau_cyl_planes_parciales` (6 PP).
- **Estrategia:** extraer códigos UBZR*, UNC*, R-5 del título → cruzar con WFS; NUM → polígono
  instrumento; fallback centroide `[40.8503, -5.5765]` + jitter.
- **Limitaciones:** licencias y tablón sin GIS; web corporativa caída; `/info.0` timeout sin cookie.

## Limitaciones

- Web municipal inactiva (502); formularios sin listado de expedientes.
- Tablón: ventana corta, sin API ni paginación clara.
- `/info.0` y `/dossier` requieren cookie de sesión (visitar `/board/` antes).
- Catálogo: formularios, no resoluciones históricas de licencias.

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla HTML (`doOpen`, fechas, títulos).
2. **WFS IDECyL** → geometría por sector/instrumento/PP.
3. **Tablón sede** (`/board/`) → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias informativas (`/catalog/t/{uuid}`).
5. **IDs:** `terradillos-{lic|proy}-{sha256[:14]}`.
