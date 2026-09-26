# Calvarrasa de Abajo — investigación portal ayuntamiento

**Municipio:** Calvarrasa de Abajo (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-08-26  
**BOCYL (referencia):** 2 avisos  
**INE:** 37069 | **DIR3:** L01370690

## Resumen

Calvarrasa de Abajo combina **web corporativa WordPress Divi** (`calvarrasadeabajo.es`) con **sede electrónica espublico**
(`calvarrasadeabajo.sedelectronica.es`). El planeamiento urbanístico vigente (NUM + sectores SRAI/SUR/SUNC) está
centralizado en **PlanPublica / SiuCyL** (Junta de Castilla y León). La geometría de sectores está disponible en
**IDECyL WFS** (`c_mun=37069`, 31 polígonos). No hay visor urbanístico municipal propio ni listado público de
licencias de obra georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://calvarrasadeabajo.es/ | WordPress Divi; REST API restringida (401) |
| Área de urbanismo | https://calvarrasadeabajo.es/area-de-urbanismo/ | Enlace PlanPublica + Google Drive + modificación NUM SRAI-7 |
| Exposición pública | https://calvarrasadeabajo.es/exposicion-publica/ | PDFs (autorizaciones de uso parcelas 770/772) |
| Modelos de solicitudes | https://calvarrasadeabajo.es/modelos-de-solicitudes/ | Formularios descargables |
| Archivo planeamiento (Drive) | https://drive.google.com/file/d/1JrCnzVikIn4Cn9p3y83nDFA0hDMW0qpV/view | PDFs históricos |
| Sede electrónica | https://calvarrasadeabajo.sedelectronica.es/info.0 | espublico gestiona (Wicket); requiere `insecure_ssl` en CI |
| Tablón de anuncios | https://calvarrasadeabajo.sedelectronica.es/board | Tabla HTML con preview-document |
| Transparencia | https://calvarrasadeabajo.sedelectronica.es/transparency | Sección 7 «Urbanismo» (5 docs) |
| Catálogo trámites | https://calvarrasadeabajo.sedelectronica.es/dossier/.0 | Lento (~25 s); licencias y certificaciones |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?provincia=37&municipio=069 | ~15+ documentos (NUM, PP, PERI, PE SRAI-8…) |
| PlanPublica — info pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?provincia=37&municipio=069 | NUM en información pública |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37069 | Mapa interactivo regional |

**Contacto:** Plaza Mayor 1, 37181 Calvarrasa de Abajo · Tel. 923 306 024 · cultura@calvarrasadeabajo.es

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), revisión y adaptación 2009 (`cDocId=285151`).
- Múltiples **modificaciones puntuales** de NUM (SRAI-1, SRAI-7, SRAI-8, SUR-18, UN5…).
- **Plan Especial SRAI-8** (2016), planes parciales históricos (S-6, S-8, PERI área B).

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Campos: instrumento (PU/GU/EU), subtipo (NUM/PP/PE/PERI/ED…), fechas, título,
enlace `openDocumento.do?cDocId={id}`.

**Documentos identificados (ago 2026, extracto):**

| cDocId | Subtipo | Título |
|--------|---------|--------|
| 285151 | NUM | NORMAS URBANÍSTICAS MUNICIPALES (REVISIÓN Y ADAPTACIÓN) |
| 290336 | NUM | MODIFICACIÓN NUM — SRAI-8 |
| 290714 | NUM | MODIFICACIÓN NUM — ámbito SRAI-1 |
| 292754 | PE | PLAN ESPECIAL DEL SECTOR SRAI-8 |
| 292755 | NUM | MODIFICACIÓN NUM — sector SUR-18 |
| 294030 | NUM | MODIFICACIÓN NUM — unidad normalización 7 |
| 294386 | NUM | MODIFICACIÓN NUM — UN5 La Cabezuela |
| 290202 | PP | PLAN PARCIAL SECTOR SUR-2 |
| 288519 | ED | ESTUDIO DETALLE reparcelación Calle San José / Santa Ana |

### Web WordPress

- `/area-de-urbanismo/`: texto «MODIFICACIÓN DE NUM (ámbito territorial SRAI-7)» + enlace PlanPublica + Google Drive.
- `/exposicion-publica/`: autorizaciones de uso parcelas 770 y 772 (PDFs técnicos).
- API REST bloqueada (`rest_cannot_access`); scrape HTML Divi (`et_pb_module_header`).

## 3. Building licenses

### Tablón de anuncios

Tabla espublico: `Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha`.
Ventana corta (~1 fila visible ago 2026: notificación padrón). Sin licencias de obra en tablón.

### Catálogo sede (trámites informativos)

Trámites destacados en `/info.0`:

- Solicitud de Certificación Urbanística
- Solicitud de Licencia de Primera Ocupación
- Solicitud de Licencia Mayor de Obras
- Solicitud de Licencia de Segregación
- Declaración Responsable de Obras
- Comunicación Ambiental

No hay dataset histórico de concesiones con coordenadas.

### Web — autorizaciones de uso

PDFs en exposición pública: parcelas 770 y 772 (documentación técnica, no licencia de obra clásica).

## 4. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Web corporativa | **WordPress** + tema **Divi** (child) |
| Sede electrónica | **espublico gestiona** (Apache Wicket) |
| Planeamiento regional | **PlanPublica** JSP (Junta CyL) |
| GIS regional | **GeoServer** IDECyL + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `plau_cyl_sectores` (31 features, `c_mun=37069`), `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`
  - SiUR: `https://idecyl.jcyl.es/siur/index.html?id=37069`
- **Estrategia:** ingestar sectores WFS con polígono; cruzar códigos SRAI/SUNC/SUR del título PlanPublica → query WFS;
  fallback centroide municipal `[40.943, -5.528]` + jitter.
- **Limitaciones:** licencias y tablón sin GIS; SiUR no expone API directa; CQL_FILTER por `n_mun` puede timeout
  (usar `c_mun='37069'`).

## Limitaciones

- REST API WordPress restringida a usuarios autenticados.
- Sede `/info.0` puede devolver 302/timeout sin `insecure_ssl`.
- Tablón: ventana muy corta, sin paginación clara.
- Catálogo dossier: lento (~25 s primera carga).
- Licencias: solo trámites informativos + 2 autorizaciones de uso en web; sin concesiones georreferenciadas.

## Estrategia adapter

1. **IDECyL WFS** (`c_mun=37069`) → sectores con `geom_geojson`.
2. **PlanPublica PLAU/PLAI** → parsear tabla HTML (`cDocId`, fechas, títulos).
3. **WordPress Divi** → PDFs y blurbs en urbanismo/exposición pública.
4. **Sede espublico** → tablón + catálogo trámites (licencias informativas).
5. **IDs:** `calvarrasa-de-abajo-{lic|proy}-{sha256[:14]}`.
