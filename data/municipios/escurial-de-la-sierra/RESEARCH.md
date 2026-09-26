# Escurial de la Sierra — investigación portal ayuntamiento

**Municipio:** Escurial de la Sierra (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-15  
**BOCYL (referencia):** 1 aviso  
**INE:** 37125 | **CIF:** P3712500B

## Resumen

Escurial de la Sierra **no dispone de web corporativa propia** (confirmado en ficha de la Diputación
de Salamanca). La presencia digital municipal pasa por la **sede electrónica espublico gestiona**
(`escurialdelasierra.sedelectronica.es`) y el canal informativo **Bandomovil**
(`bandomovil.com/escurialdelasierra`). El planeamiento urbanístico vigente (NUM) está centralizado en
**PlanPublica / SiuCyL** (Junta de Castilla y León). No hay visor urbanístico municipal ni listado
público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica (inicio) | https://escurialdelasierra.sedelectronica.es/info.0 | Requiere cookie de sesión + `insecure_ssl` en CI |
| Tablón de anuncios | https://escurialdelasierra.sedelectronica.es/board/ | 1 fila visible (ago 2026), sin urbanismo |
| Catálogo de trámites | https://escurialdelasierra.sedelectronica.es/dossier/.0 | ~74 KB HTML; trámites urbanísticos estándar espublico |
| Bandomovil (avisos) | https://www.bandomovil.com/escurialdelasierra | Avisos municipales (cortes agua, secretaría); sin urbanismo |
| Diputación Salamanca — ficha municipal | https://www.lasalina.es/Aplicaciones/GestorInter.jsp?codMunicipio=125&funcion=MuestraInformacionMunicipio&prestacion=Cipublico | INE 37125, sede, contacto |
| Diputación — normas urbanísticas | https://www.lasalina.es/Aplicaciones/GestorInter.jsp?codMunicipio=125&funcion=VerNormasUrbanisticas&nombre=Escurial+de+la+Sierra&prestacion=NormasUrbanisticas | Enlace a instrumentos provinciales |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=125 | 2 documentos NUM |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=125 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37125 | Mapa interactivo regional |

**Contacto:** Carretera de Tamames s/n, 37762 Escurial de la Sierra · Tel. 923 44 20 38 · aytoescurialdelasierra@gmail.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **17/12/2007** (`cDocId=283737`, BOCYL 10/04/2008).
- **Modificación NUM** suelo rústico, aprobación **19/11/2012** (`cDocId=289436`, BOCYL 14/05/2013).

### Sectores WFS (NUM vigente)

| Código | Sector | Categoría |
|--------|--------|-----------|
| 37125U1 | La Ermita | SU-NC |
| 37125U2 | Carretera Tejada | SU-NC |
| 37125D1 | La Iglesia | SUR |
| 37125D2 | Los Rodeos | SUR |
| 37125D3 | Carretera Hondura | SUR |

### Listado PlanPublica (PLAU) — cómo se presentan

Página HTML con tabla ordenable. Cada fila incluye libro (PU), instrumento (NUM), fechas y enlace PDF
vía `openDocumento.do?cDocId={id}`.

Códigos internos PlanPublica: **provincia=37** (Salamanca), **municipio=125** (Escurial de la Sierra).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla HTML espublico con columnas estándar. Único anuncio visible (feb 2021): contratación trabajadora
social CEAS Linares — **sin licencias de obra**.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos / formularios de solicitud (no histórico de concesiones). Relevantes:

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
| Solicitud de Aprobación de Planeamiento de Desarrollo | `/catalog/t/23c80d53-bdad-47a5-b731-f786c411e08d` |
| Solicitud de Recepción de Obras de Urbanización | `/catalog/t/e8594295-30ea-4a16-8f17-60c061a8a147` |

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido Escurial |
|--------|-----|---------|-------------------|
| WFS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON/GML | **5 sectores** (U1, U2, D1, D2, D3) + **1 instrumento** NUM |
| WMS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=37125` | JS/ArcGIS-like | Visor regional |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json
  &CQL_FILTER=n_mun='Escurial de la Sierra'
```

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (Apache Wicket + nginx) |
| Web corporativa | **No existe** |
| Avisos ciudadanos | **Bandomovil** (WordPress/Elementor) |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |
| Ficha provincial | **OpenCMS** (Diputación Salamanca, lasalina.es) |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_sectores` (5 polígonos U1/U2/D1/D2/D3); `plau_cyl_instrumentos_ambito` (1 MultiPolygon NUM municipal).
- **Estrategia:** ingestar sectores WFS como proyectos con `geom_geojson`; documentos PLAU NUM enlazan geometría del instrumento; licencias y tablón sin GIS.
- **Limitaciones:** licencias solo como trámites informativos; tablón sin anuncios urbanísticos recientes; sede requiere SSL relajado en entornos CI.

## Limitaciones

- Sin web municipal: toda la info pasa por sede + JCYL.
- Tablón: ventana muy corta, sin licencias de obra.
- Bandomovil: avisos de servicios, no expedientes urbanísticos.
- Catálogo: formularios, no resoluciones históricas.

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla HTML (2 NUM).
2. **WFS SIUCyL** → geometría por sector e instrumento municipal.
3. **Tablón sede** (`/board/`) → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias informativas (páginas `/catalog/t/{uuid}`).
5. **IDs:** `escurial-de-la-sierra-{lic|proy}-{sha256[:14]}`.
