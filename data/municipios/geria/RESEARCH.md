# Geria — investigación portal ayuntamiento

**Municipio:** Geria (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-09-17  
**BOCYL (referencia):** 1 aviso  
**INE:** 47071 | **PLAU mun:** 071

## Resumen

Geria publica su presencia digital a través de la **web de la Diputación de Valladolid**
(`geria.ayuntamientosdevalladolid.es`) y la **sede electrónica espublico gestiona**
(`geria.sedelectronica.es`). El planeamiento urbanístico vigente (NUM + planes parciales +
gestión urbanística) está centralizado en **PlanPublica / SiuCyL** (Junta de Castilla y León).
La geometría de ámbitos está disponible en el **WFS IDECyL** (sectores, planes parciales e
instrumento NUM). El tablón de anuncios de la sede está vacío (sin licencias concedidas
publicadas).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal (Diputación) | https://geria.ayuntamientosdevalladolid.es | SSL timeout desde entorno agente; accesible en navegador |
| Sede electrónica | https://geria.sedelectronica.es/info.0 | espublico gestiona (Wicket) |
| Tablón de anuncios | https://geria.sedelectronica.es/board/ | Vacío (0 filas, sep 2026) |
| Catálogo de trámites | https://geria.sedelectronica.es/dossier/.0 | ~111 trámites; requiere cookie de sesión |
| Normativa urbanística (web) | https://geria.ayuntamientosdevalladolid.es/el-ayuntamiento/administracion-municipal/normativa-urbanistica | PDFs normativa local |
| Urbanismo (web) | https://geria.ayuntamientosdevalladolid.es/el-municipio/urbanismo | Sección informativa |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=071 | 15 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=071 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=47071 | Mapa interactivo regional |

**Contacto:** C/ González de la Mata, 4 · 47131 Geria · Tel. 983 791 204 · ayuntamiento@geria.gob.es

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **30/10/2002** (`cDocId=281914`).
- Incluye modificaciones puntuales y planes parciales de sectores (PP SECTOR 01, etc.).

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Cada fila incluye tipo (PU/GU), subtipo (NUM/PP/PN/PAU…),
fechas, título y enlace `openDocumento.do?cDocId={id}`.

**Documentos identificados (sep 2026, muestra):**

| Subtipo | Fecha | Título |
|---------|-------|--------|
| NUM | 14/01/2010 | NORMAS URBANÍSTICAS MUNICIPALES |
| NUM | 02/07/2014 | MODIFICACIÓN PUNTUAL Nº 1 DE LAS NUM |
| PN | 20/05/2016 | PROYECTO DE NORMALIZACIÓN DE LA UN-10 CARRETERA DE PEÑAFIEL S/N |
| PAU | 20/05/2016 | PROYECTO DE URBANIZACIÓN DE LA UN-10 CARRETERA DE PEÑAFIEL S/N |
| PN | 28/10/2022 | PROYECTO DE LA UN-4 CALLE LOS ARENALES S/N. EXPTE.: 10/2022 |

### Licencias de obra

- No hay concesiones publicadas en el tablón `/board/` ni en `/info.0`.
- El catálogo de trámites incluye páginas informativas de licencias urbanísticas
  (Solicitud de Licencia o Autorización Urbanística, Declaración Responsable, etc.).
- El adapter devuelve estas páginas de trámite como filas informativas (`min_rows: 0` válido).

## 3. Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono NUM (c_mun=47071)
  - WFS `urbanismo:plau_cyl_sectores` — 17 sectores con geometría
  - WFS `urbanismo:plau_cyl_planes_parciales` — 4 planes parciales con geometría
  - SiUR visor: https://idecyl.jcyl.es/siur/index.html?id=47071
- **Estrategia:** consulta WFS por `n_mun='Geria'`; enriquecimiento por código de sector
  (`n_num_sect`, `c_id_sect`) cuando el título PLAU/tablón menciona sector o PP.
- **Limitaciones:**
  - Tablón vacío: sin geometría por expediente de licencia.
  - Web municipal con timeout SSL desde algunos entornos (no bloquea ingestión vía sede+PLAU+WFS).
  - Geometría WFS es del ámbito del instrumento/sector, no del expediente individual de licencia.

## 4. Limitaciones generales

- Sin API JSON pública de expedientes urbanísticos municipales.
- Licencias: solo trámites informativos, no concesiones georreferenciadas.
- Paginación PLAU: una sola página HTML (15 filas).
- Sede requiere `insecure_ssl: true` en algunos entornos.
