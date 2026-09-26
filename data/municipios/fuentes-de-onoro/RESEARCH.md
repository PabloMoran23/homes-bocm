# Fuentes de Oñoro — investigación portal ayuntamiento

**Fecha:** 2026-08-28  
**Slug:** `fuentes-de-onoro`  
**BOCYL regional (referencia):** 2 filas

## Resumen

Fuentes de Oñoro (Salamanca, frontera con Portugal) publica planeamiento y trámites urbanísticos en **cuatro portales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Web corporativa | https://fuentesdeonoro.es/ | WordPress (REST API activa) | Noticias IP sectores SUNC/SUIC, licencias, subastas parcelas |
| Normas urbanísticas | https://fuentesdeonoro.es/normas-urbanisticas/ | WordPress | Enlace PlanPublica JCyL + PDF NUM |
| Sede electrónica | https://fuentesdeonoro.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo trámites |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/ | Junta de Castilla y León | Archivo planeamiento aprobado + información pública |

## Fuentes de proyectos / expedientes

### 1. Web corporativa — WordPress REST API

- **URL base:** https://fuentesdeonoro.es/
- **REST API:** `/wp-json/wp/v2/posts?search=...` (activa)
- **Ejemplos recientes:**
  - Información pública aprobación inicial PE sector SUIC-6 (exp. 73/2026)
  - Información pública PE sectores SUNC-1, SUIC-5, SUIC-6 (ene 2025)
  - Autorización uso provisional SUNC-2 gasolinera (may 2025)
- **Limitación:** filtrar falsos positivos («campamento urbano», festividades)

### 2. PlanPublica — archivo planeamiento

- **Aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=140`
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=140`
- **Contenido:** Normas Urbanísticas Municipales (NUM, cDocId=298874, aprob. feb 2023)
- **PDF directo:** `http://www.jcyl.es/plaupdf/37/37140/298874/COMPLETO%20NUM%20Fuentes%20de%20O%F1oro.pdf`

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://fuentesdeonoro.sedelectronica.es/board
- **Formato:** tabla HTML espublico con `preview-document/UUID`
- **Contenido actual:** presupuestos, tarifas agua, plenos (pocos anuncios urbanísticos)
- **SSL:** certificado con cadena incompleta → `insecure_ssl: true`
- **Dossier:** `/dossier` — catálogo de trámites (timeout ocasional en CI)

### 4. IDECyL WFS — sectores y planes

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Filtro:** `c_mun='37140'` (INE Fuentes de Oñoro)
- **Capas:** `plau_cyl_instrumentos_ambito` (1 NUM), `plau_cyl_sectores` (11: SUNC 1-4, SUIC 1-6)
- **Campos:** `c_id_sect`, `n_num_sect`, `n_sector`, `url_doc_info`, geometría polígono

## Fuentes de licencias

1. **Noticias web** — autorizaciones de uso excepcional, licencias urbanísticas (anuncios en WP)
2. **Catálogo sede** — trámites informativos de licencia/obra (cuando accesible)
3. **Tablón sede** — sin concesiones urbanísticas indexables a fecha de investigación
4. Páginas informativas: tablón, dossier, normas urbanísticas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_*` con `CQL_FILTER=c_mun='37140'`, `srsName=EPSG:4326`
  - 12 polígonos (1 instrumento NUM + 11 sectores SUNC/SUIC)
- **Estrategia:** ingestión directa desde WFS; enriquecimiento por código sector (SUNC-*, SUIC-*) en noticias WP y PlanPublica
- **Limitaciones:**
  - Web sin visor SIG integrado
  - Licencias y autorizaciones puntuales sin geometría enlazable
  - Noticias de información pública sin polígono por expediente individual

## Limitaciones

- Tablón sede con pocos anuncios urbanísticos (mayoría administrativos)
- `/dossier` puede timeout desde CI cloud (>30s)
- Certificado SSL sede requiere `insecure_ssl`
- Municipio pequeño (2 filas BOCYL) pero con actividad urbanística reciente (NUM 2023, sectores fronterizos)

## Estrategia adapter

1. **proyectos.jsonl:** IDECyL WFS (con `geom_geojson`) + PlanPublica PLAU/PLAI + noticias WP REST + tablón sede + páginas semilla JCyL
2. **licencias.jsonl:** páginas informativas sede/web + noticias con licencia/autorización + tablón cuando publique
