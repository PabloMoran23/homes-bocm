# San Esteban de Gormaz — investigación portal ayuntamiento

**Municipio:** San Esteban de Gormaz (provincia Soria, Castilla y León)  
**Fecha:** 2026-09-02  
**BOCYL (referencia):** 2 avisos  
**INE:** 42171 | **DIR3:** L01421622

## Resumen

San Esteban de Gormaz dispone de **web corporativa WordPress** (`sanestebandegormaz.org`) orientada a
noticias y turismo, y **sede electrónica espublico gestiona** (`sanestebandegormaz.sedelectronica.es`)
con tablón de anuncios, catálogo de trámites y portal de transparencia. El planeamiento urbanístico
vigente (NUM + modificaciones puntuales + sectores) está centralizado en **PlanPublica / SiuCyL**
(Junta de Castilla y León). No hay visor urbanístico municipal propio; la geometría de sectores
proviene del WFS regional IDECyL.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.sanestebandegormaz.org | WordPress; noticias, sin sección urbanismo dedicada |
| Sede electrónica | https://sanestebandegormaz.sedelectronica.es/info | espublico gestiona |
| Tablón de anuncios | https://sanestebandegormaz.sedelectronica.es/board/ | Tabla HTML con preview-document |
| Catálogo de trámites | https://sanestebandegormaz.sedelectronica.es/dossier | Requiere cookie jar; ~107 trámites |
| Transparencia | https://sanestebandegormaz.sedelectronica.es/transparency | Sección 7 «Urbanismo, obras públicas y medio ambiente» (111 docs) |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=42&municipio=162 | 14 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=42&municipio=162 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html | Visor regional JCYL |

**Contacto:** Plaza Mayor 1, 42330 San Esteban de Gormaz · Tel. 975 350 002 · ayuntamiento@sanestebandegormaz.org

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Subsidiarias de Planeamiento) con múltiples **modificaciones puntuales** (MP 2–6, etc.).
- **Modificación nº 41** (2026): parcela viviendas protegidas calle Santa María — aprobación inicial en tablón (exp. 597/2024).
- **Modificación nº 8** plan especial asociada a la modificación 41.

### Listado PlanPublica (PLAU)

Página HTML con tabla ordenable. Cada fila incluye tipo instrumento (PU/GU/EU/SU), subtipo (NS, PE…),
fecha publicación y enlace PDF vía `openDocumento.do?cDocId={id}` o `doGoBoletin()`.

**Documentos identificados (sep 2026, muestra):**

| Título | Fecha | Notas |
|--------|-------|-------|
| MODIFICACIÓN PUNTUAL 6: Corrección error alineaciones calle Isaac García Alonso | 30/07/2001 | PU/NS |
| MODIFICACIÓN PUNTUAL 5: Reclasificación suelo, sector 2 la Tapiada | 30/07/2001 | PU/NS, exp. 80/01 |
| MODIFICACION PUNTUAL 2: CAMBIO DE ORDENANZA ZONA DE ENSANCHE | 15/01/1999 | PU/NS |
| MODIFICACION PUNTUAL 3: AMPLIACION ZONA 7 DEL SU: GRAN INDUSTRIA | 27/07/1999 | PU/NS |
| MODIFICACION PUNTUAL 4: REDUCCION ANCHURA C/EXTREMADURA | 01/12/2000 | PU/NS |

### Tablón de anuncios (sede)

Tabla HTML con columnas: Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha.
Enlaces `preview-document` a PDFs. Urbanismo reciente: Modificación 41 (planeamiento general, mar 2026).

### Trámites urbanísticos (dossier)

Catálogo espublico con trámites informativos: licencia urbanística, modificación planeamiento,
certificado urbanístico, actuación urbanística, etc. No publica concesiones georreferenciadas.

## 3. Licencias de obra

No hay dataset ni tablón de **concesiones** de licencias con coordenadas. El adapter recoge:

- Anuncios del tablón que mencionen licencias (pocos).
- Páginas informativas de trámites del dossier (solicitud licencia, comunicación previa, etc.).

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/ows`
  - Capas: `urbanismo:plau_cyl_sectores` (2 polígonos: AA PI, S2 La Tapiada),
    `urbanismo:plau_cyl_instrumentos_ambito` (1 polígono NUM)
  - SiUR visor regional: `https://idecyl.jcyl.es/siur/index.html`
- **Estrategia:** consulta WFS por `n_mun = 'San Esteban de Gormaz'`; enriquecer expedientes PLAU/tablón
  con polígono de sector si el título menciona código (p. ej. «sector 2 la Tapiada»); centroide municipal
  + jitter para el resto.
- **Limitaciones:** sin visor municipal; licencias sin georreferenciación; web corporativa sin datos GIS.

## 4. Limitaciones

- Web corporativa sin sección urbanismo ni API REST pública.
- Tablón con pocos anuncios de urbanismo activos (mayoría empleo/selección).
- Dossier requiere cookie jar (redirect loop sin sesión).
- PLAI sin documentos en información pública (sep 2026).
- Licencias: solo trámites informativos, no concesiones publicadas.
