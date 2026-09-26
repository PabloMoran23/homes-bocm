# Alaejos — investigación portal ayuntamiento

**Municipio:** Alaejos (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-09-05  
**BOCYL (referencia):** 1 aviso  
**INE:** 47004

## Resumen

Alaejos publica la actividad municipal principalmente en la **sede electrónica espublico gestiona**
(`alaejos.sedelectronica.es`). La web corporativa `www.alaejos.es` responde con error 500 (inactiva).
El planeamiento urbanístico vigente (NUM + reparcelación polígono industrial) está en **PlanPublica / SiuCyL**.
La cartografía sectorial está en **IDECyL WFS** (7 sectores + 1 polígono NUM).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.alaejos.es | HTTP 500 — inactiva |
| Sede electrónica | https://alaejos.sedelectronica.es/info.0 | espublico gestiona / Wicket |
| Tablón de anuncios | https://alaejos.sedelectronica.es/board/ | Tabla HTML con preview-document |
| Catálogo de trámites | https://alaejos.sedelectronica.es/dossier/ | `/dossier/.0` provoca bucle de redirección |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=004 | 3 documentos |
| PlanPublica — info pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=004 | Sin documentos activos (sep 2026) |
| SiUR visor | https://idecyl.jcyl.es/siur/index.html?id=47004 | Visor regional JCyL |

Códigos PlanPublica: **provincia=24** (Valladolid), **municipio=004** (INE 47004).

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **29/04/2021** (`cDocId=297371`).
- Proyectos de **reparcelación del polígono industrial** (PAU, 2023).

### Listado PlanPublica (PLAU)

| cDocId | Código | Fecha | Título |
|--------|--------|-------|--------|
| 297371 | 47004-PU-20210722-297476 | 09/06/2021 | NORMAS URBANÍSTICAS MUNICIPALES |
| 299061 | 47004-GU-20230518-299061 | 24/05/2023 | PROYECTO DE REPARCELACIÓN DEL POLÍGONO INDUSTRIAL EN CUANTO A SUPERFICIES |
| 298912 | 47004-GU-20230317-298912 | 23/03/2023 | PROYECTO DE REPARCELACIÓN DEL POLÍGONO INDUSTRIAL (modificado BOCYL 24/05/2023) |

Tabla HTML `#listado` con enlaces `openDocumento.do?cDocId={id}` y botón SiUR.

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla espublico: `Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha`.

- Anuncios recientes (ago–sep 2026): presupuesto, juntas de gobierno, padrones fiscales.
- **Urbanismo:** BOPVA 2026-144 — contribuciones especiales para urbanización calle Conventillo (30/07/2026).
- **Sin licencias de obra** concedidas en la ventana visible (~10 filas).
- PDFs: `https://alaejos.sedelectronica.es/preview-document/{uuid}`.

### Catálogo de trámites (`/dossier/`)

Trámites informativos relevantes (no histórico de concesiones):

| Trámite | URL |
|---------|-----|
| Declaración Responsable de Obras fuera del perímetro BIC | `/catalog/t/ba729040-e3e4-4b08-abf0-78b91d5048e4` |
| Declaración Responsable o Comunicación en Materia Urbanística | `/catalog/t/5d383e20-32a5-4fcf-8725-e51c51e83e6a` |
| Solicitud de Licencia o Autorización Urbanística | `/catalog/t/15fabacb-83b1-47d1-b435-508245672051` |
| Solicitud de Modificación o Renuncia de Licencia Urbanística | `/catalog/t/a3c783fb-bb19-4ea3-b40f-0072d69aebae` |
| Solicitud de Licencia de Ocupación | `/catalog/t/b834b3fa-3690-4626-9c92-d82669d6f26f` |
| Solicitud de Certificado o Informe Urbanístico | `/catalog/t/e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf` |
| Modificación del Planeamiento de Desarrollo | `/catalog/t/6e8237a3-0b83-469d-b0ad-70159b9a9c26` |
| Planeamiento General (Modificación) | `/catalog/t/96514574-aca1-40e1-a800-e06485e6d016` |
| Solicitud de Actuación Urbanística | `/catalog/t/f91e4a50-d23d-45c1-a19b-b148da37c59f` |
| Solicitud de Recepción de Obras de Urbanización | `/catalog/t/e8594295-30ea-4a16-8f17-60c061a8a147` |

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (Apache Wicket + nginx) |
| Web corporativa | **Inactiva** (HTTP 500) |
| Planeamiento regional | **PlanPublica** JSP (Junta CyL) |
| GIS regional | **GeoServer** IDECyL + visor SiUR |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `urbanismo:plau_cyl_sectores` — 7 polígonos (SUNC 1–4, SUR 01–03)
  - WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 MultiPolygon NUM municipal
  - SiUR visor: `https://idecyl.jcyl.es/siur/index.html?id=47004`
- **Estrategia:** descarga masiva WFS por `n_mun='Alaejos'`; cruce sector por código en título PLAU/tablón; fallback centroide `[41.3076, -5.2182]` + jitter.
- **Limitaciones:** licencias y tablón sin GIS; web corporativa caída; `/dossier/.0` con bucle de redirección (usar `/dossier/`).

## Limitaciones

- Sin web municipal operativa.
- Tablón: ventana corta, sin API ni paginación clara.
- Catálogo: formularios informativos, no resoluciones históricas.
- PLAI sin documentos activos.

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla HTML.
2. **WFS IDECyL** → geometría sectores + ámbito NUM.
3. **Tablón sede** → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias/proyectos informativos.
5. **IDs:** `alaejos-{lic|proy}-{sha256[:14]}`.
