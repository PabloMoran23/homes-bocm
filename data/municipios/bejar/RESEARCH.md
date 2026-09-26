# Béjar — investigación portal ayuntamiento

**Municipio:** Béjar (Salamanca, Castilla y León)  
**Código INE:** 37046  
**Fecha:** 2026-08-25  
**BOCYL (referencia):** 2 avisos

## Resumen

Béjar publica licencias y anuncios en la **sede electrónica espublico gestiona**
(`bejar.sedelectronica.es`). El planeamiento aprobado está indexado en el archivo PLAI de la
Junta de Castilla y León. La geometría de sectores, planes parciales e instrumentos de ámbito
está disponible en el WFS de IDECyL.

La web corporativa `www.bejar.es` devuelve error de base de datos (HTTP 500) desde entornos
automatizados; la ingesta usa sede + fuentes autonómicas.

## Fuentes identificadas

| Fuente | URL | Formato | Contenido |
|--------|-----|---------|-----------|
| Tablón de anuncios | `https://bejar.sedelectronica.es/board` | HTML tabla Wicket (`class_name`) | Edictos, licencias, bandos |
| Catálogo trámites | `https://bejar.sedelectronica.es/dossier` | HTML Wicket | Trámites urbanismo/licencias |
| PLAI info pública | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=046` | HTML | Documentación en exposición pública |
| PLAI archivo | `https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=046` | HTML | Planeamiento aprobado (PGOU revisión 2014) |
| IDECyL WFS | `https://idecyl.jcyl.es/geoserver/urbanismo/wfs` | GeoJSON WFS | Sectores, planes parciales, instrumentos |
| Web municipal | `https://www.bejar.es` | — | **Inaccesible** (HTTP 500 — error BD) |

## Tablón de anuncios (`/board`)

Tabla HTML con celdas `class_name`, `class_folderCode`, `class_folderName`,
`class_boardCategory`, `class_description`, `class_dateFrom`. Enlaces `preview-document/{uuid}`.

Ejemplo vigente (ago 2026):

- Expte. 1186/2026 — Licencia de Uso Provisional LUP 001/26 (Polígono 2, Parcelas 327 y 328)

## Licencias

No hay visor georreferenciado ni dataset abierto de concesiones con coordenadas.

- Anuncios de licencia en tablón cuando se publican edictos (p. ej. LUP uso provisional).
- Catálogo de trámites sede como referencia informativa si accesible.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 27 sectores (SU-NC 01, …)
  - IDECyL WFS `urbanismo:plau_cyl_planes_parciales` — 1 plan parcial
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 instrumento (PGOU revisión 2014)
  - Filtro: `CQL_FILTER=n_mun = 'Béjar'`, `srsName=EPSG:4326`
- **Estrategia:** ingestar polígonos WFS como proyectos; enriquecer tablón por código de sector en título
- **Limitaciones:** licencias del tablón sin geometría enlazable; no hay visor ArcGIS municipal propio;
  sede requiere `insecure_ssl` (certificado Firmaprofesional); `www.bejar.es` caído

## Limitaciones

- `www.bejar.es`: HTTP 500 (error establishing database connection) — no se usa como fuente.
- Certificado SSL sede: emisor no en CA del sistema; adapter usa `insecure_ssl: true`.
- Tablón muestra ~10 anuncios recientes; histórico requiere búsqueda POST Wicket (no implementado).

## Estrategia adapter

1. Bootstrap sesión en `/board` (cookie `JSESSIONID`).
2. Scrape tablón `/board` (formato `class_name`).
3. Catálogo trámites `/dossier` filtrado por keywords urbanismo/licencia.
4. URLs semilla PLAI Junta CYL (provincia 37, municipio 046).
5. WFS IDECyL: sectores + planes parciales + instrumentos con `geom_geojson`.
6. Enriquecimiento geometría tablón por código sector en título/descripción.
