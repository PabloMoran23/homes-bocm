# Pesquera de Duero — investigación portal ayuntamiento

**Municipio:** Pesquera de Duero (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-08-31  
**BOCYL (referencia):** 2 avisos  
**INE:** 47116 | **PLAI:** provincia 47, municipio 116

## Resumen

Pesquera de Duero **no dispone de web corporativa activa** (dominios `pesqueradeduero.es` no resuelven).
La presencia digital municipal pasa por la **sede electrónica espublico gestiona**
(`pesqueradeduero.sedelectronica.es`, certificado SSL con cadena inválida — requiere `insecure_ssl`).
El planeamiento urbanístico vigente (NUM + modificaciones + PAU/estudios de detalle) está en
**PlanPublica / SiuCyL** (Junta de Castilla y León). La geometría de sectores está en **IDECyL WFS**.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://pesqueradeduero.sedelectronica.es/info | espublico gestiona (Wicket) |
| Tablón de anuncios | https://pesqueradeduero.sedelectronica.es/board | 1+ anuncio urbanístico (ago 2026) |
| Catálogo de trámites | https://pesqueradeduero.sedelectronica.es/dossier | Carga lenta (>60 s); sin UUIDs estables en HTML inicial |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=116 | ~15 documentos |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=116 | Trámites en curso |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=47116 | Mapa interactivo regional |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **29/09/2004** (`cDocId=282055`).
- Sectores identificados en WFS: S1–S4 (S.Urble), SUNC 1–2.

### Listado PlanPublica (PLAU/PLAI) — cómo se presentan

Página HTML con tabla ordenable. Cada fila incluye:

| Campo | Origen HTML |
|-------|-------------|
| Libro / subtipo | PU NUM, PU ED, GU PAU, PU PP… |
| Fecha publicación / aprobación | `DD/MM/YYYY` |
| Título | Texto del instrumento |
| Enlace PDF | `openDocumento.do?cDocId={id}` vía `doOpen()` / `doGoBoletin()` |

**Documentos identificados (ago 2026, extracto):**

| Tipo | Título |
|------|--------|
| NUM | NORMAS URBANÍSTICAS MUNICIPALES (2004) |
| NUM | Múltiples modificaciones (2005–2024) |
| ED | Estudio de detalle Sector 1 y Sector 2 |
| PAU | Proyecto de actuación y reparcelación Sector 1 (2019) |
| PP | Plan parcial Sector Nº 1 (2016) |

### Tablón sede — licencias

El tablón publica anuncios con `preview-document/{uuid}`. Ejemplo (ago 2026):

- **BOCYL-D-03082026-148-46** — Trámite información pública, autorización uso excepcional suelo rústico (Bodegas Emilio Moro), categoría Licencias Urbanísticas.

No hay dataset público de concesiones de licencias georreferenciadas.

## 3. Licencias de obra

- **Publicación:** tablón sede (`/board`) — avisos puntuales, no listado histórico completo.
- **Trámites:** catálogo sede (`/dossier`) — páginas informativas de solicitud (no concesiones).
- **Estrategia adapter:** extraer licencias del tablón + filas informativas si el catálogo responde.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — polígono NUM municipal
  - WFS `urbanismo:plau_cyl_sectores` — 6 sectores (S1–S4 S.Urble, SUNC 1–2)
  - WFS `urbanismo:plau_cyl_planes_parciales` — 1 plan parcial
  - SiUR visor: https://idecyl.jcyl.es/siur/index.html?id=47116
- **Estrategia:** descarga WFS por `n_mun='Pesquera de Duero'`; enriquecimiento por código de sector (`S1`, `SUNC 1`, «Sector Nº 1») en títulos PLAU/PLAI y tablón.
- **Limitaciones:** licencias del tablón sin geometría; expedientes NUM sin polígono sectorial concreto salvo match por sector; sin visor municipal propio.

### Endpoints WFS

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeNames=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Pesquera de Duero'
```

## 4. Limitaciones

- Sin web corporativa; solo sede espublico.
- SSL sede con certificado no verificable (`insecure_ssl: true`).
- Catálogo `/dossier` muy lento; no se usan UUIDs hardcodeados.
- Licencias: solo avisos del tablón, no registro histórico completo.
- Geometría parcial: polígonos de sectores/instrumentos WFS; licencias sin coords.
