# Villasur de Herreros — investigación portal ayuntamiento

**Municipio:** Villasur de Herreros (provincia Burgos, Castilla y León)  
**Fecha:** 2026-08-23  
**BOCYL (referencia):** 3 avisos  
**INE:** 09463

## Resumen

Villasur de Herreros dispone de **web corporativa Drupal** (tema Toools, red Diputación de Burgos)
sin sección dedicada de urbanismo. El planeamiento urbanístico vigente (NUM + sectores) está
centralizado en **PlanPublica / SiuCyL** (Junta de Castilla y León). La **sede electrónica
espublico gestiona** publica tablón de anuncios y catálogo de trámites. No hay visor urbanístico
municipal ni listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.villasurdeherreros.es/inicio | Drupal Toools; sin sección urbanismo |
| Sede electrónica | https://villasurdeherreros.sedelectronica.es/ | espublico gestiona (Wicket) |
| Tablón de anuncios | https://villasurdeherreros.sedelectronica.es/board | 1 anuncio visible (no urbanismo) |
| Catálogo de trámites | https://villasurdeherreros.sedelectronica.es/dossier | ~74 KB; requiere cookie de sesión |
| Transparencia | https://villasurdeherreros.sedelectronica.es/transparency | Sin documentos urbanismo |
| Normativa web | https://www.villasurdeherreros.es/normativa | Sin PDFs urbanísticos |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=463 | 5 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=463 | Sin documentos activos (ago 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=09463 | Mapa interactivo regional |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **15/10/2014** (`cDocId=291201`).
- 8 sectores de planeamiento (SUR SE1–SE5, SU-NC SE1–SE3) en IDECyL WFS.
- Entidad menor **Urrez** incluida en el término municipal.

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Cada fila incluye tipo instrumento (PU), subtipo (NUM/ED),
fechas y enlace PDF (`openDocumento.do?cDocId={id}`).

**Documentos identificados (ago 2026):**

| cDocId | Fecha | Subtipo | Título |
|--------|-------|---------|--------|
| 286115 | 25/11/2010 | ED | Estudio de detalle y proyecto de actuación finca urbana nº 320 polígono 609 de Urrez |
| 291201 | 15/10/2014 | NUM | Normas Urbanísticas Municipales |
| 296757 | 15/10/2015 | ED | Estudio de detalle parcelas calle La Bolera nº 62 y 64 de Urrez |
| 300540 | 25/08/2020 | NUM | Modificación NUM — reclasificación terrenos Urrez a suelo urbano consolidado 104 m² |
| 296757 | 06/03/2025 | NUM | Modificación NUM — cambio clasificación parcela SUR SE5 |

Códigos PlanPublica: **provincia=09** (Burgos), **municipio=463** (Villasur de Herreros).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board`)

Tabla HTML espublico con columnas: Documento | Expediente | Procedimiento | Categoría |
Descripción | Fecha de Publicación.

- Anuncio visible (ago 2026): solicitud suertes de leña 2027 (no urbanismo).
- PDFs en `https://villasurdeherreros.sedelectronica.es/preview-document/{uuid}`.
- Sin licencias de obra en ventana visible.

### Catálogo de trámites (`/dossier`)

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

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido Villasur |
|--------|-----|---------|-------------------|
| WFS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/ows` | GeoJSON | **8 sectores** + **1 ámbito NUM** |
| WMS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=09463` | Ionic/ArcGIS-like | Visor regional |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

### Sectores WFS (ago 2026)

| Código | Nombre |
|--------|--------|
| SUR SE1 | SECTOR SUR SE1 "ERAS DE ENMEDIO" |
| SUR SE2 | SECTOR SUR SE2 "ERAS ALTAS" |
| SUR SE3 | SECTOR SUR SE3 "VILLALAGAR" |
| SUR SE4 | SECTOR SUR SE4 "LA DEHESA" |
| SUR SE5 | SECTOR SUR SE5 "LAS CABEZADAS" |
| SU-NC SE1 | SECTOR SU-NC SE1 "CAMINO DE LA MINA" |
| SU-NC SE2 | SECTOR SU-NC SE2 "LA CALLEJA" |
| SU-NC SE3 | SECTOR SU-NC SE3 "PONTÓN" |

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/ows
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Villasur de Herreros'
```

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Web corporativa | **Drupal** (tema Toools, red ayuntamientos Burgos) |
| Sede electrónica | **espublico gestiona** sobre **Apache Wicket** |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_sectores` (8 polígonos sectoriales); `plau_cyl_instrumentos_ambito`
  (1 polígono ámbito NUM); SiUR visor regional (`id=09463`).
- **Estrategia:** ingestar geometría WFS por sector; cruzar códigos `SUR SE5`, `SU-NC SE1`, etc.
  en títulos PlanPublica; NUM → polígono ámbito municipal; fallback centroide `[42.2892, -3.3418]`.
- **Limitaciones:** licencias y tablón sin GIS; estudios de detalle (ED) sin polígono WFS dedicado;
  SiUR no expone API scrapeable.

## Limitaciones

- Web municipal sin sección urbanismo (solo normativa general vacía).
- Tablón: ventana corta, sin licencias de obra visibles.
- `/dossier` requiere cookie de sesión (carga previa de `/board`).
- Catálogo: formularios informativos, no resoluciones históricas.
- Transparencia: sin documentos de urbanismo.

## Estrategia adapter

1. **WFS IDECyL** → geometría por sector y ámbito NUM.
2. **PlanPublica PLAU** → parsear tabla HTML (`doOpen`, fechas, títulos).
3. **Tablón sede** (`/board`) → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias/trámites informativos (`/catalog/t/{uuid}`).
5. **IDs:** `villasur-de-herreros-{lic|proy}-{sha256[:14]}`.
