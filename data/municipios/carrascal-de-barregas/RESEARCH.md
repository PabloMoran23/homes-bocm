# Carrascal de Barregas — investigación portal ayuntamiento

**Fecha:** 2026-09-11  
**Slug:** `carrascal-de-barregas`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Carrascal de Barregas (Salamanca, CYL) publica planeamiento y trámites urbanísticos en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://carrascaldebarregas.com/ | WordPress + Divi | Noticias, enlaces a sede y transparencia |
| Sede electrónica | https://carrascaldebarregas.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo de trámites, transparencia |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/ | Junta de Castilla y León | Archivo planeamiento aprobado (13 docs) |

## Fuentes de proyectos / expedientes

### 1. Sede electrónica — tablón de anuncios

- **URL:** https://carrascaldebarregas.sedelectronica.es/board
- **Formato:** tabla HTML espublico con `preview-document/{uuid}` por fila
- **Contenido urbanístico activo (sep 2026):**
  - Información pública Plan Parcial Sector 4 «La Alcantarilla» (varios volúmenes: memoria, ordenanzas, índice)
  - Categoría «Urbanismo» / procedimiento «Planeamiento de Desarrollo»
- **SSL:** certificado con cadena incompleta → `insecure_ssl: true`

### 2. PlanPublica — archivo planeamiento

- **Aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=087`
- **Código INE:** 37087 (PlanPublica municipio `087`)
- **Contenido:** 13 documentos — normas urbanísticas (NUM 2008), planes parciales UR-R9, UrR-4, UR-R1, UR-15, URR-8, PERI, modificaciones puntuales
- **Enlaces:** `openDocumento.do?cDocId=...`

### 3. Web corporativa — noticias

- **URL base:** https://carrascaldebarregas.com/
- **Formato:** WordPress Divi con noticias en portada
- **Transparencia sede:** `/transparency` con subsecciones de contratación y urbanismo

### 4. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Filtro:** `c_mun='37087'`
- **Capas:** `plau_cyl_instrumentos_ambito`, `plau_cyl_planes_parciales`, `plau_cyl_sectores`
- **Sectores vigentes (12):** La Charca (DIEZ), Carrascal (DOS), Las Eras (OCHO), El Monte (SEIS), La Alcantarilla (CUATRO), Mirador del Montalvo (TRES), etc.

## Fuentes de licencias

1. **Catálogo sede** (`/dossier`) — trámites informativos de licencia urbanística, declaración responsable, certificados
2. **Tablón sede** — sin concesiones de licencia indexadas en la investigación; expedientes de planeamiento sí
3. No hay listado histórico público de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_*` con `CQL_FILTER=c_mun='37087'`, `srsName=EPSG:4326`
  - 12 polígonos de sectores + instrumentos/planes parciales asociados
- **Estrategia:** ingestión directa desde WFS en adapter; enriquecimiento por código de sector (UR-R*, UrR-*, «Sector 4», «La Alcantarilla») en filas PlanPublica/tablón
- **Limitaciones:**
  - Sin visor SIG integrado en web municipal
  - Licencias sin georreferencia en fuentes públicas
  - Certificado SSL sede requiere `insecure_ssl`

## Limitaciones

- Tablón sin licencias de obra publicadas (solo planeamiento y administración)
- Catálogo de trámites sede carga lento (~60s); puede fallar en entornos con timeout corto
- WP REST no usado; scrape HTML de portada como fuente opcional

## Estrategia adapter

1. **proyectos.jsonl:** IDECyL WFS (con `geom_geojson`) + PlanPublica PLAU + tablón sede + catálogo trámites + noticias web
2. **licencias.jsonl:** catálogo trámites sede (páginas informativas) + tablón cuando publique concesiones
