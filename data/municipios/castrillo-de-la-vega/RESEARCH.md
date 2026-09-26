# Castrillo de la Vega — investigación portal ayuntamiento

**Municipio:** Castrillo de la Vega (provincia Burgos, Castilla y León)  
**Fecha:** 2026-09-12  
**BOCYL (referencia):** 1 aviso  
**INE:** 09085

## Resumen

Castrillo de la Vega combina **web corporativa Drupal (tema Toools)** con **sede electrónica espublico gestiona**.
El planeamiento urbanístico vigente (NUM + estudios de detalle) está en **PlanPublica / SiuCyL** (Junta de CYL).
No hay visor urbanístico municipal propio; la geometría del término municipal está en **IDECyL WFS**.
El tablón de anuncios de la sede no publica concesiones de licencias de obra (solo edictos administrativos).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://www.castrillodelavega.es | Drupal 9, tema Toools |
| Normativa / urbanismo | https://www.castrillodelavega.es/normativa | Ordenanza CT + modificaciones NUM |
| Sede electrónica | https://castrillodelavega.sedelectronica.es | espublico gestiona (Wicket) |
| Tablón de anuncios | https://castrillodelavega.sedelectronica.es/board | Sin licencias de obra (ago 2026) |
| Catálogo de trámites | https://castrillodelavega.sedelectronica.es/dossier | Requiere cookie de sesión |
| Transparencia | https://castrillodelavega.sedelectronica.es/transparency | |
| OVC Diputación Burgos | https://ovc.diputaciondeburgos.es/ | Enlace desde web municipal |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=09&municipio=085 | 6 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=09&municipio=085 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=09085 | Mapa interactivo regional |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **20/10/2005** (`cDocId=283565`).
- **Ordenanza Nº 1: Casco Tradicional CT** — publicada en web Drupal (`/node/863`) con PDFs.
- Estudios de detalle: ED-1 (2008), ED-3 modificación (2013), ED Casco Tradicional (2012).
- Modificaciones NUM recientes: 2020 (cambios alineaciones, costanilla nº 9).

### Páginas semilla Drupal

| URL | Contenido |
|-----|-----------|
| `/normativa` | Índice normativa urbanística |
| `/node/863` | Ordenanza Casco Tradicional CT (2 PDFs) |
| `/node/864` | Aprobación inicial modificación puntual NUM (12 PDFs) |
| `/node/865` | Modificaciones puntuales Nº 2 y 3 NUM |

### Listado PlanPublica (PLAU)

Tabla HTML con filas `PU NUM/ED`. Enlaces vía `openDocumento.do?cDocId={id}`.

| cDocId | Fecha | Título |
|--------|-------|--------|
| 283565 | 21/11/2005 | NORMAS URBANÍSTICAS MUNICIPALES |
| 284599 | 01/02/2008 | ESTUDIO DE DETALLE DE LA ZONA ED-1 |
| 289194 | 26/02/2013 | MODIFICACIÓN DEL ESTUDIO DETALLE ED-3 |
| 288811 | 06/11/2012 | ESTUDIO DETALLE ORDENANZA Nº 1 CASCO TRADICIONAL |
| 296638 | 08/07/2020 | MODIFICACIÓN NUM (cambios alineaciones) |
| 296459 | 10/03/2020 | MODIFICACIÓN NUM (costanilla nº 9) |

## 3. Licencias de obra

- **Tablón sede:** sin concesiones de licencias urbanísticas (solo anuncios BOP/juez de paz).
- **Catálogo trámites:** páginas informativas de solicitud de licencia, comunicación previa, DR urbanística, etc.
- Estrategia adapter: trámites del catálogo espublico como filas informativas (`min_rows` acepta 0 concesiones reales).

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS: `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores`
  - Filtro: `n_mun = 'Castrillo de la Vega'` o `c_mun = '09085'`
  - SiUR: `https://idecyl.jcyl.es/siur/index.html?id=09085`
- **Estrategia:** query WFS con `outputFormat=application/json&srsName=EPSG:4326`; polígono del ámbito NUM para instrumentos; sectores/ED si existen en capas.
- **Limitaciones:**
  - Sin visor municipal con enlace expediente→geometría.
  - Licencias del tablón sin coords; el orquestador aplica centroide municipal + jitter.
  - Geometría WFS disponible a nivel de instrumento/sector, no por expediente individual del tablón.

## 4. Limitaciones técnicas

- Sede `dossier` requiere cookie JSESSIONID (primera carga ~2–5 s).
- Web Drupal con PageSpeed; rutas PDF relativas bajo `/sites/castrillodelavega/files/`.
- WAF F5/Volt ADC bloquea peticiones `urllib` (respuesta «Request Rejected»); `curl`/navegador OK. El adapter prioriza PLAU/WFS; semillas Drupal quedan como fallback documentado.
- PLAI sin documentos en información pública activa.
- OVC Diputación Burgos enlazado pero sin API directa al expediente municipal.
