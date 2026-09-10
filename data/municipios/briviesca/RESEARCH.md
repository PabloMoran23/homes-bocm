# Briviesca — investigación portal ayuntamiento

**Fecha:** 2026-09-10  
**Slug:** `briviesca`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Briviesca publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://briviesca.es | Drupal 10 (Toools) | PDFs de planeamiento vigente, PGOU 2023, Plan Especial CH, ITE |
| Sede electrónica | https://briviesca.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios (~10 filas), trámites, transparencia (160 docs urbanismo) |
| Junta CYL / IDECyL | https://servicios.jcyl.es/PlanPublica/ | Java + GeoServer WFS | Archivo PLAU (25 docs), geometría sectores WFS |

**Código INE:** `09056` (PLAU: provincia `09`, municipio `056`).

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores e instrumentos

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_sectores` (42), `plau_cyl_planes_parciales` (0)
- **Filtro:** `c_mun = '09056'`
- Incluye PGOU Revisión y sectores UE con polígonos WGS84

### 2. Web Drupal — PDFs de planeamiento

- **Planeamiento vigente:** https://briviesca.es/planeamientourbanistico (estudios de detalle UE 2-UE-4, 2-UE-8, 4-UE-4, 5-UE-2, 5-UE-3-1)
- **PGOU 2023:** https://briviesca.es/plangeneral2023
- **Plan Especial CH:** https://briviesca.es/planespecial
- **ITE:** https://briviesca.es/inspecciontecnica
- **Formato:** enlaces a PDF en `/sites/briviesca/files/inline-files/`

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://briviesca.sedelectronica.es/board
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Anuncios urbanísticos: licencias urbanísticas, información pública

### 4. Junta CYL — planeamiento documental (PLAU)

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=09&municipio=056`
- Información pública: `searchVPubDocMuniPlai.do?provincia=09&municipio=056`
- PGOU Revisión: `openDocuIndice.do?cDocId=299634`

## Fuentes de licencias

1. **Tablón sede** — anuncios puntuales con procedimiento `Licencias Urbanísticas`
2. **Sede trámites** (`/info.0`) — catálogo: declaración responsable, ITE, licencia de ocupación
3. **Páginas informativas** — tablón y catálogo como referencia de trámite

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — 42 polígonos de sectores
  - IDECyL WFS `plau_cyl_instrumentos_ambito` — 1 polígono PGOU
  - SiuCyL visor: https://idecyl.jcyl.es/siur/ (sin API por expediente municipal)
- **Estrategia:** descarga WFS por `c_mun='09056'`; enriquecimiento por coincidencia de título/sector en tablón/PDFs; resto centroide municipal + jitter
- **Limitaciones:** web municipal sin visor propio; licencias y anuncios del tablón sin GIS enlazable; geometría solo a nivel de instrumento/sector, no por expediente individual

## Limitaciones

- Sin visor urbanístico municipal propio (solo PDFs)
- Tablón sede: ventana corta (~10 anuncios), sin API
- Licencias sin geolocalización en fuentes públicas
- Expedientes individuales del tablón sin geometría enlazable

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. Drupal PDFs → proyectos de planeamiento (memorias, planos)
3. Tablón espublico → proyectos/licencias filtrados por keywords
4. Semillas Junta CYL (PLAI/PLAU) → proyectos de planeamiento
5. Páginas informativas sede → licencias (trámites, sin concesiones históricas)
