# El Cubo de Don Sancho — investigación portal ayuntamiento

**Municipio:** El Cubo de Don Sancho (provincia Salamanca, Castilla y León)  
**Fecha:** 2026-09-14  
**BOCYL (referencia):** 1 aviso  
**INE:** 37113 | **PlanPublica mun:** 113 (provincia 37)

## Resumen

El Cubo de Don Sancho **no dispone de web corporativa propia**. El subdominio
`elcubodedonsancho.sedelectronica.es` (espublico gestiona) responde con la página
**«Sede Electrónica Indeterminada»** en todas las rutas probadas (`/`, `/board/`,
`/info.0`, `/dossier/.0`), por lo que no hay tablón de anuncios ni catálogo de trámites
accesible. El planeamiento urbanístico se consulta en **PlanPublica / SiuCyL** (Junta de
Castilla y León). El municipio tiene **sin planeamiento general (SPG)** como instrumento
vigente; no hay planes parciales ni sectores publicados en IDECyL.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://elcubodedonsancho.sedelectronica.es/ | **Indeterminada** — sin tablón ni trámites |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=113 | Sin filas en tabla (ago 2026) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=113 | Sin documentos activos |
| Instrumento SPG (índice) | https://servicios.jcyl.es/PlanPublica/openDocuIndice.do?cDocId=278415 | «Sin Planeamiento General» |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=37113 | Mapa interactivo regional |
| IDECyL WFS urbanismo | https://idecyl.jcyl.es/geoserver/urbanismo/wfs | Capas `plau_cyl_*` filtradas por `n_mun` |

**Web corporativa:** no resuelve (`elcubodedonsancho.es`, `aytoelcubodedonsancho.es`).

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente (WFS / PlanPublica)

| Campo | Valor |
|-------|-------|
| Código plan | `37113-PU-00000000-278415` |
| Instrumento | SPG — Sin Planeamiento General |
| cDocId | 278415 |
| Superficie | ~91,1 km² (polígono municipal) |

No hay documentos adicionales en el listado PLAU HTML ni expedientes de información
pública en PLAI. Los avisos BOCYL del municipio no aportan listado estructurado en portal.

### Cómo se listan los datos

| Fuente | Formato | Uso en adapter |
|--------|---------|----------------|
| IDECyL WFS | GeoJSON (`application/json`, EPSG:4326) | 1 feature `plau_cyl_instrumentos_ambito` con polígono municipal |
| PlanPublica PLAU/PLAI | HTML tabla (vacía) | URLs semilla de consulta |
| openDocuIndice | HTML índice documental | Enlace al instrumento SPG |
| Sede tablón | — | No operativo |

## 3. Licencias de obra

No hay listado público de concesiones de licencias georreferenciadas. La sede
electrónica no expone catálogo de trámites. El adapter incluye **páginas informativas**
(PLAU/PLAI, SiUR, sede) como referencia de trámites urbanísticos, sin concesiones
publicadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS IDECyL `urbanismo:plau_cyl_instrumentos_ambito` — filtro `n_mun='El Cubo de Don Sancho'`
  - SiUR: https://idecyl.jcyl.es/siur/index.html?id=37113
- **Estrategia:** query WFS GetFeature con `srsName=EPSG:4326`; polígono del ámbito SPG
  (límite municipal). Sin capas de sectores (`plau_cyl_sectores`: 0) ni planes parciales.
- **Limitaciones:** solo contorno municipal / instrumento SPG; sin geometría por expediente
  de licencia; sede indeterminada impide tablón con PDFs georreferenciables.

## 4. Limitaciones

- Sede espublico **indeterminada** (bloquea tablón y catálogo local).
- PLAU/PLAI sin filas en tabla HTML (documento SPG accesible solo vía índice WFS/`cDocId`).
- Sin visor urbanístico municipal; dependencia total de IDECyL/SiuCyL.
- Licencias: solo trámites informativos, sin concesiones publicadas.

## 5. Referencias de implementación

- Adapter CYL sede+WFS: `municipio/adapters/valverdon.py`
- Helpers geometría: `municipio/geometry.py`
