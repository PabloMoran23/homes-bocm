# Murias de Paredes — investigación portal ayuntamiento

**Fecha:** 2026-09-25  
**Slug:** `murias-de-paredes`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Murias de Paredes publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://www.aytomuriasdeparedes.es | OpenCms (`es.samdipuleon.templates`) | Normativa urbanística, trámites/licencias (HTML), enlace tablón → sede |
| Sede electrónica | https://aytomuriasdeparedes.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites (`/dossier`), transparencia |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Planeamiento en información pública y archivo aprobado (provincia 24, municipio 102) |

**Nota:** dominios genéricos `muriasdeparedes.sedelectronica.es` / `murias-de-paredes.sedelectronica.es` devuelven «Sede Electrónica Indeterminada»; el host correcto es `aytomuriasdeparedes.sedelectronica.es`.

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumentos y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores`
- **Filtro:** `n_mun = 'Murias de Paredes'`, código INE municipio `24102`
- En prueba (2026-09): al menos 1 instrumento de ámbito con polígono; sectores S.U.N.C. sin geometría publicada en WFS para este municipio

### 2. Sede electrónica — tablón de anuncios

- **URL:** https://aytomuriasdeparedes.sedelectronica.es/board/
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Ventana corta (~10 anuncios); en la muestra actual predominan anuncios administrativos (sin categoría Urbanismo)

### 3. Web OpenCms — normativa y Junta CYL

- **Normativa:** https://www.aytomuriasdeparedes.es/ayuntamiento/normativa-municipal/urbanismo/
- Enlaces PlanPublica CYL:
  - Info pública: `searchVPubDocMuniPlai.do?provincia=24&municipio=102`
  - Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=24&municipio=102`

### 4. Catálogo trámites sede (`/dossier`)

- Requiere sesión (cookie) tras visitar tablón o home sede
- Trámites urbanismo: licencias, modificaciones de planeamiento, actuaciones urbanísticas, etc.

## Fuentes de licencias

1. **Páginas informativas web** — licencia urbanística, primera ocupación, comunicación ambiental (OpenCms)
2. **Tablón sede** — anuncios puntuales cuando mencionan licencias
3. **Catálogo sede** — formularios de solicitud (sin histórico de concesiones)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` (y capas parciales/planes si existen)
  - Sin visor urbanístico municipal ni ArcGIS propio
- **Estrategia:** descarga WFS por `n_mun`; enriquecimiento por código de sector en títulos del tablón; resto con centroide municipal + jitter
- **Limitaciones:** licencias sin geolocalización; tablón sin enlace GIS; `/dossier` puede ser lento sin sesión sede

## Limitaciones

- Tablón sede: ventana corta, sin API
- Dominios sede alternativos no resuelven municipio
- Licencias sin geolocalización en fuentes públicas
- Sin visor urbanístico municipal propio

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` cuando hay polígono
2. Tablón espublico → proyectos/licencias filtrados por palabras clave
3. Páginas trámite OpenCms → licencias informativas
4. Semillas normativa + JCyl → proyectos de planeamiento
5. Catálogo `/dossier` (sesión cookie) → trámites urbanismo
