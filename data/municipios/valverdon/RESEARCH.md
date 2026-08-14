# Valverdón — investigación portal ayuntamiento

**Municipio:** Valverdón (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-08-14  
**BOCYL (referencia):** 4 avisos  
**INE:** 37342 | **DIR3:** L01373420

## Resumen

Valverdón **no dispone de web corporativa propia**; toda la presencia digital municipal pasa por la
**sede electrónica espublico gestiona** (`valverdon.sedelectronica.es`). El planeamiento urbanístico
vigente (NUM + planes especiales de regularización + gestión urbanística) está centralizado en
**PlanPublica / SiuCyL** (Junta de Castilla y León). No hay visor urbanístico municipal ni listado
público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica (inicio) | https://valverdon.sedelectronica.es/info.0 | A veces lento/timeout; requiere UA y paciencia |
| Tablón de anuncios | https://valverdon.sedelectronica.es/board/ | Responde de forma fiable |
| Catálogo de trámites | https://valverdon.sedelectronica.es/dossier/.0 | Requiere cookie de sesión; ~50 s primera carga |
| Transparencia | https://valverdon.sedelectronica.es/transparency/ | Sección 7 «Urbanismo, obras públicas y medio ambiente» vacía (0 docs) |
| Directorio PAG | https://administracion.gob.es/...?codigoUnidad=L01373420 | Ficha DIR3 |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=342 | 11 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=342 | Sin documentos activos (ago 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37342 | Mapa interactivo regional |
| Datos abiertos Diputación | https://datosabiertossalamanca.es/dataset/planeamiento-urbanistico | Listado provincial (fuente JCYL) |

**Contacto:** Calle Concejo 2, 37115 Valverdón · Tel. 923 314 274 / 923 321 141 · aytovalverdon@gmail.com

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **13/06/2014** (`cDocId=290767`).
- Sustituye al antiguo **Plan Parcial Sector 3, Zorita** (1993).
- En suelo rústico aplican de forma **complementaria** las **NSAP** provinciales de Salamanca
  (Diputación), no como instrumento principal.

### Listado PlanPublica (PLAU) — cómo se presentan

Página HTML con tabla `#listado` ordenable. Cada fila incluye:

| Campo | Origen HTML |
|-------|-------------|
| Código expediente | `37342-{PU\|GU\|EU\|SU}-YYYYMMDD-{cDocId}` en `doOpen()` / `doGoBoletin()` |
| Tipo instrumento | `<span title="..."> PU / GU / EU / SU </span>` |
| Subtipo | PE, NUM, PAU, JC, ESU, PN, PP… |
| Fecha publicación | `DD/MM/YYYY` |
| Enlace PDF | `openDocumento.do?cDocId={id}` o árbol `openDocuIndice.do?cDocId={id}` |
| BOCYL | `doGoBoletin(cDocId, código)` |
| Mapa | botón SiUR `id=37342` |

**Documentos identificados (ago 2026):**

| cDocId | Código | Fecha | Título |
|--------|--------|-------|--------|
| 290767 | 37342-PU-20140613-290767 | 13/06/2014 | NORMAS URBANÍSTICAS MUNICIPALES |
| 295685 | 37342-PU-20190327-295685 | 27/03/2019 | PLAN ESPECIAL DEL ÁREA DE REGULARIZACIÓN PE-1 |
| 296127 | 37342-PU-20190925-296127 | 25/09/2019 | PLAN ESPECIAL DE REGULARIZACIÓN DEL ÁREA PE-2 |
| 297922 | 37342-GU-20220214-297922 | 14/02/2022 | Proyecto de urbanización PE-2, Vega de Abajo |
| 298740 | 37342-GU-20230105-298740 | 05/01/2023 | Proyecto de normalización asentamiento irregular PE-2, Vega de Abajo |
| 297453 | 37342-EU-20210712-297453 | 12/07/2021 | Junta de compensación AR-P1 |
| 297485 | 37342-EU-20210728-297485 | 28/07/2021 | Corrección errores JC AR-P1 |
| 297333 | 37342-EU-20210520-297333 | 20/05/2021 | Constitución JC AR-P2 (exp. 16/2021) |
| 297334 | 37342-SU-20210520-297334 | 20/05/2021 | Estatutos JC AR-P2 (exp. 16/2021) |
| 297671 | 37342-EU-20211020-297671 | 20/10/2021 | Junta de compensación AR-P2 |
| 278887 | 37342-PU-19931126-278887 | 26/11/1993 | Plan Parcial Sector 3, Zorita (histórico) |

**API / endpoints útiles:**

```
# Listado HTML
GET https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=342

# PDF directo
GET https://servicios.jcyl.es/PlanPublica/openDocumento.do?cDocId={id}

# Árbol de documentos (lista PDFs por carpeta)
GET https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId={id}
# PDFs embebidos: http://www.jcyl.es/plaupdf//37/37342/{cDocId}/CARATULA.pdf

# Búsqueda avanzada (todos los municipios CyL)
GET https://servicios.jcyl.es/PlanPublica/cavanz_plau.do
```

Códigos internos PlanPublica: **provincia=37** (Salamanca), **municipio=342** (Valverdón).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla HTML espublico con columnas:

`Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha de Publicación`

- Anuncios recientes (jul–ago 2026): cobranza IAE, anexo cuadrante hogar jubilado, ordenanzas
  fiscales (cementerio, piscinas, residuos).
- **Sin licencias de obra** en la ventana visible (~5–7 filas).
- PDFs en `https://valverdon.sedelectronica.es/preview-document/{uuid}`.
- Sin paginador público evidente; ventana corta.

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

**No existe** dataset ni visor de licencias concedidas con coordenadas.

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido Valverdón |
|--------|-----|---------|---------------------|
| WFS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON/GML | **4 sectores** SU-NC: UNC1–UNC4 |
| WMS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*`, `ot_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=37342` | JS/ArcGIS-like | Visor regional (no API scrapeable) |
| PlanPublica mapa | `https://servicios.jcyl.es/PlanPublica/mapa.jsp` | JSP | Mapa provincial, no municipal dedicado |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json
  &CQL_FILTER=n_mun='Valverdón'
```

Propiedades útiles: `c_id_sect` (ej. `37342UNC3`), `n_num_sect`, `c_categ_sue`, `c_instrum=NUM`.

Capas adicionales con datos: `urbanismo:plau_cyl_instrumentos_ambito` (1 polígono municipal NUM).
`plau_cyl_planes_parciales`: 0 features.

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (`com.espublico.expedientes.*`) sobre **Apache Wicket** + nginx |
| Web corporativa | **No existe** (confirmado en directorios municipales y PAG) |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |
| Transparencia | Mismo stack Wicket; sección urbanismo vacía |

Fingerprints HTML: `wicket-ajax.js`, `com.espublico.expedientes.web.page`, `JSESSIONID` en cookies.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_sectores` (polígonos UNC1–4); centroide municipal para expedientes
  sin código de sector (PE-1, PE-2, juntas compensación).
- **Estrategia:** extraer `PE-1`, `PE-2`, `AR-P1`, `UNC{n}` del título → cruzar con WFS;
  fallback centroide `[41.0475, -5.7703]` + jitter.
- **Limitaciones:** licencias y tablón sin GIS; SiUR no expone WFS directo al scrapeador.

## Limitaciones

- Sin web municipal: toda la info pasa por sede + JCYL.
- Tablón: ventana muy corta, sin API ni paginación clara.
- `/info.0` y `/dossier` pueden timeout (>25 s) sin cookie de sesión previa.
- Catálogo: formularios, no resoluciones históricas.
- Transparencia urbanismo: 0 documentos publicados.

## Estrategia adapter recomendada

1. **PlanPublica PLAU** → parsear tabla `#listado` (`doOpen`, fechas, títulos vía `openDocuIndice.do`).
2. **WFS SIUCyL** → geometría por sector (`plau_cyl_sectores`, `plau_cyl_instrumentos_ambito`).
3. **Tablón sede** (`/board/`) → filtrar keywords urbanismo/licencia; PDFs `preview-document/{uuid}`.
4. **Catálogo dossier** → licencias informativas (páginas `/catalog/t/{uuid}`).
5. **IDs:** `valverdon-{lic|proy}-{sha256[:14]}`.
6. Modelar tras `villadangos_del_paramo` (CyL + espublico sede + WFS IDECyL).
