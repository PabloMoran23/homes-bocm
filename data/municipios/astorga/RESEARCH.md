# Astorga — investigación portal ayuntamiento

**Fecha:** 2026-09-08  
**Slug:** `astorga`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Astorga publica urbanismo en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://aytoastorga.es | OpenCms (`es.samdipuleon.templates`, Diputación León) | Tablón de anuncios, noticias PGOU, trámites |
| Sede electrónica | https://ayuntamientoastorga.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, info pública, catálogo trámites |
| Junta CYL | https://servicios.jcyl.es/PlanPublica/ | Java portal | Archivo planeamiento aprobado e info pública (provincia 24, municipio 008) |

**Nota:** `www.astorga.es` no responde desde el entorno del agente; la web activa es `aytoastorga.es`.

## Fuentes de proyectos / expedientes

### 1. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Capas:** `plau_cyl_sectores` (12), `plau_cyl_instrumentos_ambito` (1), `plau_cyl_planes_parciales` (0)
- **Filtro:** `n_mun = 'Astorga'` o `c_mun = '24008'`
- GeoJSON WGS84 con polígonos de sectores S.U.N.C. (R1–R5, etc.)

### 2. PlanPublica JCyL — documentos aprobados

- **PLAU:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=24&municipio=008`
- **PLAI:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=24&municipio=008`
- Tabla HTML con `doOpen(cDocId)` → `openDocumento.do?cDocId=...`
- Documentos detectados: normas urbanísticas, convenios urbanísticos (CUP), etc.

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://ayuntamientoastorga.sedelectronica.es/board
- **Info pública:** https://ayuntamientoastorga.sedelectronica.es/info.1
- **Formato:** tabla HTML espublico (Documento, Expediente, Procedimiento, Categoría, Descripción, Fecha)
- Ventana corta (~10 anuncios); incluye licencias ambientales, información pública AAI

### 4. Web OpenCms — tablón de anuncios

- **URL:** https://aytoastorga.es/ayuntamiento/tablon-de-anuncios/
- Anuncios en `/_contenidos/tablon-de-anuncios/{año}/...html`
- Contenido urbanístico: licencias ambientales, obras, ruina (calle Santa Lucía), PGOU provisional (noticia 2021)

### 5. SiuCyL / visor regional

- **URL:** https://idecyl.jcyl.es/siur/index.html?id=24008
- Visor de planeamiento regional; geometría accesible vía WFS

## Fuentes de licencias

1. **Tablón web OpenCms** — información pública de licencias ambientales y obras
2. **Tablón sede espublico** — anuncios de licencias ambientales y trámites AAI
3. **Páginas informativas** — solicitud general de trámites, tablón sede
4. **Catálogo sede** (`/dossier`) — formularios de solicitud (puede timeout en CI)

No hay listado histórico público de concesiones con coordenadas.

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_sectores` — polígonos por sector (`n_num_sect` p. ej. SU-NC R1)
  - IDECyL WFS `plau_cyl_instrumentos_ambito` — ámbito PGOU
  - SiuCyL visor: `https://idecyl.jcyl.es/siur/index.html?id=24008`
- **Estrategia:** descarga WFS por municipio (`n_mun='Astorga'`); enriquecimiento por código de sector en título; expedientes del tablón sin GIS directo usan centroide municipal + jitter
- **Limitaciones:** licencias y expedientes puntuales sin polígono enlazable; sin visor urbanístico municipal propio; `www.astorga.es` inaccesible

## Limitaciones

- Tablón sede: ventana corta (~10 filas), sin API
- `/dossier` puede timeout desde CI
- Licencias sin geolocalización en fuentes públicas
- Dominio `www.astorga.es` no responde (usar `aytoastorga.es`)
- Sede en subdominio `ayuntamientoastorga.sedelectronica.es` (no `astorga.sedelectronica.es`)

## Estrategia adapter

1. WFS IDECyL → proyectos con `geom_geojson`
2. PlanPublica PLAU/PLAI → documentos de planeamiento
3. Tablón espublico + tablón web OpenCms → proyectos/licencias filtrados
4. Semillas PGOU + JCyl → proyectos de planeamiento
5. Páginas trámite → licencias informativas
