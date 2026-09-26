# Olivares de Duero — investigación portal ayuntamiento

**Municipio:** Olivares de Duero (provincia Valladolid, Castilla y León)  
**Fecha:** 2026-08-31  
**BOCYL (referencia):** 2 avisos  
**INE:** 47103 | **PlanPublica:** provincia=47, municipio=107

## Resumen

Olivares de Duero publica trámites y anuncios en la **sede electrónica espublico gestiona**
(`olivaresdeduero.sedelectronica.es`). El planeamiento urbanístico vigente (NUM con sectores SUD/SUNC)
está en **PlanPublica / IDECyL** (Junta de Castilla y León). La web corporativa alojada en la
plantilla de la Diputación de Valladolid (`olivaresdeduero.ayuntamientosdevalladolid.es`) no respondió
en el entorno del agente (timeout). No hay listado público de licencias de obra concedidas con
coordenadas.

## 1. URLs oficiales

| Portal | URL | Notas |
|--------|-----|-------|
| Sede electrónica | https://olivaresdeduero.sedelectronica.es | Redirige desde `/` |
| Tablón de anuncios | https://olivaresdeduero.sedelectronica.es/board | HTML tabla Wicket; ~2 filas visibles (ago 2026) |
| Catálogo de trámites | https://olivaresdeduero.sedelectronica.es/dossier | Timeout / respuesta vacía en el agente |
| Transparencia | https://olivaresdeduero.sedelectronica.es/transparency | Sección «Urbanismo, obras públicas y medio ambiente» (2 PDFs) |
| Web Diputación Valladolid | https://olivaresdeduero.ayuntamientosdevalladolid.es | Timeout; dominio alternativo `olivaresdeduero.gob.es` |
| PlanPublica — archivo aprobado (PLAU) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=47&municipio=107 | Sin documentos (ago 2026) |
| PlanPublica — información pública (PLAI) | https://servicios.jcyl.es/PlanPublica/searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=47&municipio=107 | Sin documentos activos |
| SiuCyL visor (SiUR) | https://idecyl.jcyl.es/siur/index.html?id=47103 | Mapa interactivo regional |

**Contacto:** Plaza Mayor 1, 47359 Olivares de Duero · Tel. 983 680 201 · ayuntamiento@olivaresdeduero.gob.es

## 2. Urban planning — expedientes / planeamiento

### Instrumento vigente (WFS IDECyL)

- **NUM** (Normas Urbanísticas Municipales) con sectores de desarrollo:
  - `SUD-01`, `SUD-02`, `SUD-03` (suelo urbanizable no consolidado)
  - `SUNC 01` (Las Eras y Entorno), `SUNC-02` (La Alameda)
- Códigos internos WFS: `47103SUD-01` … `47103SUNC-02`

### PlanPublica (PLAU/PLAI)

Tabla HTML estándar JCyL. **Sin filas** para municipio 107 (provincia 47) en agosto 2026.
El adapter consulta PLAU/PLAI por si se publican expedientes futuros.

### Tablón de anuncios

Columnas: `Documento | Expediente | Procedimiento | Categoría | Descripción | Fecha`.

Anuncios recientes (jul–ago 2026): número de electores, bando limpieza de solares.
**Sin expedientes de planeamiento** en la ventana visible.

PDFs: `https://olivaresdeduero.sedelectronica.es/preview-document/{uuid}`.

### Transparencia — urbanismo

| Título | URL |
|--------|-----|
| DECRETO 2020-0080 [Resolución adjudicación obra Pavimentación varias calles Planes 2018-2019] | preview-document/41ca88e2-0748-4ad0-bbd7-6a2efac0ba43 |
| PROPUESTA PRESUPUESTOS MUNICIPALES 2018 | preview-document/94ded37c-0354-4b85-becb-58117536179b |

## 3. Building licenses

- **Tablón:** sin licencias de obra en ventana visible.
- **Catálogo dossier:** no accesible (timeout); no se pudieron extraer UUIDs de trámites.
- **Estrategia adapter:** páginas informativas (tablón, dossier, transparencia urbanismo) como
  filas `licencias.jsonl` tipo trámite; sin concesiones georreferenciadas.

## 4. CMS / tecnología

| Componente | Stack |
|------------|-------|
| Sede electrónica | **espublico gestiona** (Apache Wicket) |
| Web corporativa | Plantilla **Diputación Valladolid** (inaccesible en pruebas) |
| Planeamiento regional | **PlanPublica** JCyL + **GeoServer** IDECyL |

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - WFS `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
  - Capas: `urbanismo:plau_cyl_sectores` (5 polígonos), `urbanismo:plau_cyl_instrumentos_ambito` (1 polígono NUM municipal)
  - Filtro: `CQL_FILTER=n_mun='Olivares de Duero'`
  - Visor SiUR: `https://idecyl.jcyl.es/siur/index.html?id=47103`
- **Estrategia:** ingestar features WFS como proyectos con `geom_geojson`; cruzar códigos SUD/SUNC
  en títulos de tablón/transparencia; centroide municipal `[41.637, -4.358]` + jitter para el resto.
- **Limitaciones:** licencias y tablón sin GIS; dossier inaccesible; PLAU sin documentos PDF.

### WFS — ejemplo de consulta

```
GET https://idecyl.jcyl.es/geoserver/urbanismo/wfs
  ?service=WFS&version=2.0.0&request=GetFeature
  &typeName=urbanismo:plau_cyl_sectores
  &outputFormat=application/json&srsName=EPSG:4326
  &CQL_FILTER=n_mun='Olivares de Duero'
```

## Limitaciones

- Web Diputación Valladolid no responde (timeout >45 s).
- Catálogo `/dossier` devuelve respuesta vacía o excede timeout.
- Tablón con ventana muy corta y sin urbanismo reciente.
- Sin licencias concedidas publicadas con coordenadas.

## Estrategia adapter

1. **WFS IDECyL** → sectores NUM con geometría (fuente principal de proyectos).
2. **PlanPublica PLAU/PLAI** → parseo tabla si aparecen documentos.
3. **Tablón sede** (`/board`) → filtrar keywords urbanismo/licencia.
4. **Transparencia** → PDFs sección urbanismo (obras, adjudicaciones).
5. **Trámites informativos** → tablón, dossier, transparencia para `licencias.jsonl`.
6. **IDs:** `olivares-de-duero-{lic|proy}-{sha256[:14]}`.
