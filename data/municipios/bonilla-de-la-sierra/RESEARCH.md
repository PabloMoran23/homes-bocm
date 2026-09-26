# Bonilla de la Sierra — investigación portal ayuntamiento

**Municipio:** Bonilla de la Sierra (provincia Ávila, Castilla y León)  
**Fecha:** 2026-09-09  
**BOCYL (referencia):** 1 aviso  
**INE:** 05038

## Resumen

Bonilla de la Sierra dispone de **web corporativa WordPress** orientada a turismo y patrimonio
(`bonilladelasierra.com`) y **sede electrónica espublico gestiona**
(`bonilladelasierra.sedelectronica.es`). El planeamiento urbanístico vigente es mínimo: el municipio
figura como **«Sin Planeamiento General» (SPG)** en PlanPublica/SiuCyL, con aplicación de las
**NSAP provinciales de Ávila** (Diputación). No hay visor urbanístico municipal ni listado público
de licencias de obra georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://bonilladelasierra.com/ | WordPress + Divi; turismo, patrimonio, contacto |
| Ayuntamiento (WP) | https://bonilladelasierra.com/ayuntamiento/ | Enlaces a sede, bandos y transparencia |
| Sede electrónica | https://bonilladelasierra.sedelectronica.es/info.0 | espublico gestiona (Wicket) |
| Tablón de anuncios | https://bonilladelasierra.sedelectronica.es/board | 2 anuncios visibles (ago 2026); sin urbanismo |
| Catálogo de trámites | https://bonilladelasierra.sedelectronica.es/dossier/.0 | ~114 trámites; requiere cookie de sesión |
| Transparencia | https://bonilladelasierra.sedelectronica.es/transparency | Sección 7 «Urbanismo…» con **0 documentos** |
| PlanPublica — PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=038 | 1 documento (NSAP) |
| PlanPublica — PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=05&municipio=038 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=05038 | Mapa interactivo regional |

**Contacto:** Plaza 1, 05514 Bonilla de la Sierra · Tel. 920 362 708 · bonilla@diputacionavila.es

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **SPG** — Sin Planeamiento General (estado en PlanPublica).
- **NSAP** — Normas Subsidiarias de Ámbito Provincial (Diputación de Ávila), aprobación
  **22/09/1997** (`cDocId=295481`).

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Documento identificado:

| cDocId | Tipo | Fecha | Título |
|--------|------|-------|--------|
| 295481 | PU / NSAP | 22/09/1997 | NORMAS SUBSIDIARIAS DE PLANEAMIENTO MUNICIPAL CON ÁMBITO PROVINCIAL |

**Endpoints:**

```
GET https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=05&municipio=038
GET https://servicios.jcyl.es/PlanPublica/openDocumento.do?cDocId=295481
```

Códigos PlanPublica: **provincia=05** (Ávila), **municipio=038** (Bonilla de la Sierra).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board`)

Tabla HTML espublico. Anuncios visibles (jul 2026): cobranza IAE, denuncia telemática Guardia Civil.
**Sin licencias de obra** en la ventana visible.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos relevantes (no histórico de concesiones):

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

| Fuente | URL | Formato | Contenido Bonilla |
|--------|-----|---------|-------------------|
| WFS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON | **1** polígono `plau_cyl_instrumentos_ambito` (SPG municipal) |
| WMS SIUCyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=05038` | JS/ArcGIS-like | Visor regional |

**No hay:** visor urbanístico municipal propio, sectores/parcelas (`plau_cyl_sectores`: 0 features).

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeNames=urbanismo:plau_cyl_instrumentos_ambito
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Bonilla de la Sierra'
```

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Web corporativa | **WordPress** + Divi + Yoast SEO |
| Sede electrónica | **espublico gestiona** sobre **Apache Wicket** |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_instrumentos_ambito` (polígono municipal SPG); SiUR visor regional.
- **Estrategia:** extraer polígono municipal vía WFS; cruzar expedientes PLAU con geometría del
  instrumento; fallback centroide `[40.5298, -5.2672]` + jitter.
- **Limitaciones:** sin sectores ni parcelas; tablón y licencias sin GIS; transparencia urbanismo vacía.

## Limitaciones

- Web corporativa sin sección de urbanismo (solo turismo/patrimonio).
- Tablón: ventana corta, sin licencias de obra.
- `/dossier` requiere cookie de sesión (~5 s primera carga).
- Catálogo: formularios informativos, no resoluciones históricas.
- Transparencia urbanismo: 0 documentos publicados.

## Estrategia adapter

1. **PlanPublica PLAU** → parsear tabla HTML (`doOpen`, fechas, títulos).
2. **WFS SIUCyL** → geometría del instrumento municipal (`plau_cyl_instrumentos_ambito`).
3. **Tablón sede** (`/board`) → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias informativas (`/catalog/t/{uuid}`).
5. **IDs:** `bonilla-de-la-sierra-{lic|proy}-{sha256[:14]}`.
