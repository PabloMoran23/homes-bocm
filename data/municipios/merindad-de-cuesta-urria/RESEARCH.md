# Merindad de Cuesta Urria — investigación portal ayuntamiento

**Municipio:** Merindad de Cuesta Urria (provincia Burgos, Castilla y León)  
**Fecha:** 2026-08-30  
**BOCYL (referencia):** 2 avisos  
**INE:** 09213 | **PlanPublica:** provincia 09, municipio 213

## Resumen

Merindad de Cuesta Urria **no tiene web corporativa accesible** desde el entorno del agente
(`merindaddecuestaurrea.es`, diputación Burgos, gestion3: sin respuesta). La sede electrónica
en `merindaddecuestaurrea.sedelectronica.es` responde **«Sede Electrónica Indeterminada»** (sin
tablón ni catálogo de trámites). El planeamiento urbanístico vigente (NUM + sectores de desarrollo)
está en **PlanPublica / SiuCyL** con geometría en **IDECyL WFS**.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://merindaddecuestaurrea.sedelectronica.es/ | **Indeterminada** — no sirve tablón ni trámites |
| Sede (variante) | https://merindaddecuesta-urria.sedelectronica.es/ | Igual: indeterminada |
| Web municipal | https://www.merindaddecuestaurrea.es/ | Sin respuesta (timeout / DNS) |
| Diputación Burgos | https://merindaddecuestaurrea.diputaciondeburgos.es/ | Sin respuesta |
| PlanPublica — archivo (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=9&municipio=213 | 2 documentos NUM |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=9&municipio=213 | Sin documentos activos (ago 2026) |
| SiUR visor | https://idecyl.jcyl.es/siur/index.html?id=09213 | Visor regional JCyL |
| JCyL catálogo planeamiento | http://www.jcyl.es/plau/lplanes.plau?municipio=09213 | Listado histórico |

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente

- **NUM** (Normas Urbanísticas Municipales), aprobación definitiva **17/04/2008**, BOCYL **28/05/2008**
  (`cDocId=284321`, código `09213-PU-20080529-284321`).
- **Modificación NUM** sobre ordenanza del edificio «Castillo de las Cuevas», aprobación **10/04/2014**
  (`cDocId=290682`).

### Listado PlanPublica (PLAU)

Tabla HTML ordenable. Campos: tipo instrumento (PU/NUM), fechas publicación/aprobación, título,
enlaces `openDocuIndice.do?cDocId={id}` y PDFs en `openDocumento.do?cDocId={id}`.

### WFS IDECyL — sectores identificados (ago 2026)

12 sectores en `plau_cyl_sectores` con códigos **NOF**, **EXT**, **MIJ** (ej. NOF 01, EXT 02, MIJ 01).
1 polígono municipal NUM en `plau_cyl_instrumentos_ambito`. 0 planes parciales en `plau_cyl_planes_parciales`.

## 3. Building licenses — tablón, sede, etc.

- **Tablón sede:** no accesible (sede indeterminada).
- **Catálogo trámites sede:** no accesible.
- **No hay** dataset público de licencias concedidas con coordenadas.
- El adapter registra páginas **informativas** de trámites de licencia (referencia sede indeterminada)
  y enlaces PlanPublica/SiUR, siguiendo el patrón Pozuelo/Valverdón.

## 4. GIS / geometría

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| WFS IDECyL | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON | 1 NUM + 12 sectores |
| SiUR | `https://idecyl.jcyl.es/siur/index.html?id=09213` | Visor JS | Sin API scrapeable |

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/ows
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json
  &srsName=EPSG:4326
  &CQL_FILTER=n_mun='Merindad de Cuesta-Urria'
```

Propiedades útiles: `n_num_sect`, `n_sector`, `c_id_sect`, `f_bocyl`, `url_doc_info`.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:** WFS `plau_cyl_instrumentos_ambito` (polígono NUM municipal); WFS `plau_cyl_sectores`
  (12 sectores NOF/EXT/MIJ).
- **Estrategia:** ingestar features WFS con `geom_geojson`; cruzar códigos de sector en títulos PLAU;
  fallback centroide `[42.85795, -3.40275]` + jitter.
- **Limitaciones:** sede indeterminada (sin tablón/licencias); sin visor municipal propio; SiUR sin WFS directo.

## Limitaciones

- Sede espublico no operativa para este municipio.
- Sin web corporativa verificable.
- Licencias: solo trámites informativos, no concesiones publicadas.
- PLAI sin documentos de información pública activos.

## Estrategia adapter

1. **PlanPublica PLAU** — parsear tabla de documentos NUM.
2. **WFS IDECyL** — geometría de instrumentos y sectores (`plau_cyl_*`).
3. **Sede** — intento tablón/catálogo (falla silenciosamente si indeterminada).
4. **Trámites informativos** — licencias vía páginas de referencia (sede + PlanPublica).
5. **IDs:** `merindad-de-cuesta-urria-{lic|proy}-{sha256[:14]}`.
