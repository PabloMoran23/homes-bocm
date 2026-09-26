# La Hoya — investigación portal ayuntamiento

**Municipio:** La Hoya (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-20  
**BOCYL (referencia):** 1 aviso  
**INE:** 37163 | **DIR3:** L01371630

## Resumen

La Hoya **no dispone de web corporativa propia**; la presencia digital municipal pasa por la
**sede electrónica espublico gestiona** (`lahoya.sedelectronica.es`). El planeamiento urbanístico
vigente (NUM con 4 sectores de suelo urbanizable) está centralizado en **PlanPublica / SiuCyL**
(Junta de Castilla y León). No hay visor urbanístico municipal ni listado público de concesiones
de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica (inicio) | https://lahoya.sedelectronica.es/info.0 | espublico gestiona / Wicket |
| Tablón de anuncios | https://lahoya.sedelectronica.es/board | Vacío (sep 2026) |
| Catálogo de trámites | https://lahoya.sedelectronica.es/dossier.0 | ~114 trámites; redirect interno |
| Transparencia | https://lahoya.sedelectronica.es/transparency/ | Sección 7 «Urbanismo…» (0 docs) |
| Diputación Salamanca | https://www.lasalina.es/...codMunicipio=163 | Ficha municipal |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=163 | 1 documento (NUM) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=163 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37163 | Mapa interactivo regional |

**Contacto:** C/ Eras, 1, 37716 La Hoya · Tel. 923 41 11 11 · concejodelahoya@hotmail.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **29/06/2016**, publicación BOCYL **22/09/2016** (`cDocId=293275`, código `37163-PU-20160922-293275`).
- Delimita **4 sectores de suelo urbanizable** (SUR-01 … SUR-04) accesibles vía WFS IDECyL.

### Listado PlanPublica (PLAU)

Página HTML con tabla `#listado`. Documento identificado:

| cDocId | Código | Fecha pub. | Título |
|--------|--------|------------|--------|
| 293275 | 37163-PU-20160922-293275 | 22/09/2016 | NORMAS URBANÍSTICAS MUNICIPALES |

**Endpoints útiles:**

```
GET https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=163
GET https://servicios.jcyl.es/PlanPublica/openDocumento.do?cDocId=293275
```

Códigos PlanPublica: **provincia=37** (Salamanca), **municipio=163** (La Hoya, INE 37163).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board`)

- Tabla HTML espublico (columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha).
- **Sin anuncios visibles** en sep 2026 (0 filas con `preview-document`).
- PDFs habituales en `https://lahoya.sedelectronica.es/preview-document/{uuid}`.

### Catálogo de trámites (`/dossier.0`)

Trámites informativos (no histórico de concesiones). Relevantes para urbanismo:

| Trámite | URL |
|---------|-----|
| Declaración Responsable o Comunicación en Materia Urbanística | `/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Modificación o Renuncia de Licencia Urbanística | `/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Modificación del Planeamiento de Desarrollo | `/catalog/t/6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Planeamiento General (Modificación) | `/catalog/t/96514574-aca1-40e1-a800-e06485e6d016` |
| Solicitud de Actuación Urbanística | `/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f` |

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido La Hoya |
|--------|-----|---------|-------------------|
| WFS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON/GML | **4 sectores** SUR-01…SUR-04 + **1 ámbito** NUM |
| WMS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=37163` | JS/ArcGIS-like | Visor regional |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json
  &CQL_FILTER=c_mun='37163'
```

Propiedades útiles: `c_id_sect` (ej. `37163SUR-01`), `n_num_sect`, `c_categ_sue=SUR`, `c_instrum=NUM`.

Capas con datos:
- `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono municipal NUM
- `urbanismo:plau_cyl_sectores` — 4 polígonos SUR-01…SUR-04
- `urbanismo:plau_cyl_planes_parciales` — 0 features

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (Apache Wicket) + nginx |
| Web corporativa | **No existe** |
| Planeamiento regional | **PlanPublica** (Junta CyL) |
| GIS regional | **GeoServer** IDECyL + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_sectores` (polígonos SUR-01…04) + `plau_cyl_instrumentos_ambito` (NUM).
- **Estrategia:** ingestar geometría desde WFS por sector; cruzar códigos SUR en títulos de tablón/PlanPublica; fallback centroide municipal `[40.408, -5.696]` + jitter.
- **Limitaciones:** tablón vacío; licencias solo como trámites informativos; SiUR no expone API scrapeable directa.

## Limitaciones

- Sin web municipal: toda la info pasa por sede + JCYL.
- Tablón vacío en la ventana visible.
- Catálogo: formularios, no resoluciones históricas.
- Transparencia urbanismo: 0 documentos publicados.

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla `#listado` (`doGoBoletin`, fechas, títulos).
2. **WFS SIUCyL** → geometría por sector (`plau_cyl_sectores`, `plau_cyl_instrumentos_ambito`).
3. **Tablón sede** (`/board`) → filtrar keywords urbanismo/licencia (vacío actualmente).
4. **Catálogo dossier** → licencias/proyectos informativos (`/catalog/t/{uuid}`).
5. **IDs:** `la-hoya-{lic|proy}-{sha256[:14]}`.
