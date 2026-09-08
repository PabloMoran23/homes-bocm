# Bembibre — investigación portal ayuntamiento

**Municipio:** Bembibre (provincia León, Castilla y León, comarca El Bierzo)  
**Fecha:** 2026-09-08  
**BOCYL (referencia):** 1 aviso  
**INE:** 24014 | **DIR3:** L01240140

## Resumen

Bembibre dispone de **web corporativa** (`aytobembibre.es`) y **sede electrónica espublico gestiona**
(`aytobembibre.sedelectronica.es`). El planeamiento urbanístico vigente (PGOU 2005 + modificaciones
puntuales, planes parciales industriales, sector SUR nº10 Parras) está centralizado en
**PlanPublica / SiuCyL**. No hay visor urbanístico municipal propio; la geometría de sectores e
instrumentos está en **IDECyL WFS**. El tablón de anuncios no publica concesiones de licencias de obra
en la ventana visible.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.aytobembibre.es | Canal informativo; **timeout/SSL** desde entornos CI |
| Sede electrónica | https://aytobembibre.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://aytobembibre.sedelectronica.es/board/ | Responde; ~10 anuncios (contratación, padrón, subvenciones) |
| Catálogo de trámites | https://aytobembibre.sedelectronica.es/dossier/.0 | ~114 trámites; requiere cookie de sesión |
| Inicio sede (`/info.0`) | https://aytobembibre.sedelectronica.es/info.0 | **Bucle de redirección** (evitar) |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=014 | **15 documentos** |
| PlanPublica — info pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=014 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=24014 | Mapa interactivo regional |
| Listado municipios PLAU | https://servicios.jcyl.es/PlanPublica/lmuni_plau.do?provincia=24 | Código interno **014** (no confundir con 015=Benavides) |

**Contacto:** Plaza Mayor 1, 24300 Bembibre · Tel. 987 51 00 01 · registro@aytobembibre.es

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **PGOU** (Plan General de Ordenación Urbana), aprobación **26/09/2005**.
- Planes parciales industriales: P-I-2 / PI-3 Parque Industrial Bierzo Alto, PE Villavieja.
- Múltiples **modificaciones puntuales** del PGOU (2007–2011): convenios urbanísticos, sistemas
  generales de vías (AA-13N), sector Parras (SUR nº10), etc.

### Listado PlanPublica (PLAU) — cómo se presentan

Página HTML con tabla ordenable. Cada fila incluye tipo instrumento (PU/GU/EU/SU), subtipo, fecha
`DD/MM/YYYY`, título y enlace PDF vía `openDocumento.do?cDocId={id}`.

**Documentos identificados (sep 2026, 15 filas):**

| Fecha | Título (resumen) |
|-------|------------------|
| 26/09/2005 | PLAN GENERAL DE ORDENACIÓN URBANA |
| 01/10/2004 | PLAN PARCIAL PI-3 POLÍGONO INDUSTRIAL "EL BIERZO ALTO" |
| 06/03/1995 | PLAN PARCIAL INDUSTRIAL P-I-2 PARQUE BIERZO ALTO |
| 03/11/1998 | PLAN ESPECIAL DEL CONJUNTO HISTÓRICO «VILLAVIEJA» |
| 25/06/2010 | MODIFICACIÓN PUNTUAL 10/2009 (Supinilla) |
| … | +10 modificaciones puntuales PGOU (2007–2011) |

Códigos PlanPublica: **provincia=24** (León), **municipio=014** (Bembibre).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board/`)

Tabla espublico: Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha.

- Anuncios recientes (ago–sep 2026): contratación dumper, padrón IBI, mercados, subvenciones deportivas.
- **Sin licencias de obra** en la ventana visible.
- PDFs en `preview-document/{uuid}`.

### Catálogo de trámites (`/dossier/.0`)

Trámites informativos relevantes (no histórico de concesiones):

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

| Fuente | URL | Formato | Contenido Bembibre |
|--------|-----|---------|---------------------|
| WFS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON | **1** instrumento + **3** planes parciales + **20** sectores |
| WMS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wms` | WMS 1.3.0 | Capas `plau_cyl_*` |
| SiUR visor | `https://idecyl.jcyl.es/siur/index.html?id=24014` | JS/ArcGIS-like | Visor regional |

**No hay:** visor urbanístico municipal propio, ArcGIS municipal, WFS local.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Bembibre'
```

Sectores ejemplo: SUR Sector nº10 Parras, SU-NC U 9 Noceda de Viñales, U 4Bis Río Esla.

## 5. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Web corporativa | WordPress (aytobembibre.es) — inaccesible/timeout en CI |
| Sede electrónica | **espublico gestiona** (Apache Wicket + nginx) |
| Planeamiento regional | **PlanPublica** — portal Java/JSP (Junta CyL) |
| GIS regional | **GeoServer** (IDECyL) + visor **SiUR** |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_sectores` (20 polígonos), `plau_cyl_planes_parciales` (3),
  `plau_cyl_instrumentos_ambito` (1 polígono PGOU); SiUR visor regional.
- **Estrategia:** ingestar features WFS por municipio; cruzar códigos sector (SUR, SU-NC, PI-3, AA-*)
  del título PLAU/tablón con `n_num_sect` / `c_id_sect`; fallback centroide municipal + jitter.
- **Limitaciones:** licencias y tablón sin GIS; web corporativa inestable; `/info.0` con bucle redirect.

## Limitaciones

- Web corporativa: timeout/SSL desde entornos automatizados.
- Tablón: ventana corta sin licencias urbanísticas.
- `/info.0`: bucle de redirección infinito.
- Catálogo: formularios informativos, no resoluciones históricas.

## Estrategia adapter

1. **WFS IDECyL** → geometría de sectores/instrumentos (24 features).
2. **PlanPublica PLAU** → parsear tabla HTML (15 documentos PGOU/PE/MP).
3. **Tablón sede** (`/board/`) → filtrar keywords urbanismo/licencia.
4. **Catálogo dossier** → licencias informativas (`/catalog/t/{uuid}`).
5. **IDs:** `bembibre-{lic|proy}-{sha256[:14]}`.
