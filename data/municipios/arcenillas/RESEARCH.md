# Arcenillas — investigación portal ayuntamiento

**Municipio:** Arcenillas (provincia Zamora, Castilla y León)  
**Fecha:** 2026-09-07  
**BOCYL (referencia):** 1 aviso  
**INE:** 49010 | **PlanPublica municipio:** 010 (provincia 49)

## Resumen

Arcenillas combina **web corporativa WordPress** (`arcenillas.es`, tema Salient) con **sede electrónica espublico gestiona** (`arcenillas.sedelectronica.es`). El planeamiento urbanístico vigente (DSU — Delimitación de Suelo Urbano) y sus modificaciones puntuales están centralizados en **PlanPublica / SiuCyL** (Junta de Castilla y León). No hay visor urbanístico municipal ni listado público de concesiones de licencias georreferenciadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa | https://arcenillas.es | WordPress Salient; enlaces a sede, tablón, PLAU |
| Sede electrónica (inicio) | https://arcenillas.sedelectronica.es/info.0 | Requiere cookie jar; redirección desde `/info` |
| Tablón de anuncios | https://arcenillas.sedelectronica.es/board | Tabla espublico; sin licencias de obra visibles (ago 2026) |
| Catálogo de trámites | https://arcenillas.sedelectronica.es/dossier/.0 | ~111 trámites; requiere cookie jar |
| Transparencia | https://arcenillas.sedelectronica.es/transparency | Sección urbanismo sin documentos destacados |
| Portal tributario | https://tributos.diputaciondezamora.es/portal/entidades.do?ent_id=2 | Diputación de Zamora |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=49&municipio=010 | 4 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=49&municipio=010 | Sin documentos activos (sep 2026) |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=49010 | Mapa interactivo regional |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **DSU** (Delimitación de Suelo Urbano), aprobación definitiva **19/05/1999** (`cDocId=279741`).
- Modificaciones puntuales publicadas en BOCyL (2004–2014) sobre ampliación de suelo urbano.

### Listado PlanPublica (PLAU) — cómo se presentan

Página HTML con tabla ordenable. Cada fila incluye tipo (PU/OT), subtipo (DSU/PYIC), fechas y enlace `openDocumento.do?cDocId={id}`.

**Documentos identificados (sep 2026):**

| Subtipo | Fecha pub. | Título |
|---------|------------|--------|
| DSU | 07/03/2000 | DSU (delimitación suelo urbano) |
| DSU | 23/02/2005 | Modificación puntual: ampliación suelo urbano C.º Villaralbo |
| DSU | 01/06/2005 | Modificación puntual: C/ Santa Marina, parcela 118 |
| DSU | 13/02/2014 | Modificación puntual parcela nº 9 |
| PYIC | 23/08/2023 | Proyecto regional OTPYIC_18 — ampliación instalaciones cárnicas |

Códigos internos PlanPublica: **provincia=49** (Zamora), **municipio=010** (Arcenillas).

## 3. Building licenses — tablón, sede, etc.

### Tablón de anuncios (`/board`)

Tabla HTML espublico. Anuncio visible (ago 2026): Plan de medidas antifraude — **sin licencias de obra**.

### Catálogo de trámites (`/dossier/.0`)

Trámites urbanísticos estándar espublico (licencia, comunicación previa, certificado urbanístico, actuación urbanística, etc.). El adapter devuelve páginas informativas cuando no hay concesiones publicadas.

## Geometría / visor

- **geometry_status:** partial
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — polígono DSU municipal (`n_mun='Arcenillas'`, 1 feature MultiPolygon WGS84)
  - SiuCyL visor: https://idecyl.jcyl.es/siur/index.html?id=49010
  - Sin capas de sectores/PE en WFS (`plau_cyl_sectores`: 0 features)
- **Estrategia:** ingestar geometría del ámbito DSU vía WFS; enriquecer filas PLAU con subtipo DSU; sector codes en títulos → query puntual (sin sectores publicados)
- **Limitaciones:** modificaciones puntuales y PYIC sin polígono individual en WFS; licencias sin coords en tablón; expedientes solo PDF en PLAU

## 4. Limitaciones técnicas

- Sede `/info` y `/dossier` redirigen en bucle sin cookie jar → usar `/info.0` y `/dossier/.0`
- Primera carga del dossier ~50 s
- Sin dataset de licencias georreferenciadas
- Portal corporativo no lista expedientes (solo enlaza a PLAU)
