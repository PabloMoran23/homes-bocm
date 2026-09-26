# Cantaracillo — investigación portal ayuntamiento

**Fecha:** 2026-09-10  
**Slug:** `cantaracillo`  
**BOCYL regional (referencia):** 1 fila

## Resumen

Cantaracillo (Salamanca, INE 37083) publica trámites y planeamiento en **dos portales principales**:

| Portal | URL | Stack | Contenido relevante |
|--------|-----|-------|---------------------|
| Sede electrónica | https://cantaracillo.sedelectronica.es | espublico gestiona (Wicket) | Tablón de anuncios, catálogo de trámites urbanísticos |
| PlanPublica JCyL | https://servicios.jcyl.es/PlanPublica/ | Junta de Castilla y León | Archivo NUM y modificaciones aprobadas |
| Diputación Salamanca | https://www.lasalina.es/...codMunicipio=83 | Gestor municipal | Ficha ayuntamiento + enlace sede |

No hay web corporativa municipal accesible (`aytocantaracillo.es` no responde desde el entorno de investigación).

## Fuentes de proyectos / expedientes

### 1. PlanPublica — archivo planeamiento

- **Aprobado:** `searchVPubDocMuniPlau.do?bInfoPublica=N&provincia=37&municipio=083`
- **Info pública:** `searchVPubDocMuniPlai.do?bInfoPublica=S&provincia=37&municipio=083`
- **Contenido (2026-09-10):** 3 documentos NUM:
  - NORMAS URBANÍSTICAS MUNICIPALES (2014)
  - MODIFICACIÓN Nº 1 DE LAS NUM — suelo rústico (2022)
  - MODIFICACIÓN Nº 2 DE LAS NUM — parámetros suelo rústico (info pública 2026)
- **Enlaces:** `openDocumento.do?cDocId=...`

### 2. IDECyL WFS — sectores e instrumentos

- **URL:** `https://idecyl.jcyl.es/geoserver/urbanismo/wfs`
- **Filtro:** `c_mun='37083'`
- **Capas:** `plau_cyl_instrumentos_ambito` (1), `plau_cyl_sectores` (6), `plau_cyl_planes_parciales` (0)
- **Sectores:** SUR-01, SUR-02, SU-NC-01..04 (polígonos MultiPolygon en WGS84)

### 3. Sede electrónica — tablón de anuncios

- **URL:** https://cantaracillo.sedelectronica.es/board
- **Formato:** tabla HTML espublico (vacío a fecha de investigación)
- **Info pública:** `/info` (sin anuncios urbanísticos indexables)
- **SSL:** certificado con cadena incompleta → `insecure_ssl: true`

### 4. Sede electrónica — catálogo trámites

- **URL:** https://cantaracillo.sedelectronica.es/dossier (requiere cookie de sesión)
- **Trámites urbanísticos relevantes:** Solicitud de Licencia o Autorización Urbanística, Declaración Responsable o Comunicación en Materia Urbanística, Solicitud de Certificado o Informe Urbanístico, Modificación del Planeamiento de Desarrollo, etc.
- **Limitación:** páginas informativas de trámite, no concesiones publicadas

## Fuentes de licencias

1. **Catálogo sede** — trámites informativos de licencias urbanísticas y actividades
2. **Tablón sede** — vacío en investigación
3. No hay listado histórico público de concesiones con coordenadas

## Geometría / visor

- **geometry_status:** `partial`
- **Fuentes:**
  - IDECyL WFS `urbanismo:plau_cyl_*` con `CQL_FILTER=c_mun='37083'`, `srsName=EPSG:4326`
  - 7 polígonos (1 instrumento NUM + 6 sectores)
- **Estrategia:** ingestión directa desde WFS; enriquecimiento por código de sector (SUR-*, SU-NC-*) en filas PlanPublica/tablón
- **Limitaciones:**
  - Sin visor SIG municipal integrado
  - Tablón vacío — licencias sin georreferencia
  - Estudios/modificaciones recientes solo como PDF en PlanPublica

## Limitaciones

- Tablón sede vacío (sin anuncios urbanísticos indexables)
- Web municipal inaccesible
- Certificado SSL sede requiere `insecure_ssl`
- Licencias: solo trámites informativos del catálogo sede

## Estrategia adapter

1. **proyectos.jsonl:** IDECyL WFS (con `geom_geojson`) + PlanPublica PLAU/PLAI + tablón sede + catálogo trámites + páginas semilla JCyL
2. **licencias.jsonl:** catálogo trámites sede (páginas informativas) + tablón cuando publique concesiones
