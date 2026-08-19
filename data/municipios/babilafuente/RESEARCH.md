# Babilafuente — investigación portal ayuntamiento

**Fecha:** 2026-08-15  
**Slug:** `babilafuente`  
**BOCYL regional (referencia):** 3 filas

## Resumen

Babilafuente publica planeamiento y trámites urbanísticos en **tres portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://babilafuente.es/ | WordPress (REST deshabilitado) | Noticias de urbanismo (estudios de detalle, aprobaciones) |
| Sede electrónica | https://babilafuente.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo de trámites |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/ | Junta de Castilla y León | Archivo planeamiento aprobado + información pública |

## Fuentes de proyectos / expedientes

### 1. Web corporativa — noticias

- **URL base:** https://babilafuente.es/
- **Formato:** WordPress con listado de noticias en portada (`<h2><a href="...">`)
- **REST API:** `/wp-json/` devuelve 404 (deshabilitado)
- **Ejemplo reciente:** aprobación inicial estudio de detalle Calle San Andrés (ene 2026)
- **Limitación:** `babilafuente.es` resetea conexión desde algunos entornos cloud (IP extranjera); el adapter hace fallback a otras fuentes

### 2. PlanPublica — archivo planeamiento

- **Aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=38`
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=38`
- **Contenido:** ~13 documentos (NS, PP, DSU, PORN) — normas subsidiarias, planes parciales AP-UR-*, modificaciones puntuales
- **Enlaces:** `openDocumento.do?cDocId=...`

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://babilafuente.sedelectronica.es/board
- **Formato:** tabla HTML espublico (tbody vacío a fecha de investigación)
- **SSL:** certificado con cadena incompleta → `insecure_ssl: true`
- **Dossier:** `/dossier` (redirect con cookie) — catálogo de trámites urbanísticos

### 4. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Filtro:** `c_mun='37038'` (INE Babilafuente)
- **Capas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_sectores` (5), `plau_cyl_planes_parciales` (2)
- **Sectores:** RIUC, DOTACIONAL-1, S-1, UR-S3, I-1

## Fuentes de licencias

1. **Catálogo sede** — trámites informativos: Solicitud de Licencia Urbanística, Declaración Responsable de Obra Menor, Solicitud de Certificado o Informe Urbanístico, etc.
2. **Tablón sede** — vacío en investigación; se mantiene como fuente incremental
3. No hay listado histórico público de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_*` con `CQL_FILTER=c_mun='37038'`, `srsName=EPSG:4326`
  - 8 polígonos (1 instrumento + 5 sectores + 2 planes parciales)
- **Estrategia:** ingestión directa desde WFS en adapter; enriquecimiento por código de sector (AP-UR-*, I-1, RIUC…) en filas PlanPublica/tablón
- **Limitaciones:**
  - Web corporativa sin visor SIG integrado
  - Estudios de detalle recientes (noticias WP) sin geometría enlazable
  - Licencias sin georreferencia en fuentes públicas

## Limitaciones

- Tablón sede vacío (sin anuncios urbanísticos indexables)
- Web `babilafuente.es` inaccesible desde CI cloud (connection reset); sede y JCyL sí accesibles
- WP REST deshabilitado — scrape HTML de portada como fuente opcional
- Certificado SSL sede requiere `insecure_ssl`

## Estrategia adapter

1. **proyectos.jsonl:** IDECyL WFS (con `geom_geojson`) + PlanPublica PLAU/PLAI + tablón sede + catálogo trámites + noticias web + páginas semilla JCyL
2. **licencias.jsonl:** catálogo trámites sede (páginas informativas) + tablón cuando publique concesiones
