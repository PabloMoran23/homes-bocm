# Carracedelo — investigación portal ayuntamiento

**Municipio:** Carracedelo (provincia León, Castilla y León)  
**Fecha:** 2026-09-11  
**BOCYL (referencia):** 1 aviso  
**INE:** 24038

## Resumen

Carracedelo **no dispone de web corporativa operativa** (`www.carracedelo.es` responde 500 y redirige a la
sede). Toda la presencia digital municipal pasa por la **sede electrónica espublico gestiona**
(`carracedelo.sedelectronica.es`). El planeamiento urbanístico vigente (NUM) está centralizado en
**PlanPublica / SiuCyL** (Junta de Castilla y León). No hay visor urbanístico municipal ni listado
público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.carracedelo.es | Error 500; redirige a sede |
| Sede electrónica (inicio) | https://carracedelo.sedelectronica.es/info.0 | espublico gestiona / Wicket |
| Tablón de anuncios | https://carracedelo.sedelectronica.es/board/ | Tabla HTML con preview-document |
| Catálogo de trámites | https://carracedelo.sedelectronica.es/dossier/.0 | ~70 KB; requiere cookie sesión |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=038 | 2 documentos NUM (2024) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=038 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=24038 | Mapa interactivo regional |

Códigos PlanPublica: **provincia=24** (León), **municipio=038** (INE 24038).

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **29/02/2024** (`cDocId=299785`).
- Corrección de errores **29/02/2024** (`cDocId=299824`).

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Campos: tipo (PU), subtipo (NUM), fechas, título, enlaces
`openDocumento.do?cDocId={id}` y BOCYL via `doGoBoletin()`.

| cDocId | Código | Fecha | Título |
|--------|--------|-------|--------|
| 299785 | 24038-PU-20240418-299785 | 18/04/2024 | NORMAS URBANÍSTICAS MUNICIPALES |
| 299824 | 24038-PU-20240506-299824 | 06/05/2024 | CORRECCIÓN DE ERRORES DE LAS NORMAS URBANÍSTICA MUNICIPALES |

### Sectores WFS (IDECyL)

10 sectores con geometría MultiPolygon: UR-1..UR-6 (suelo urbano no consolidado), SUR-1 (suelo urbanizable),
etc. Ejemplos: Vayelo I (UR-1), La Pradela (SUR-1), El Matagal (UR-6).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla espublico: `Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha`.

Ventana visible (sep 2026): subvenciones, cobros agua/basura, empleo público, PEF. **Sin licencias de obra**
ni urbanismo en la ventana actual.

PDFs: `https://carracedelo.sedelectronica.es/preview-document/{uuid}`.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos relevantes (no histórico de concesiones):

| Trámite | UUID |
|---------|------|
| Declaración Responsable o Comunicación en Materia Urbanística | 667c2405-5964-48b8-a504-9c64fe6a8836 |
| Solicitud de Licencia o Autorización Urbanística | 3eec8ea1-30dc-4373-a5f8-bfe9e5204172 |
| Solicitud de Modificación o Renuncia de Licencia Urbanística | a3c783fb-bb19-4ea3-b40f-0072d69aebae |
| Solicitud de Licencia de Ocupación | b834b3fa-3690-4626-9c92-d82669d6f26f |
| Solicitud de Certificado o Informe Urbanístico | e247f7c3-b1ff-42ef-8b7d-5195c14e9bbf |
| Modificación del Planeamiento de Desarrollo | 6e8237a3-0b83-469d-b0ad-70159b9a9c26 |
| Planeamiento General (Modificación) | 96514574-aca1-40e1-a800-e06485e6d016 |
| Solicitud de Actuación Urbanística | f91e4a50-d23d-45c1-a19b-b148da37c59f |

## 4. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (Apache Wicket) + nginx |
| Web corporativa | **No operativa** (500 / redirect) |
| Planeamiento regional | **PlanPublica** JSP (Junta CyL) |
| GIS regional | **GeoServer** IDECyL + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `available`
- **Fuentes:** WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` — capas
  `plau_cyl_sectores`, `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`;
  filtro `n_mun='Carracedelo'`; 10 polígonos sectoriales con códigos UR-n / SUR-n.
- **Estrategia:** ingestar features WFS directamente; cruzar códigos sector del título PLAU/tablón
  con `n_num_sect` / `c_id_sect`; centroide del polígono como lat/lon.
- **Limitaciones:** tablón y licencias sin GIS; SiUR no expone API scrapeable; web corporativa caída.

## Limitaciones

- Sin web municipal operativa.
- Tablón sin entradas urbanísticas en ventana actual.
- Catálogo: formularios, no resoluciones históricas de licencias.
- `/dossier/.0` requiere sesión cookie (~10 s primera carga).

## Estrategia adapter

1. **WFS IDECyL** → proyectos con `geom_geojson` (10 sectores + instrumento ámbito).
2. **PlanPublica PLAU** → parsear tabla HTML (2 docs NUM).
3. **Tablón sede** → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias informativas (`/catalog/t/{uuid}`).
5. **IDs:** `carracedelo-{lic|proy}-{sha256[:14]}`.
