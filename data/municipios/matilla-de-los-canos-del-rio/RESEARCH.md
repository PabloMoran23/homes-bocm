# Matilla de los Caños del Río — investigación portal ayuntamiento

**Municipio:** Matilla de los Caños del Río (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-08-30  
**BOCYL (referencia):** 2 avisos  
**INE:** 37187

## Resumen

Matilla de los Caños del Río publica la administración electrónica en la **sede espublico gestiona**
(`matilladeloscanos.sedelectronica.es`). La web corporativa `www.matilladeloscanos.es` responde con
error 500 (ago 2026). El planeamiento urbanístico vigente es una **DSU** (Delimitación de Suelo Urbano)
de 1977, centralizada en **PlanPublica** (Junta de Castilla y León). No hay listado público de
concesiones de licencias georreferenciadas; el tablón municipal solo publica anuncios generales.

El municipio está contratando la redacción de **Normas Urbanísticas Municipales** (licitación 54/2026).

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://matilladeloscanos.sedelectronica.es/ | espublico gestiona, Wicket |
| Tablón de anuncios | https://matilladeloscanos.sedelectronica.es/board/ | 4 documentos (ago 2026), sin urbanismo |
| Información pública | https://matilladeloscanos.sedelectronica.es/info.0 | Mismo formato tablón |
| Catálogo de trámites | https://matilladeloscanos.sedelectronica.es/dossier/.0 | ~100 trámites; requiere cookie sesión |
| Transparencia | https://matilladeloscanos.sedelectronica.es/transparency/ | Sección 7 «Urbanismo» vacía (0 docs) |
| Web corporativa | https://www.matilladeloscanos.es/ | HTTP 500 (ago 2026) |
| PlanPublica — PLAU | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=187 | 1 documento (DSU 1977) |
| PlanPublica — PLAI | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=187 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37187 | Mapa interactivo regional |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente (PlanPublica)

| cDocId | Código | Fecha | Título |
|--------|--------|-------|--------|
| 277904 | 37187-PU-A19770401-277904 | 01/04/1977 | DSU SIN ORDENANZAS (Delimitación de Suelo Urbano) |

**Formato:** tabla HTML `#listado` con columnas Libro / Subtipo / Fecha / Título. Enlaces PDF vía
`openDocumento.do?cDocId={id}`.

### Tablón sede (ago 2026)

Documentos publicados: convocatoria pleno, padrón electoral, cobranza IAE, bando incendios. Ninguno
es expediente urbanístico ni concesión de licencia.

### Licencias

No hay tablón de concesiones ni dataset de licencias. El adapter incluye páginas informativas de
trámites de licencia/urbanismo del catálogo espublico (sin fecha de concesión).

## 3. Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun='Matilla de los Caños del Río'`
  - SiUR visor JCyL: `https://idecyl.jcyl.es/siur/index.html?id=37187`
- **Estrategia:** descarga WFS por municipio; polígono del ámbito DSU (1 feature). Sin sectores ni
  planes parciales en capas `plau_cyl_sectores` / `plau_cyl_planes_parciales`.
- **Limitaciones:** instrumento único de 1977 sin geometría por expediente del tablón; licencias sin
  coords; web corporativa caída; sede requiere `insecure_ssl` por certificado intermedio.

## 4. Limitaciones generales

- Sin visor urbanístico municipal propio.
- Transparencia sección urbanismo vacía.
- Tablón sin licencias ni IP de planeamiento reciente.
- NUM en elaboración (licitación 2026); no publicada aún.
