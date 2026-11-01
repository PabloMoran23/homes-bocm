# San Andrés del Rabanedo — investigación portal ayuntamiento

**Municipio:** San Andrés del Rabanedo (provincia León, Castilla y León)  
**Fecha:** 2026-11-01  
**BOCYL / boletín regional:** sin boletín asociado en cola  
**INE:** 24181 | **PlanPublica:** provincia 24, municipio 181

## Resumen

Municipio del área metropolitana de León. La **web corporativa** (`www.aytosanandres.es`, `sanandresdelrabanedo.es`) no responde de forma usable desde el entorno del agente (HTTP 503 / sin DNS). La **sede electrónica** en `sanandresdelrabanedo.sedelectronica.es` devuelve la página genérica *«Sede Electrónica Indeterminada»* (sin tablón ni catálogo de trámites enlazado).

El planeamiento urbanístico publicado de forma estable está en **PlanPublica / SiuCyL** (Junta de Castilla y León) y la **geometría de sectores** en **IDECyL WFS**.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Web corporativa (intento) | https://www.aytosanandres.es | 503 F5 desde cloud agent |
| Web alternativa | https://www.sanandresdelrabanedo.es | Sin respuesta |
| Sede electrónica | https://sanandresdelrabanedo.sedelectronica.es | Página «Indeterminada»; `/board` sin tablón real |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=181 | 1 documento (NUM) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=181 | Sin filas en nov 2026 |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=24181 | Visor regional por INE |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **27/02/2007**, publicación **26/03/2007** (`cDocId=283313`, código `24181-PU-20070326-283313`).

### Listado PlanPublica (PLAU)

Tabla HTML estándar JCyL. Enlace PDF: `openDocumento.do?cDocId={id}` vía `doGoBoletin()`.

### Sectores urbanísticos (WFS)

IDECyL expone **49 sectores** (`urbanismo:plau_cyl_sectores`) con polígonos en EPSG:4326 (p. ej. SUNC 04, MultiPolygon). Un polígono de **ámbito del instrumento** en `plau_cyl_instrumentos_ambito`.

## 3. Licencias de obra

- **Tablón sede:** no operativo (sede indeterminada).
- **No** hay dataset público de concesiones georreferenciadas localizado.
- **Estrategia adapter:** intentar tablón/catálogo sede (falla silenciosa) + filas informativas si aparecen; `min_rows` licencias = 0 en validación.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — polígono NUM municipal
  - WFS `urbanismo:plau_cyl_sectores` — 49 sectores (SUNC, etc.)
  - SiUR: https://idecyl.jcyl.es/siur/index.html?id=24181
- **Estrategia:** descarga WFS con `CQL_FILTER=n_mun='San Andrés del Rabanedo'`; enriquecimiento por código de sector en títulos PLAU/PLAI y filas WFS.
- **Limitaciones:** sin visor municipal propio accesible; sede sin tablón; licencias sin geometría; web corporativa inaccesible desde automatización.

### Endpoint WFS (ejemplo)

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeNames=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='San Andrés del Rabanedo'
```

## 4. Limitaciones

- Sede espublico mal configurada o migración pendiente.
- Web ayuntamiento bloqueada (503) en entorno cloud — revisar manualmente en red local.
- Licencias: sin fuente pública fiable salvo futuro arreglo del tablón.
