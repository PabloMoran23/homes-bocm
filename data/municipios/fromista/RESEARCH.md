# Frómista — investigación portal ayuntamiento

**Municipio:** Frómista (provincia Palencia, Castilla y León)  
**Fecha:** 2026-09-16  
**BOCYL (referencia):** 1 aviso  
**INE:** 34069 | **PlanPublica:** provincia=34, municipio=069

## Resumen

Frómista **no dispone de web corporativa activa** (`fromista.es` sin respuesta). Toda la presencia
digital municipal pasa por la **sede electrónica espublico gestiona**
(`fromista.sedelectronica.es`). El planeamiento urbanístico vigente (NSPM + planes parciales y
gestión urbanística histórica) está centralizado en **PlanPublica / SiuCyL** (Junta de Castilla y
León). No hay visor urbanístico municipal ni listado público de concesiones de licencias
georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica (inicio) | https://fromista.sedelectronica.es/info | Redirect loop sin sesión previa |
| Tablón de anuncios | https://fromista.sedelectronica.es/board | Responde; sin filas urbanísticas visibles (sep 2026) |
| Catálogo de trámites | https://fromista.sedelectronica.es/dossier/.0 | Requiere cookie de sesión (warm-up vía `/board`) |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=34&municipio=069 | 16+ documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=34&municipio=069 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=34069 | Mapa interactivo regional |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NSPM** (Normas Subsidiarias de Planeamiento Municipal), aprobación definitiva **17/03/1999**
  (`cDocId=290924`, código `34074-PU-19990525-290924`).
- Suelo urbano no consolidado: **Sector 1** (`c_id_sect=34074Sector 1`, categoría SU-NC).

### Listado PlanPublica (PLAU) — cómo se presentan

Página HTML con tabla ordenable. Cada fila incluye tipo instrumento (PU/GU/CU), subtipo (PP, PE,
PAU, PPI…), fechas y enlace PDF vía `openDocumento.do?cDocId={id}`.

**Documentos identificados (sep 2026, extracto):**

| Tipo | Fecha | Título |
|------|-------|--------|
| PPI | 27/10/1997 | PLAN PARCIAL INDUSTRIAL SECTOR 4 |
| PPI | 21/04/1997 | PLAN PARCIAL INDUSTRIAL SECTOR 8 |
| PE | 24/07/2002 | Plan Especial de Ordenación de Usos del Monte de la Villa |
| PP | 22/07/2005 | PLAN PARCIAL DEL SECTOR-5 |
| PP | 26/03/2008 | PLAN PARCIAL DEL SECTOR 1B DE SUD |
| PAU | 16/08/2010 | PROYECTO DE ACTUACIÓN DEL POLÍGONO RESIDENCIAL CAMPONECHA |
| PP | 14/12/2010 | PLAN PARCIAL SECTOR 10 "EL CERCADO" |
| PAU | 11/08/2011 | Proyecto de Normalización y Urbanización UN 3-4 (NSPM mod. puntual) |

Códigos internos PlanPublica: **provincia=34** (Palencia), **municipio=069** (Frómista).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board`)

Tabla HTML espublico con columnas:
`Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha de Publicación`

- **Sin licencias de obra** en la ventana visible (sep 2026).
- PDFs en `https://fromista.sedelectronica.es/preview-document/{uuid}`.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos / formularios de solicitud (no histórico de concesiones). Relevantes:

| Trámite | URL |
|---------|-----|
| Declaración Responsable Obra Menor | `/catalog/t/f6e1eba2-d893-492e-806d-2c5b52df86a8` |
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Modificación o Renuncia de Licencia Urbanística | `/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Modificación del Planeamiento de Desarrollo | `/catalog/t/6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Planeamiento General (Modificación) | `/catalog/t/96514574-aca1-40e1-a800-e06485e6d016` |
| Solicitud de Actuación Urbanística | `/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f` |
| Solicitud de Aprobación de Planeamiento de Desarrollo | `/catalog/t/23c80d53-bdad-47a5-b731-f786c411e08d` |

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido Frómista |
|--------|-----|---------|---------------------|
| WFS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON/GML | **1 sector** SU-NC (Sector 1) |
| WFS instrumentos | `urbanismo:plau_cyl_instrumentos_ambito` | GeoJSON | **1 polígono** NSPM municipal |
| WMS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=34069` | JS/ArcGIS-like | Visor regional |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json
  &CQL_FILTER=n_mun='Frómista'
```

Propiedades útiles: `c_id_sect` (`34074Sector 1`), `n_num_sect` (`Sector 1`), `c_categ_sue=SU-NC`.

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (`com.espublico.expedientes.*`) sobre **Apache Wicket** + nginx |
| Web corporativa | **No activa** (`fromista.es` sin respuesta) |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_sectores` (1 polígono Sector 1 SU-NC); WFS
  `plau_cyl_instrumentos_ambito` (polígono NSPM municipal); cruce por código de sector en título
  PLAU.
- **Estrategia:** extraer `Sector N`, `PE-`, `PAU` del título → cruzar con WFS; fallback centroide
  `[42.2670, -4.5280]` + jitter.
- **Limitaciones:** licencias y tablón sin GIS; planes parciales históricos sin polígono WFS
  individual; SiUR no expone API directa al scrapeador.

## Limitaciones

- Sin web municipal activa: toda la info pasa por sede + JCYL.
- Tablón vacío de urbanismo en ventana visible.
- `/info` puede redirect loop sin sesión previa desde `/board`.
- Catálogo: formularios, no resoluciones históricas.

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla HTML (`doOpen`, fechas, títulos).
2. **WFS SIUCyL** → geometría por sector (`plau_cyl_sectores`, `plau_cyl_instrumentos_ambito`).
3. **Tablón sede** (`/board/`) → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias informativas (páginas `/catalog/t/{uuid}`).
5. **IDs:** `fromista-{lic|proy}-{sha256[:14]}`.
