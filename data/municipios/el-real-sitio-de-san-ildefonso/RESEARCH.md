# El Real Sitio de San Ildefonso — investigación portal ayuntamiento

**Municipio:** El Real Sitio de San Ildefonso (provincia Segovia, Castilla y León)  
**Fecha:** 2026-09-14  
**BOCYL (referencia):** 1 aviso  
**INE:** 40165 | **PLAU:** prov=40, mun=165

## Resumen

El municipio publica urbanismo en **WordPress** (`lagranja-valsain.com`, dominio histórico La Granja-Valsaín) con formularios PDF de trámites, y en la **sede electrónica espublico gestiona** (`realsitiodesanildefonso.sedelectronica.es`) con tablón y catálogo de trámites. El planeamiento vigente (PGOU adaptación 2011 + modificaciones) está centralizado en **PlanPublica / SiuCyL** (Junta de Castilla y León). No hay visor urbanístico municipal propio; la geometría de sectores está en **IDECyL WFS**.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web municipal | https://www.lagranja-valsain.com | WordPress, tema `sanildefonso` |
| Concejalía de Urbanismo | https://www.lagranja-valsain.com/ayuntamiento/concejalias/concejalia-de-urbanismo/ | Trámites PDF, enlaces PGOU |
| Declaración responsable | https://www.lagranja-valsain.com/ayuntamiento/concejalias/concejalia-de-urbanismo/declaracion-responsable/ | Enlace a sede + archivo JCyL |
| Sede electrónica | https://realsitiodesanildefonso.sedelectronica.es/ | espublico gestiona |
| Tablón de anuncios | https://realsitiodesanildefonso.sedelectronica.es/board | Tabla HTML con `preview-document` |
| Catálogo de trámites | https://realsitiodesanildefonso.sedelectronica.es/dossier | ~28 trámites urbanísticos |
| PlanPublica — PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=40&municipio=165 | 4 documentos aprobados |
| PlanPublica — PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=40&municipio=165 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=40165 | Mapa interactivo regional |

**Contacto urbanismo:** urbanismo@lagranja-valsain.com · Tel. 921 47 00 18 ext. 3203

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **PGOU (Adaptación)** aprobado definitivamente **25/11/2011** (Comisión Territorial de Urbanismo de Segovia).
- Sustituye/adapta el PGOU original de 1981.
- Modificaciones puntuales documentadas en PLAU (p. ej. sector «Las Eras», 2015).

### PlanPublica (PLAU) — documentos identificados

| Fecha pub. | Tipo | Título |
|------------|------|--------|
| 06/07/2005 | NUM | Normas Urbanísticas Municipales |
| 20/09/2006 | NUM | Modificación puntual reclasificación parcelas |
| 20/01/2010 | PORN | Plan Ordenación Recursos Naturales Sierra de Guadarrama |
| 22/09/2015 | NUM | Modificación puntual nº 2 sector «Las Eras» |

Cada fila enlaza a `openDocumento.do?cDocId={id}`.

### Sede — tablón

HTML estático con tabla (`<tbody>`). Campos: documento, expediente, procedimiento, categoría, descripción, fecha. PDF vía `preview-document/{uuid}`. En sep 2026 el tablón no contenía anuncios de urbanismo recientes (mayoría empleo/tributos).

### Sede — catálogo trámites urbanísticos

Incluye: declaración responsable urbanística, licencia/autorización urbanística, actuación urbanística, modificación planeamiento, certificado urbanístico, etc. Son páginas informativas (no listado de concesiones).

### Web — formularios licencias

PDFs en `/files/tramites/urbanismo/` (obra mayor, primera ocupación, licencia actividad, vado, consulta urbanística, etc.).

## 3. Licencias

No hay dataset público de concesiones georreferenciadas. Fuentes:

1. Tablón sede (cuando publica licencias/concesiones).
2. Catálogo de trámites sede (páginas informativas).
3. Formularios PDF en web municipal.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito` (1 polígono PGOU), `urbanismo:plau_cyl_sectores` (9 sectores: SUR-1/2, UNC-1..5, UNCA-1/2), `urbanismo:plau_cyl_planes_parciales`
  - Filtro: `n_mun = 'Real Sitio de San Ildefonso'`
  - SiUR visor: `https://idecyl.jcyl.es/siur/index.html?id=40165`
- **Estrategia:** ingestar features WFS con geometría; enriquecer documentos PLAU/tablón por código de sector (`SUR-1`, `UNC-5`, etc.) o subtipo NUM → polígono del instrumento.
- **Limitaciones:** sin visor municipal con enlace expediente↔polígono; licencias del tablón sin coords; `/info.0` y `/dossier/.0` provocan bucle de redirección (usar `/info` y `/dossier`).

## 4. Limitaciones

- Sin listado público de licencias concedidas con coordenadas.
- Tablón sede mezcla urbanismo con empleo/tributos/elecciones.
- Web no publica modificaciones de planeamiento en páginas separadas (sección vacía en HTML).
- PLAI sin documentos en exposición pública activa.

## 5. Adapter

- Módulo: `municipio/adapters/el_real_sitio_de_san_ildefonso.py`
- Fuentes: WFS IDECyL + PLAU + tablón sede + catálogo trámites + formularios WP
- IDs: `el-real-sitio-de-san-ildefonso-{lic|proy}-{sha256[:14]}`
