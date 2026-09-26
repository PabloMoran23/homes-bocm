# Asturianos — investigación portal ayuntamiento

**Fecha:** 2026-09-08  
**Slug:** `asturianos`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Asturianos (Zamora, Sanabria) publica urbanismo en **cuatro portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://aytoasturianos.es | WordPress (consorcio Sanabria) | Tablón de anuncios, posts (instalación autoconsumo 2023) |
| Sede electrónica | https://asturianos.sedelectronica.es | espublico gestiona (Wicket) | Tablón (~2 anuncios), trámites |
| Junta CYL / PLAU | https://servicios.jcyl.es/PlanPublica/ | Java | SPG (Sin Planeamiento General), cDocId=279745 |
| IDECyL SIUR/WFS | https://idecyl.jcyl.es/siur/index.html?id=49017 | GeoServer WFS | Polígono municipal SPG |

**Nota:** `www.asturianos.es` no responde; el dominio activo es `aytoasturianos.es` (redirige desde `asturianos.es`).

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — instrumento de planeamiento

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas consultadas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0), `plau_cyl_sectores` (0)
- **Filtro:** `n_mun = 'Asturianos'`, `c_mun = 49017`
- **Resultado:** 1 registro SPG «SIN PLANEAMIENTO GENERAL» con `MultiPolygon` WGS84 (~42.6 km²)

### 2. Junta CYL — planeamiento documental

- Archivo aprobado: `searchVPubDocMuniPlau.do?provincia=49&municipio=017`
- Información pública: `searchVPubDocMuniPlai.do?provincia=49&municipio=017`
- Documento SPG: `openDocuIndice.do?cDocId=279745`
- **Código PLAU:** municipio=017 (no confundir con 275 = Zamora capital)

### 3. Web WordPress — tablón de anuncios

- **URL:** https://aytoasturianos.es/index.php/tablon-de-anuncios/
- **API REST:** `https://aytoasturianos.es/index.php/wp-json/wp/v2/posts`
- Anuncio urbanístico relevante: «Instalación de generación eléctrica renovable para autoconsumo» (2023-08-23)

### 4. Sede electrónica — tablón

- **URL:** https://asturianos.sedelectronica.es/board
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Anuncios actuales: IAE, uso agua estival (sin interés urbanístico directo)

## Fuentes de licencias

1. **Tablón sede** — anuncios puntuales si mencionan licencias/obra
2. **Web WordPress** — post autoconsumo renovable (autorización/instalación)
3. **Sede trámites** (`/dossier`) — catálogo de trámites (sin histórico de concesiones)
4. **Páginas informativas** — tablón y dossier como referencia de trámite

No hay listado histórico público de concesiones de licencia con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_instrumentos_ambito` — 1 polígono municipal (SPG)
  - IDECyL SIUR visor: `https://idecyl.jcyl.es/siur/index.html?id=49017`
- **Estrategia:** descarga WFS por municipio (`CQL_FILTER n_mun='Asturianos'`); enriquecimiento por coincidencia de título en tablón/WP; resto centroide municipal + jitter
- **Limitaciones:** sin PGOU ni sectores/PP desglosados; polígono WFS es delimitación municipal completa (no por expediente); licencias y anuncios del tablón sin GIS enlazable; web consorcio compartida con otros municipios de Sanabria

## Limitaciones

- Municipio sin Planeamiento General (SPG) — no hay sectores ni planes parciales en WFS
- Tablón sede: ventana corta (~2 anuncios), sin API
- Licencias sin geolocalización en fuentes públicas
- Web `aytoasturianos.es` es portal consorcio (varios municipios Sanabria)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson` (polígono SPG)
2. Semillas Junta CYL (PLAI/PLAU + openDocuIndice) → proyectos de planeamiento
3. WordPress REST → proyectos/licencias filtrados por keywords
4. Tablón espublico → proyectos/licencias filtrados por keywords
5. Páginas informativas sede → licencias (trámites, sin concesiones históricas)
